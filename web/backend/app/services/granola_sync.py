"""
Granola sync orchestrator — pulls notes from Granola Enterprise API and runs
the full scoring pipeline on new ones.

Workflow:
  1. List notes created since last sync (cursor-paginated).
  2. For each new note ID:
     a. Skip if already imported (external_id match).
     b. Fetch full note (transcript + calendar event + attendees).
     c. Optional folder filter — if GRANOLA_FOLDER_NAME is set, skip notes
        not in that workspace folder.
     d. Optional external-attendee filter — skip internal-only meetings.
     e. Match note.owner.email to an SE in our DB.
     f. Auto-detect call_type from title.
     g. Format transcript with SE name attribution.
     h. Score + extract insights via Claude.
     i. Persist Call + Scorecard + Insights.
  3. Update last_sync_at to start-of-run timestamp.

Notes:
  - Granola's API only returns notes shared to workspace folders, so personal
    notes are never exposed to us. Privacy is enforced by the SE choosing
    which folder to save into.
  - Transcript speaker labels are 'microphone' (SE) / 'speaker' (everyone
    else). We label SE turns with their name; non-SE turns go in as 'Speaker'.
    The scoring prompt includes the attendee list so Claude can attribute
    Prospect vs AE from content.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

# Make src/ importable
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.db import SessionLocal
from app.models import Call, Insights, Scorecard, User

from src.analysis.insights_extractor import extract_insights
from src.analysis.llm_client import LLMClient
from src.analysis.scoring_engine import CallContext, score_call
from src.ingestion.granola_client import GranolaClient, GranolaNoteDetail


INTERNAL_DOMAIN = os.getenv("INTERNAL_DOMAIN", "surveysparrow.com")

# Optional: restrict ingestion to a specific workspace folder name.
# If unset, all workspace-accessible notes are eligible (modulo external filter).
GRANOLA_FOLDER_NAME = os.getenv("GRANOLA_FOLDER_NAME", "").strip()

# Persisted state on local disk. For MVP this is fine — single Render dyno.
# Would move to DB if we ever scale to multi-instance.
_STATE_FILE = Path("/tmp/granola_last_sync.txt")
_RESULT_FILE = Path("/tmp/granola_last_result.json")
_PROGRESS_FILE = Path("/tmp/granola_sync_in_progress")

# If a sync has been "in progress" longer than this, assume the process died
# without cleaning up and treat the flag as stale.
_STALE_PROGRESS_MINUTES = 15


def _is_progress_stale() -> bool:
    if not _PROGRESS_FILE.exists():
        return False
    try:
        age_seconds = datetime.now(timezone.utc).timestamp() - _PROGRESS_FILE.stat().st_mtime
        return age_seconds > _STALE_PROGRESS_MINUTES * 60
    except Exception:
        return True  # if we can't stat, treat as stale to allow recovery


def _is_in_progress() -> bool:
    """True only if a sync is currently running (not stale)."""
    if not _PROGRESS_FILE.exists():
        return False
    if _is_progress_stale():
        _PROGRESS_FILE.unlink(missing_ok=True)  # auto-cleanup
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
        print(f"[granola_sync] failed to persist last result: {e}")


def _read_result() -> Optional[dict]:
    if not _RESULT_FILE.exists():
        return None
    try:
        return json.loads(_RESULT_FILE.read_text())
    except Exception:
        return None


# Always look back at least this far on every sync, regardless of last_sync_at.
# Why: Granola's `updated_after` filter catches retroactively-shared notes only
# within its window. A 30-day overlap window means even if a team member
# back-shares a 3-week-old note, we still pick it up. Dedupe via external_id
# prevents reprocessing, so the cost is just extra API list calls (cheap).
LOOKBACK_DAYS = 30


def _read_last_sync() -> datetime:
    """Used only for the UI 'last sync N min ago' display. NOT used for filtering."""
    if _STATE_FILE.exists():
        try:
            return datetime.fromisoformat(_STATE_FILE.read_text().strip())
        except Exception:
            pass
    return datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)


def _query_window() -> datetime:
    """The actual datetime we send to Granola — always a constant 30-day lookback."""
    return datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)


def _write_last_sync(when: datetime):
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(when.isoformat())


def get_status() -> dict:
    """Snapshot of sync state for the admin UI."""
    last = _read_last_sync()
    return {
        "last_sync_at": last.isoformat(),
        "minutes_since_last_sync": int((datetime.now(timezone.utc) - last).total_seconds() // 60),
        "configured": bool(os.getenv("GRANOLA_API_KEY")),
        "internal_domain": INTERNAL_DOMAIN,
        "folder_filter": GRANOLA_FOLDER_NAME or None,
        "in_progress": _is_in_progress(),
        "last_result": _read_result(),
    }


def _detect_call_type(title: str) -> str:
    t = (title or "").lower()
    if "closure" in t or "close" in t or "commitment" in t:
        return "closure"
    if "poc" in t or "proof of concept" in t:
        return "poc"
    if "follow-up" in t or "followup" in t or "follow up" in t:
        return "followup_demo" if "demo" in t else "followup_query"
    if "demo" in t or "discovery" in t or "intro" in t or "walkthrough" in t:
        return "demo"
    return "demo"


def _prospect_company(note: GranolaNoteDetail) -> str:
    """Infer prospect company from the first external attendee's email domain."""
    externals = note.external_attendees(INTERNAL_DOMAIN)
    if not externals:
        return "Unknown"
    email = externals[0].get("email", "")
    if "@" in email:
        return email.split("@")[1].split(".")[0].title()
    return "Unknown"


