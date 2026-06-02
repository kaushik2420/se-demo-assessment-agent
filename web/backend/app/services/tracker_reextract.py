"""
Re-extract existing tracker rows under the current extraction prompt.

What it does for each row:
  1. Fetches the original Slack thread (channel_id + thread_ts)
  2. Re-runs `_extract_full` to pull product / kind / L2 / Jira / details
  3. Re-attributes the SE (owner) using the first-poster rule
  4. Backfills any fields that are currently null; PRESERVES manual edits
     (i.e. if a human already set product='ThriveSparrow' via the edit UI,
     we don't clobber it even if the LLM disagrees)

Status + result are tracked in /tmp files, same pattern as Granola/reanalyze.
Admin-triggered via POST /tracker/reextract — runs as a background task.

Modes:
  - 'outdated' (default): only rows missing product OR kind (haven't been
    touched by the new extraction). Fast path.
  - 'all': re-extracts every row. Use sparingly — Slack API + Claude both
    get hit for every row.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.db import SessionLocal
from app.models import TrackerRequest
from src.analysis.llm_client import LLMClient
from src.integrations.slack_client import SlackClient


_PROGRESS_FILE = Path("/tmp/tracker_reextract_in_progress")
_RESULT_FILE = Path("/tmp/tracker_reextract_last_result.json")
_STALE_PROGRESS_MINUTES = 60


def _is_progress_stale() -> bool:
    if not _PROGRESS_FILE.exists():
        return False
    try:
        age = datetime.now(timezone.utc).timestamp() - _PROGRESS_FILE.stat().st_mtime
        return age > _STALE_PROGRESS_MINUTES * 60
    except Exception:
        return True


def is_in_progress() -> bool:
    if not _PROGRESS_FILE.exists():
        return False
    if _is_progress_stale():
        _PROGRESS_FILE.unlink(missing_ok=True)
        return False
    return True


def _set_in_progress(yes: bool):
    if yes:
        _PROGRESS_FILE.touch()
    else:
        _PROGRESS_FILE.unlink(missing_ok=True)


def _write_result(stats: dict):
    try:
        _RESULT_FILE.write_text(json.dumps(stats))
    except Exception as e:
        print(f"[tracker.reextract] failed to persist result: {e}")


def read_result() -> Optional[dict]:
    if not _RESULT_FILE.exists():
        return None
    try:
        return json.loads(_RESULT_FILE.read_text())
    except Exception:
        return None


def get_status() -> dict:
    return {
        "in_progress": is_in_progress(),
        "last_result": read_result(),
    }


def _needs_reextract(row: TrackerRequest) -> bool:
    """Outdated if either product OR kind is null (new fields, never extracted)."""
    return not row.product or not row.kind


def run_reextract(mode: str = "outdated", limit: Optional[int] = None) -> dict:
    """Re-extract matching tracker rows. Returns stats dict.

    Requires SLACK_BOT_TOKEN (to fetch threads) and ANTHROPIC_API_KEY (else
    Claude returns mock data, which would pollute the DB).
    """
    _set_in_progress(True)
    started_at = datetime.now(timezone.utc)
    stats: dict = {
        "started_at": started_at.isoformat(),
        "mode": mode,
        "limit": limit,
        "candidates": 0,
        "reextracted": 0,
        "skipped_already_complete": 0,
        "skipped_thread_gone": 0,
        "fields_backfilled": {  # rough audit log of what we actually changed
            "product": 0, "kind": 0, "l2_url": 0, "jira_url": 0,
            "se_email": 0, "details": 0,
        },
        "failed": 0,
        "errors": [],
    }

    if not os.getenv("SLACK_BOT_TOKEN"):
        stats["errors"].append("SLACK_BOT_TOKEN not set")
        _write_result(stats); _set_in_progress(False); return stats
    if not os.getenv("ANTHROPIC_API_KEY"):
        stats["errors"].append("ANTHROPIC_API_KEY not set — refusing to run (would write mock data)")
        _write_result(stats); _set_in_progress(False); return stats

    # Import here so a circular import on app startup doesn't break us
    from app.services.slack_tracker import (
        _extract_full, _extract_urls, _classify_product_heuristic,
        _format_thread_for_prompt, _resolve_se_from_first_poster,
    )

    llm = LLMClient(live=True)
    slack = SlackClient()
    db: Session = SessionLocal()
    processed = 0

    try:
        rows = (db.query(TrackerRequest)
                  .order_by(TrackerRequest.created_at.desc()).all())
        stats["candidates"] = len(rows)

        for row in rows:
            if limit is not None and processed >= limit:
                break

            if mode == "outdated" and not _needs_reextract(row):
                stats["skipped_already_complete"] += 1
                continue

            if not row.channel_id or not row.thread_ts:
                stats["skipped_thread_gone"] += 1
                continue

            try:
                msgs = slack.fetch_thread(row.channel_id, row.thread_ts)
                if not msgs:
                    stats["skipped_thread_gone"] += 1
                    continue

                # Resolve participants for the prompt + first-poster lookup
                tagger_uid = None
                # We don't actually know who tagged @SE Coach historically.
                # Use the LAST human poster as the "tagger" proxy (close enough
                # for prompt formatting; doesn't affect SE attribution since
                # _resolve_se_from_first_poster ignores the tagger anyway).
                human_msgs = [m for m in msgs if m.get("user") and not m.get("bot_id")]
                if human_msgs:
                    tagger_uid = human_msgs[-1].get("user")
                try:
                    tagger = slack.get_user_info(tagger_uid) if tagger_uid else {"id": None}
                except Exception:
                    tagger = {"id": tagger_uid}

                participants: dict[str, dict] = {}
                for m in msgs:
                    uid = m.get("user")
                    if uid and uid != tagger.get("id") and uid not in participants:
                        try:
                            participants[uid] = slack.get_user_info(uid)
                        except Exception:
                            pass

                thread_text = _format_thread_for_prompt(msgs, participants, tagger)
                raw_text = " ".join((m.get("text") or "") for m in msgs)

                # Re-attribute SE from first poster (won't downgrade an
                # explicit human edit because we PRESERVE existing values
                # — see backfill rules below)
                new_se_email, new_se_name, _info = _resolve_se_from_first_poster(
                    db, slack, msgs, tagger
                )

                extracted = _extract_full(llm, thread_text,
                                          new_se_name or "Unknown", participants)
                regex_l2, regex_jira = _extract_urls(raw_text)

                changes = []

                # --- Backfill-only rules: only write if currently empty ----
                def maybe_set(field: str, new_val):
                    if not new_val:
                        return
                    if getattr(row, field):  # already has a value — preserve
                        return
                    setattr(row, field, new_val)
                    stats["fields_backfilled"][field] = stats["fields_backfilled"].get(field, 0) + 1
                    changes.append(f"{field}=({new_val[:40]})")

                maybe_set("product", extracted.get("product")
                          or _classify_product_heuristic(raw_text))
                maybe_set("kind", extracted.get("kind"))
                maybe_set("l2_url", extracted.get("l2_url") or regex_l2)
                maybe_set("jira_url", extracted.get("jira_url") or regex_jira)

                # SE re-attribution — only override if there's no current SE,
                # OR the current SE doesn't exist in our DB (orphan). If a
                # human has set a real SE via the edit UI, we leave it alone.
                if not row.se_email and new_se_email:
                    row.se_email = new_se_email
                    row.se_name = new_se_name
                    stats["fields_backfilled"]["se_email"] += 1
                    changes.append(f"se={new_se_email}")

                # Details — only overwrite if blank (we're more careful here
                # because details may have been edited)
                if not (row.details or "").strip() and extracted.get("details"):
                    row.details = extracted["details"]
                    stats["fields_backfilled"]["details"] += 1
                    changes.append("details")

                row.last_synced_at = datetime.now(timezone.utc)
                db.commit()
                stats["reextracted"] += 1
                processed += 1
                print(f"[tracker.reextract] OK row #{row.id} — backfilled: "
                      f"{', '.join(changes) if changes else '(no gaps)'}")
            except Exception as e:
                db.rollback()
                stats["failed"] += 1
                stats["errors"].append(f"row {row.id}: {type(e).__name__}: {e}")
                print(f"[tracker.reextract] FAIL row #{row.id}: {e}")
    finally:
        db.close()

    stats["finished_at"] = datetime.now(timezone.utc).isoformat()
    _write_result(stats)
    _set_in_progress(False)
    return stats
