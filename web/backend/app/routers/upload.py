"""
Transcript upload endpoint — async pipeline.

Flow:
  1. SE pastes text OR uploads .txt / .vtt file
  2. Validator runs synchronously (cheap — rejects notes/summaries)
  3. Call row created immediately (without scorecard/insights yet)
  4. Endpoint returns 200 with call_id + redirect URL
  5. Background task runs scoring + insights and writes them onto the row
  6. Frontend redirects to /call/{id} which shows "Analyzing…" and polls
     every few seconds until the scorecard appears (then renders it)

Why async: scoring + insights are 2 sequential Claude calls. For a long
transcript that's 60-120s, and Render kills HTTP requests at ~100s. Running
synchronously caused silent failures (timed out before completion, browser
gave up). The async path returns in <1s and the analysis completes in the
background.
"""

from __future__ import annotations

import os
import sys
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Make src/ importable from web/backend/
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.db import SessionLocal, get_db
from app.deps import CurrentUser, get_current_user
from app.models import Call, Scorecard, Insights, User

from src.analysis.scoring_engine import CallContext, score_call
from src.analysis.insights_extractor import extract_insights
from src.analysis.llm_client import LLMClient
from src.utils.transcript_validator import validate, validate_with_llm_fallback, ValidationResult


router = APIRouter()


class UploadResponse(BaseModel):
    accepted: bool
    call_id: Optional[str] = None
    validation: dict
    message: str
    redirect: Optional[str] = None


def _run_analysis_in_background(call_db_id: int, call_id: str):
    """Runs Claude scoring + insights and persists to DB. Called from a
    BackgroundTask after the upload endpoint has already returned 200.

    Uses its own DB session because FastAPI's request-scoped Session is
    closed by the time the background task runs."""
    db = SessionLocal()
    try:
        call = db.query(Call).filter(Call.id == call_db_id).first()
        if not call:
            print(f"[upload.bg] call_db_id={call_db_id} disappeared; aborting analysis")
            return

        print(f"[upload.bg] starting analysis for call_id={call.call_id} "
              f"prospect={call.prospect_company!r} length={len(call.transcript or '')}")

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
        llm = LLMClient(live=bool(os.getenv("ANTHROPIC_API_KEY")))

        try:
            sc_data = score_call(ctx, llm=llm)
            ins_data = extract_insights(ctx, llm=llm)
        except Exception as e:
            # Log loudly. The call row stays in the DB without scorecard so
            # the SE can see "Analysis pending…" turning into a retry surface
            # later. Could add a status column if we want a clearer error UI.
            print(f"[upload.bg] analysis FAILED for call_id={call.call_id}: {e}")
            traceback.print_exc()
            return

        db.add(Scorecard(
            call_id=call.id,
            weighted_final=sc_data["weighted_final"],
            industry_percentile=sc_data["industry_percentile"],
            per_criterion=sc_data["per_criterion_score"],
            sub_scores=sc_data["scores"],
            qualitative=sc_data["qualitative"],
            weights_applied=sc_data.get("weights_applied", {}),
            not_assessable=sc_data.get("not_assessable", {}),
            prompt_version=sc_data["prompt_version"],
        ))
        db.add(Insights(
            call_id=call.id,
            data=ins_data,
            prompt_version=ins_data.get("prompt_version", "v1"),
        ))
        db.commit()
        print(f"[upload.bg] DONE call_id={call.call_id} "
              f"score={sc_data['weighted_final']} P{sc_data['industry_percentile']}")

        # Best-effort Notion push (no-op if unconfigured)
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
            print(f"[upload.bg] notion push failed for {call.call_id}: {e}")
    except Exception as e:
        print(f"[upload.bg] outer crash: {e}")
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


@router.post("/upload", response_model=UploadResponse)
async def upload_transcript(
    bg: BackgroundTasks,
    call_type: str = Form(...),
    prospect_company: str = Form(...),
    ae_name: Optional[str] = Form(default=""),
    prospect_industry: Optional[str] = Form(default=""),
    stated_use_case: Optional[str] = Form(default=""),
    duration_min: Optional[int] = Form(default=None),
    transcript: str = Form(default=""),
    file: Optional[UploadFile] = File(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Accept transcript, validate, persist, fire-and-forget analysis."""

    # 1. Read file if provided
    if file:
        contents = (await file.read()).decode("utf-8", errors="ignore")
        if file.filename and file.filename.lower().endswith((".vtt", ".srt")):
            contents = "\n".join(
                l for l in contents.splitlines()
                if l and "-->" not in l and not l.isdigit() and l != "WEBVTT"
            )
        transcript = contents

    # 2. Validate — heuristics first (cheap), then LLM fallback (~$0.005)
    # if heuristics rejected what could be a real transcript in an unknown
    # shape. This means weird Otter / Fellow / proprietary formats no longer
    # need manual reformatting — Claude rewrites them to canonical for us.
    result: ValidationResult = validate(transcript)
    if not result.ok:
        try:
            fallback_llm = LLMClient(live=bool(os.getenv("ANTHROPIC_API_KEY")))
            result = validate_with_llm_fallback(transcript, llm=fallback_llm)
        except Exception as e:
            print(f"[upload] LLM fallback validator threw: {e}")
    if not result.ok:
        return UploadResponse(
            accepted=False,
            validation={"kind": result.kind, "title": result.title,
                        "detail": result.detail, "metrics": result.metrics},
            message="Rejected — paste a real call transcript, not notes or a summary.",
        )
    transcript = result.normalized or transcript

    # 3. Look up SE user
    se = db.query(User).filter(User.email == user.email).first()
    if not se:
        raise HTTPException(404, "User not found")

    # 4. Persist the Call row immediately (no scorecard/insights yet — those
    #    arrive when the background task lands)
    call_id = f"call_{uuid.uuid4().hex[:12]}"
    duration = duration_min or result.metrics.get("word_count", 0) // 150  # ~150 wpm
    call = Call(
        call_id=call_id, se_id=se.id, se_name=se.name, ae_name=ae_name,
        prospect_company=prospect_company, prospect_industry=prospect_industry,
        stated_use_case=stated_use_case, duration_min=duration,
        call_type=call_type, source="upload",
        call_date=datetime.now(timezone.utc),
        transcript=transcript,
    )
    db.add(call); db.commit(); db.refresh(call)

    # 5. Fire-and-forget the analysis. We pass the DB id; the BG task opens
    #    its own session (FastAPI closes ours when this function returns).
    bg.add_task(_run_analysis_in_background, call.id, call.call_id)

    return UploadResponse(
        accepted=True,
        call_id=call_id,
        validation={"kind": result.kind, "title": result.title, "metrics": result.metrics},
        message="Transcript accepted. Analysis is running in the background.",
        redirect=f"/call/{call_id}",
    )
