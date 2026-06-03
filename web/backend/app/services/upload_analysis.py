"""
Background analysis runner for uploaded transcripts.

Why a dedicated module + threading instead of FastAPI BackgroundTasks:
  - FastAPI BackgroundTasks run inside the worker process AFTER the response.
    On Render free/starter, if the worker is busy or the dyno sleeps, tasks
    can be delayed indefinitely with no observable failure mode.
  - threading.Thread(daemon=True) is dirt simple and runs immediately. The
    worker stays alive as long as the FastAPI app is running.
  - We track explicit lifecycle status on the Call row (pending/analyzing/
    done/failed) so the UI can SHOW errors instead of spinning forever.

Public surface:
  - kickoff_analysis(call_db_id, call_id):
      Set status='analyzing' and spawn a thread that runs the scoring +
      insights pipeline. Returns immediately. Idempotent — if status is
      already 'analyzing', does nothing.
  - mark_stuck_as_failed():
      Cron-friendly. Any call stuck in 'analyzing' for >ANALYSIS_STUCK_MIN
      minutes is presumed dead and gets marked 'failed' so the user can
      retry from the UI.
"""

from __future__ import annotations

import os
import sys
import threading
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make src/ importable
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.db import SessionLocal
from app.models import Call, Insights, Scorecard

from src.analysis.scoring_engine import CallContext, score_call
from src.analysis.insights_extractor import extract_insights
from src.analysis.llm_client import LLMClient


# After this many minutes in 'analyzing', presume the worker died and
# mark the row as 'failed' so the UI surfaces a retry button instead of
# polling forever.
ANALYSIS_STUCK_MIN = 15


def _set_status(call_db_id: int, **fields):
    """Helper: open a session, update Call status fields, commit, close."""
    db = SessionLocal()
    try:
        call = db.query(Call).filter(Call.id == call_db_id).first()
        if not call:
            return
        for k, v in fields.items():
            setattr(call, k, v)
        db.commit()
    except Exception as e:
        print(f"[upload_analysis] failed to update status for call_db_id={call_db_id}: {e}")
        db.rollback()
    finally:
        db.close()


def _run(call_db_id: int, call_id: str):
    """Worker body. Runs in a daemon thread.

    Strict lifecycle:
      1. Set status='analyzing', analysis_started_at=now (already done by caller)
      2. Run score_call + extract_insights (slow)
      3. Persist Scorecard + Insights rows
      4. Set status='done', clear analysis_error
      5. Best-effort Notion push (failures don't change status)

    Any exception at steps 2-3 → status='failed' with a short error message
    the user can see in the UI. Traceback always goes to logs.
    """
    print(f"[upload_analysis] >>> START call_id={call_id} call_db_id={call_db_id}")
    db = SessionLocal()
    try:
        call = db.query(Call).filter(Call.id == call_db_id).first()
        if not call:
            print(f"[upload_analysis] call_db_id={call_db_id} disappeared; aborting")
            return

        if not (call.transcript or "").strip():
            _set_status(call_db_id, analysis_status="failed",
                        analysis_error="Empty transcript — nothing to analyze")
            return

        if not os.getenv("ANTHROPIC_API_KEY"):
            _set_status(call_db_id, analysis_status="failed",
                        analysis_error="ANTHROPIC_API_KEY not set on server — contact admin")
            return

        print(f"[upload_analysis] call_id={call_id} prospect={call.prospect_company!r} "
              f"transcript_chars={len(call.transcript)} se={call.se_name!r}")

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
        llm = LLMClient(live=True)

        # ---- scoring ----
        try:
            print(f"[upload_analysis] {call_id} → score_call() …")
            sc_data = score_call(ctx, llm=llm)
            print(f"[upload_analysis] {call_id} ← score_call() ok "
                  f"score={sc_data.get('weighted_final')}")
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[upload_analysis] {call_id} score_call() FAILED: {e}\n{tb}")
            _set_status(call_db_id, analysis_status="failed",
                        analysis_error=f"Scoring failed: {type(e).__name__}: {str(e)[:500]}")
            return

        # ---- insights ----
        try:
            print(f"[upload_analysis] {call_id} → extract_insights() …")
            ins_data = extract_insights(ctx, llm=llm)
            print(f"[upload_analysis] {call_id} ← extract_insights() ok "
                  f"product={(ins_data.get('product') or {}).get('primary')!r}")
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[upload_analysis] {call_id} extract_insights() FAILED: {e}\n{tb}")
            _set_status(call_db_id, analysis_status="failed",
                        analysis_error=f"Insights extraction failed: {type(e).__name__}: {str(e)[:500]}")
            return

        # ---- persist ----
        try:
            # If a previous run created a Scorecard/Insights row (retry case),
            # update it in place instead of inserting a duplicate.
            existing_sc = db.query(Scorecard).filter(Scorecard.call_id == call.id).first()
            sc = existing_sc or Scorecard(call_id=call.id)
            sc.weighted_final = sc_data["weighted_final"]
            sc.industry_percentile = sc_data["industry_percentile"]
            sc.per_criterion = sc_data["per_criterion_score"]
            sc.sub_scores = sc_data["scores"]
            sc.qualitative = sc_data["qualitative"]
            sc.weights_applied = sc_data.get("weights_applied", {})
            sc.not_assessable = sc_data.get("not_assessable", {})
            sc.prompt_version = sc_data["prompt_version"]
            if existing_sc is None:
                db.add(sc)

            existing_ins = db.query(Insights).filter(Insights.call_id == call.id).first()
            ins = existing_ins or Insights(call_id=call.id)
            ins.data = ins_data
            ins.prompt_version = ins_data.get("prompt_version", "v1")
            if existing_ins is None:
                db.add(ins)

            call.analysis_status = "done"
            call.analysis_error = None
            db.commit()
            print(f"[upload_analysis] <<< DONE call_id={call_id} "
                  f"score={sc.weighted_final} P{sc.industry_percentile}")
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[upload_analysis] {call_id} persist FAILED: {e}\n{tb}")
            db.rollback()
            _set_status(call_db_id, analysis_status="failed",
                        analysis_error=f"DB write failed: {type(e).__name__}: {str(e)[:500]}")
            return

        # ---- best-effort Notion push ----
        try:
            from app.services.notion_sync import push_call
            push_call(
                call_data={
                    "prospect_company": call.prospect_company,
                    "call_date": call.call_date,
                    "call_type": call.call_type,
                    "se_name": call.se_name,
                    "ae_name": call.ae_name,
                    "stated_use_case": call.stated_use_case,
                },
                insights=ins_data,
            )
        except Exception as e:
            print(f"[upload_analysis] {call_id} notion push failed (non-fatal): {e}")
    except Exception as e:
        # Belt-and-suspenders catch-all
        tb = traceback.format_exc()
        print(f"[upload_analysis] {call_id} outer crash: {e}\n{tb}")
        try:
            _set_status(call_db_id, analysis_status="failed",
                        analysis_error=f"Unexpected error: {type(e).__name__}: {str(e)[:300]}")
        except Exception:
            pass
    finally:
        db.close()