def _attendee_summary(note: GranolaNoteDetail, se_name: str) -> str:
    """Render the attendee list as a transcript header so Claude can attribute."""
    lines = [f"Call attendees:", f"  SE: {se_name}"]
    for a in note.attendees:
        email = (a.get("email") or "").lower()
        name = a.get("name") or email
        if not email:
            continue
        if email.endswith(f"@{INTERNAL_DOMAIN}"):
            lines.append(f"  Internal: {name} <{email}>")
        else:
            lines.append(f"  Prospect-side: {name} <{email}>")
    return "\n".join(lines)


def run_sync(force_since: Optional[datetime] = None, dry_run: bool = False) -> dict:
    """
    Run a single Granola sync. Returns a stats dict for the admin UI / logs.
    Safe to call from APScheduler, the manual sync button (via background task),
    or a manual debug call.

    This function may take minutes to complete (each note triggers Claude
    scoring + insight extraction). Callers from HTTP context should invoke
    it via FastAPI BackgroundTasks to avoid request timeouts.
    """
    _set_in_progress(True)
    started_at = datetime.now(timezone.utc)
    # IMPORTANT: we use a constant 30-day lookback (not last_sync_at) so that
    # retroactively-shared notes get caught. Dedupe via external_id prevents
    # double-processing notes we've seen before.
    since = force_since or _query_window()
    stats = {
        "started_at": started_at.isoformat(),
        "since": since.isoformat(),
        "lookback_days": LOOKBACK_DAYS,
        "notes_seen": 0,
        "imported": 0,
        "skipped_folder_filter": 0,
        "skipped_external_filter": 0,
        "skipped_already_imported": 0,
        "skipped_unknown_se": 0,
        "skipped_no_transcript": 0,
        "analysis_failed": 0,
        "errors": [],
    }

    if not os.getenv("GRANOLA_API_KEY"):
        stats["errors"].append("GRANOLA_API_KEY not set")
        _write_result(stats); _set_in_progress(False)
        return stats

    try:
        client = GranolaClient()
        # Use updated_after (not created_after) so we catch notes that were
        # CREATED earlier but SHARED-TO-FOLDER recently. This is the fix for
        # retroactive shares that previously got missed by incremental sync.
        notes = client.list_notes_since(updated_after=since)
    except Exception as e:
        stats["errors"].append(f"list_notes_since failed: {e}")
        _write_result(stats); _set_in_progress(False)
        return stats

    stats["notes_seen"] = len(notes)

    # Diagnostic: which owners did the API return notes for? If this only ever
    # contains the token-owner's email, the API is user-scoped — Granola won't
    # return other workspace members' notes even if they're shared to a
    # workspace folder. That requires a different (workspace-level) token.
    owners_seen = sorted({n.owner_email for n in notes if n.owner_email})
    stats["owners_seen"] = owners_seen
    print(f"[granola_sync] notes_seen={len(notes)} owners={owners_seen!r}")

    llm = LLMClient(live=bool(os.getenv("ANTHROPIC_API_KEY")))

    db: Session = SessionLocal()
    try:
        ses = {u.email.lower(): u for u in db.query(User).all()}

        for note_meta in notes:
            # Dedupe early — before paying for the detail GET
            existing = db.query(Call).filter(Call.external_id == note_meta.id).first()
            if existing:
                stats["skipped_already_imported"] += 1
                continue

            # Match owner to SE
            se = ses.get(note_meta.owner_email)
            if not se:
                stats["skipped_unknown_se"] += 1
                continue

            # Fetch full note
            try:
                note = client.get_note(note_meta.id, include_transcript=True)
            except Exception as e:
                stats["errors"].append(f"get_note {note_meta.id}: {e}")
                continue

            # Folder filter (strict).
            #
            # Notes must explicitly live in GRANOLA_FOLDER_NAME (default
            # "Calls for analysis"). Match is case-insensitive + whitespace
            # tolerant. Notes with empty folder_membership are PERSONAL notes
            # — they have not been opted in by the SE and must be rejected.
            #
            # We log every rejection with the actual folder_membership and
            # raw-note keys so we can see WHY a given note got skipped
            # (and notice if Granola is putting folder info somewhere else).
            if GRANOLA_FOLDER_NAME:
                wanted = GRANOLA_FOLDER_NAME.strip().casefold()
                seen_raw = [(f.get("name") or "") for f in note.folder_membership]
                seen_norm = [n.strip().casefold() for n in seen_raw]
                if wanted not in seen_norm:
                    folder_ish = {k: v for k, v in (note.raw or {}).items()
                                  if "folder" in k.lower()}
                    print(f"[granola_sync] skipped_folder_filter note={note.id!r} "
                          f"title={note.title!r} owner={note.owner_email!r} "
                          f"wanted={GRANOLA_FOLDER_NAME!r} seen={seen_raw!r} "
                          f"raw_keys={list((note.raw or {}).keys())} "
                          f"folder_ish={folder_ish!r}")
                    stats["skipped_folder_filter"] += 1
                    continue

            # External-meeting filter
            if not note.is_external(INTERNAL_DOMAIN):
                stats["skipped_external_filter"] += 1
                continue

            transcript_body = note.transcript_text(se.name)
            if not transcript_body or len(transcript_body) < 100:
                stats["skipped_no_transcript"] += 1
                continue

            if dry_run:
                stats["imported"] += 1
                continue

            # Prepend attendee list so Claude can attribute speaker turns
            transcript = f"{_attendee_summary(note, se.name)}\n\n{transcript_body}"

            call_id = f"granola_{uuid.uuid4().hex[:12]}"
            call_type = _detect_call_type(note.title)
            prospect = _prospect_company(note)
            duration_min = note.duration_min()

            ctx = CallContext(
                se_name=se.name, ae_name="",
                prospect_company=prospect, prospect_industry="",
                stated_use_case=note.title,
                duration_min=duration_min,
                transcript=transcript, call_id=call_id, call_type=call_type,
            )

            try:
                sc = score_call(ctx, llm=llm)
                ins = extract_insights(ctx, llm=llm)
            except Exception as e:
                stats["analysis_failed"] += 1
                stats["errors"].append(f"analysis failed for note {note.id}: {e}")
                continue

            try:
                call = Call(
                    call_id=call_id, external_id=note.id, se_id=se.id, se_name=se.name,
                    ae_name=None, prospect_company=prospect, prospect_industry=None,
                    stated_use_case=note.title, duration_min=duration_min,
                    call_type=call_type, source="granola",
                    call_date=_parse_dt(note.scheduled_start) or datetime.now(timezone.utc),
                    transcript=transcript,
                )
                db.add(call); db.flush()
                db.add(Scorecard(
                    call_id=call.id,
                    weighted_final=sc["weighted_final"],
                    industry_percentile=sc["industry_percentile"],
                    per_criterion=sc["per_criterion_score"],
                    sub_scores=sc["scores"],
                    qualitative=sc["qualitative"],
                    weights_applied=sc.get("weights_applied", {}),
                    prompt_version=sc["prompt_version"],
                ))
                db.add(Insights(
                    call_id=call.id, data=ins,
                    prompt_version=ins.get("prompt_version", "v1"),
                ))
                db.commit()
                stats["imported"] += 1
                # Push to Notion tracker (best-effort, no-op if not configured)
                try:
                    from app.services.notion_sync import push_call
                    push_result = push_call(
                        call_data={
                            "prospect_company": prospect, "call_date": call.call_date,
                            "call_type": call_type, "se_name": se.name,
                            "ae_name": None, "stated_use_case": note.title,
                        },
                        insights=ins,
                    )
                    if push_result.get("pushed") is False and push_result.get("reason") and "not set" not in push_result["reason"]:
                        stats["errors"].append(f"notion push failed for {note.id}: {push_result['reason']}")
                except Exception as e:
                    stats["errors"].append(f"notion push exception for {note.id}: {e}")
            except Exception as e:
                db.rollback()
                stats["errors"].append(f"persist failed for note {note.id}: {e}")
    finally:
        db.close()

    _write_last_sync(started_at)
    stats["finished_at"] = datetime.now(timezone.utc).isoformat()
    _write_result(stats)
    _set_in_progress(False)
    return stats


def _parse_dt(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None
