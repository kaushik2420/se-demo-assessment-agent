"""
Transcript upload endpoint — async pipeline with explicit status tracking.

Flow:
  1. SE pastes text OR uploads .txt / .vtt file
  2. Validator runs synchronously (cheap — rejects notes/summaries)
  3. Call row created with analysis_status='pending'
  4. kickoff_analysis() flips status to 'analyzing' and spawns a daemon
     thread that runs scoring + insights (slow)
  5. Endpoint returns 200 with call_id + redirect URL (sub-second)
  6. Frontend redirects to /call/{id} which polls; status field tells it
     to show 'analyzing' / 'failed' / scorecard view
  7. If the worker dies, a 5-minute cron marks stuck rows 'failed' so the
     user can retry from the UI

Why threading.Thread (not FastAPI BackgroundTasks): the latter runs inside
the worker process and can be delayed/lost when the dyno sleeps or restarts
on Render. A daemon thread runs immediately and writes status as it goes —
the user always sees real progress or a real error.
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
from app.models import Call, User

from app.services.upload_analysis import kickoff_analysis
from src.analysis.llm_client import LLMClient
from src.utils.transcript_validator import validate, validate_with_llm_fallback, ValidationResult


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
    """Validate, persist Call row (status=pending), kick off analysis thread."""

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

    # 4. Persist the Call row immediately (status='pending')
    call_id = f"call_{uuid.uuid4().hex[:12]}"
    duration = duration_min or result.metrics.get("word_count", 0) // 150  # ~150 wpm
    call = Call(
        call_id=call_id, se_id=se.id, se_name=se.name, ae_name=ae_name,
        prospect_company=prospect_company, prospect_industry=prospect_industry,
        stated_use_case=stated_use_case, duration_min=duration,
        call_type=call_type, source="upload",
        call_date=datetime.now(timezone.utc),
        transcript=transcript,
        analysis_status="pending",
    )
    db.add(call); db.commit(); db.refresh(call)
    print(f"[upload] created call_id={call_id} se={se.email!r} prospect={prospect_company!r}")

    # 5. Kick off the analysis thread (flips status to 'analyzing' inside).
    kickoff_analysis(call.id, call.call_id)

    return UploadResponse(
        accepted=True,
        call_id=call_id,
        validation={"kind": result.kind, "title": result.title, "metrics": result.metrics},
        message="Transcript accepted. Analysis is running in the background.",
        redirect=f"/call/{call_id}",
    )
