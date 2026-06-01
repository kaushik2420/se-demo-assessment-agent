"""
Re-analyze existing calls under the current scoring/insights prompt version.

Use case: prompts change (e.g. v2 adds not_assessable handling, split features,
product field). We want every call in the system to be measurable against the
same yardstick. This service walks every call with a transcript, re-runs the
analysis pipeline, and updates the Scorecard + Insights rows in place.

Runs as a background task (long — many Claude calls). Progress and last result
live in /tmp like the Granola sync.

Filters:
  - mode='outdated' (default): only calls whose scorecard.prompt_version OR
    insights.prompt_version differs from the current code version
  - mode='all': every call with a transcript (use sparingly — costs $$$)
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
from app.models import Call, Insights, Scorecard

from prompts import scoring_prompt, insights_prompt
from src.analysis.insights_extractor import extract_insights
from src.analysis.llm_client import LLMClient
from src.analysis.scoring_engine import CallContext, score_call


_PROGRESS_FILE = Path("/tmp/reanalyze_in_progress")
_RESULT_FILE = Path("/tmp/reanalyze_last_result.json")
_STALE_PROGRESS_MINUTES = 60  # re-analysis can be slow


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
        print(f"[reanalyze] failed to persist result: {e}")


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
        "current_scoring_version": scoring_prompt.VERSION,
        "current_insights_version": insights_prompt.VERSION,
        "last_result": read_result(),
    }


def _needs_reanalysis(call: Call) -> bool:
    """True if scorecard OR insights is on an older prompt version."""
    sc = call.scorecard
    ins = call.insights
    if sc is None or ins is None:
        return True  # missing analysis → re-analyze
    if (sc.prompt_version or "") != scoring_prompt.VERSION:
        return True
    if (ins.prompt_version or "") != insights_prompt.VERSION:
        return True
    return False


def run_reanalysis(mode: str = "outdated", limit: Optional[int] = None) -> dict:
    """Re-run analysis for matching calls.

    mode:
      - 'outdated': only calls whose prompt_version != current
      - 'all': every call (re-runs even if already up to date)
    limit: cap on number of calls processed (None = all)
    """
    _set_in_progress(True)
    started_at = datetime.now(timezone.utc)
    stats: dict = {
        "started_at": started_at.isoformat(),
        "mode": mode,
        "limit": limit,
        "scoring_version": scoring_prompt.VERSION,
        "insights_version": insights_prompt.VERSION,
        "candidates": 0,
        "reanalyzed": 0,
        "skipped_up_to_date": 0,
        "skipped_no_transcript": 0,
        "failed": 0,
        "errors": [],
    }

    if not os.getenv("ANTHROPIC_API_KEY"):
        stats["errors"].append("ANTHROPIC_API_KEY not set — refusing to run (would produce mock data)")
        _write_result(stats); _set_in_progress(False)
        return stats

    llm = LLMClient(live=True)
    db: Session = SessionLocal()
    try:
        calls = db.query(Call).order_by(Call.created_at.desc()).all()
        stats["candidates"] = len(calls)

        processed = 0
        for call in calls:
            if limit is not None and processed >= limit:
                break

            if mode == "outdated" and not _needs_reanalysis(call):
                stats["skipped_up_to_date"] += 1
                continue

            if not (call.transcript or "").strip():
                stats["skipped_no_transcript"] += 1
                continue

            try:
                ctx = CallContext(
                    se_name=call.se_name,
                    ae_name=call.ae_name or "",
                    prospect_company=call.prospect_company,
                    prospect_industry=call.prospect_industry or "",
                    stated_use_case=call.stated_use_case or "",
                    duration_min=call.duration_min or 0,
                    transcript=call.transcript,
                    call_id=call.call_id,
                    call_type=call.call_type,
                )

                sc_data = score_call(ctx, llm=llm)
                ins_data = extract_insights(ctx, llm=llm)

                # Upsert Scorecard
                sc = call.scorecard or Scorecard(call_id=call.id)
                sc.weighted_final = sc_data["weighted_final"]
                sc.industry_percentile = sc_data["industry_percentile"]
                sc.per_criterion = sc_data["per_criterion_score"]
                sc.sub_scores = sc_data["scores"]
                sc.qualitative = sc_data["qualitative"]
                sc.weights_applied = sc_data.get("weights_applied", {})
                sc.not_assessable = sc_data.get("not_assessable", {})
                sc.prompt_version = sc_data["prompt_version"]
                if sc.id is None:
                    db.add(sc)

                # Upsert Insights
                ins = call.insights or Insights(call_id=call.id)
                ins.data = ins_data
                ins.prompt_version = ins_data.get("prompt_version", "v1")
                if ins.id is None:
                    db.add(ins)

                db.commit()
                stats["reanalyzed"] += 1
                processed += 1
                print(f"[reanalyze] OK call={call.call_id} prospect={call.prospect_company!r} "
                      f"new_score={sc.weighted_final}")
            except Exception as e:
                db.rollback()
                stats["failed"] += 1
                stats["errors"].append(f"{call.call_id}: {type(e).__name__}: {e}")
                print(f"[reanalyze] FAIL call={call.call_id}: {e}")

    finally:
        db.close()

    stats["finished_at"] = datetime.now(timezone.utc).isoformat()
    _write_result(stats)
    _set_in_progress(False)
    return stats