def kickoff_analysis(call_db_id: int, call_id: str):
    """Set status='analyzing' and spawn the worker thread.

    Safe to call multiple times — if status is already 'analyzing', does
    nothing (prevents double-spawn on retry-clicks before the worker has
    flipped status to 'done' or 'failed').
    """
    db = SessionLocal()
    try:
        call = db.query(Call).filter(Call.id == call_db_id).first()
        if not call:
            print(f"[upload_analysis] kickoff: call_db_id={call_db_id} not found")
            return
        if call.analysis_status == "analyzing":
            # Already running — let it finish; UI will pick up the result.
            print(f"[upload_analysis] kickoff: {call_id} already analyzing, skipping spawn")
            return
        call.analysis_status = "analyzing"
        call.analysis_started_at = datetime.now(timezone.utc)
        call.analysis_error = None
        db.commit()
    finally:
        db.close()

    t = threading.Thread(target=_run, args=(call_db_id, call_id),
                         name=f"analysis-{call_id}", daemon=True)
    t.start()
    print(f"[upload_analysis] kickoff: spawned thread {t.name}")


def mark_stuck_as_failed() -> dict:
    """Cron: any call that's been 'analyzing' for >ANALYSIS_STUCK_MIN
    minutes is presumed dead (worker crashed, dyno restarted, OOM, etc).
    Mark it 'failed' so the user can retry from the UI."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=ANALYSIS_STUCK_MIN)
    db = SessionLocal()
    stats = {"checked": 0, "marked_failed": 0}
    try:
        stuck = (db.query(Call)
                 .filter(Call.analysis_status == "analyzing")
                 .filter(Call.analysis_started_at < cutoff)
                 .all())
        stats["checked"] = len(stuck)
        for c in stuck:
            c.analysis_status = "failed"
            c.analysis_error = (
                f"Analysis didn't complete within {ANALYSIS_STUCK_MIN} minutes "
                f"(worker likely crashed). Click Retry to try again."
            )
            stats["marked_failed"] += 1
        if stuck:
            db.commit()
            print(f"[upload_analysis] marked {len(stuck)} stuck calls as failed")
    finally:
        db.close()
    return stats
