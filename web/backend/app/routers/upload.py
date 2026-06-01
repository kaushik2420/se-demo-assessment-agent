"""
Transcript upload endpoint — runs the FULL analysis pipeline synchronously.

Flow:
  1. SE pastes text OR uploads .txt / .vtt file
  2. Validator runs (rejects notes/summaries)
  3. Score the rubric (Claude or mock if no key)
  4. Extract 9 deal-intel signals
  5. Persist Call + Scorecard + Insights to DB
  6. Return scorecard immediately — SE sees the report instantly
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Make src/ importable from web/backend/
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.db import get_db
from app.deps import CurrentUser, get_current_user
from app.models import Call, Scorecard, Insights, User

from src.analysis.scoring_engine import CallContext, score_call
from src.analysis.insights_extractor import extract_insights
from src.analysis.llm_client import LLMClient
from src.utils.transcript_validator import validate, ValidationResult


router = APIRouter()


class UploadResponse(BaseModel):
    accepted: bool
    call_id: Optional[str] = None
    validation: dict
    message: str
    redirect: Optional[str] = None


@router.post("/upload", response_model=UploadResponse)
async def upload_transcript(
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
    """Accept transcript, validate, run analysis, persist."""

    # 1. Read file if provided
    if file:
        contents = (await file.read()).decode("utf-8", errors="ignore")
        if file.filename and file.filename.lower().endswith((".vtt", ".srt")):
            contents = "\n".join(
                l for l in contents.splitlines()
                if l and "-->" not in l and not l.isdigit() and l != "WEBVTT"
            )
        transcript = contents

    # 2. Validate (reject notes/summaries). Also returns a normalized version —
    #    handles Avoma's "speaker on own line" format auto-converted to canonical.
    result: ValidationResult = validate(transcript)
    if not result.ok:
        return UploadResponse(
            accepted=False,
            validation={"kind": result.kind, "title": result.title,
                        "detail": result.detail, "metrics": result.metrics},
            message="Rejected — paste a real call transcript, not notes or a summary.",
        )
    # Use normalized text for everything downstream (scoring, insights, DB storage)
    transcript = result.normalized or transcript

    # 3. Look up SE user
    se = db.query(User).filter(User.email == user.email).first()
    if not se:
        raise HTTPException(404, "User not found")

    # 4. Run scoring + insights (sync for MVP — async later)
    call_id = f"call_{uuid.uuid4().hex[:12]}"
    ctx = CallContext(
        se_name=se.name,
        ae_name=ae_name or "",
        prospect_company=prospect_company,
        prospect_industry=prospect_industry or "",
        stated_use_case=stated_use_case or "",
        duration_min=duration_min or result.metrics.get("word_count", 0) // 150,  # ~150 wpm
        transcript=transcript,
        call_id=call_id,
        call_type=call_type,
    )

    llm = LLMClient(live=bool(os.getenv("ANTHROPIC_API_KEY")))
    try:
        scorecard_data = score_call(ctx, llm=llm)
        insights_data = extract_insights(ctx, llm=llm)
    except Exception as e:
        raise HTTPException(500, f"Analysis failed: {e}")

    # 5. Persist
    call = Call(
        call_id=call_id, se_id=se.id, se_name=se.name, ae_name=ae_name,
        prospect_company=prospect_company, prospect_industry=prospect_industry,
        stated_use_case=stated_use_case, duration_min=ctx.duration_min,
        call_type=call_type, source="upload",
        call_date=datetime.now(timezone.utc),
        transcript=transcript,
    )
    db.add(call); db.flush()

    db.add(Scorecard(
        call_id=call.id,
        weighted_final=scorecard_data["weighted_final"],
        industry_percentile=scorecard_data["industry_percentile"],
        per_criterion=scorecard_data["per_criterion_score"],
        sub_scores=scorecard_data["scores"],
        qualitative=scorecard_data["qualitative"],
        weights_applied=scorecard_data.get("weights_applied", {}),
        not_assessable=scorecard_data.get("not_assessable", {}),
        prompt_version=scorecard_data["prompt_version"],
    ))
    db.add(Insights(
        call_id=call.id,
        data=insights_data,
        prompt_version=insights_data.get("prompt_version", "v1"),
    ))
    db.commit()

    # 6. Best-effort push to Notion tracker (no-op if not configured)
    try:
        from app.services.notion_sync import push_call
        push_call(
            call_data={
                "prospect_company": prospect_company,
                "call_date": call.call_date,
                "call_type": call_type,
                "se_name": se.name,
                "ae_name": ae_name,
                "stated_use_case": stated_use_case,
            },
            insights=insights_data,
        )
    except Exception as e:
        print(f"[upload] notion push failed: {e}")

    return UploadResponse(
        accepted=True,
        call_id=call_id,
        validation={"kind": result.kind, "title": result.title, "metrics": result.metrics},
        message=f"Analyzed. Score: {scorecard_data['weighted_final']}/5 (P{scorecard_data['industry_percentile']}).",
        redirect=f"/call/{call_id}",
    )
