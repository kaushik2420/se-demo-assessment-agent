"""List + detail endpoints for calls (real DB)."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, get_current_user, require_role
from app.models import Call, Scorecard, Insights, User


router = APIRouter()


class CallSummary(BaseModel):
    call_id: str
    se_name: str
    prospect_company: str
    call_type: str
    cx_maturity: str | None = None        # legacy alias — same value as `maturity`
    maturity: str | None = None
    maturity_scope: str | None = None     # "CX" | "EX"
    product: str | None = None            # "SurveySparrow" | "ThriveSparrow" | "SparrowDesk"
    weighted_final: float | None = None
    date: str | None = None
    duration_min: int | None = None


class CallDetail(BaseModel):
    call: dict
    scorecard: dict | None
    insights: dict | None


@router.get("", response_model=List[CallSummary])
def list_calls(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List calls for the current user (SE = own only; manager/ceo/admin = all)."""
    q = db.query(Call).join(Call.scorecard, isouter=True).join(Call.insights, isouter=True)
    if user.role == "se":
        u = db.query(User).filter(User.email == user.email).first()
        if not u:
            return []
        q = q.filter(Call.se_id == u.id)
    q = q.order_by(Call.created_at.desc()).limit(200)

    out = []
    for c in q.all():
        ins = (c.insights.data if c.insights and c.insights.data else {}) or {}
        # New shape: maturity.category + maturity.scope + product.primary.
        # Old shape: cx_maturity.category (no scope/product).
        mat = ins.get("maturity") or {}
        category = mat.get("category") or (ins.get("cx_maturity", {}) or {}).get("category")
        scope = mat.get("scope") or ("CX" if (ins.get("cx_maturity") or {}).get("category") else None)
        product = (ins.get("product") or {}).get("primary")
        out.append(CallSummary(
            call_id=c.call_id,
            se_name=c.se_name,
            prospect_company=c.prospect_company,
            call_type=c.call_type,
            cx_maturity=category,
            maturity=category,
            maturity_scope=scope,
            product=product,
            weighted_final=c.scorecard.weighted_final if c.scorecard else None,
            date=c.call_date.isoformat() if c.call_date else c.created_at.isoformat(),
            duration_min=c.duration_min,
        ))
    return out


@router.delete("/{call_id}", status_code=204,
               dependencies=[Depends(require_role("admin", "manager"))])
def delete_call(
    call_id: str,
    db: Session = Depends(get_db),
):
    """Hard-delete a call and its scorecard + insights. Manager/admin only.
    Used to clean up test data. Scorecard + Insights cascade via the
    relationship config on Call."""
    c = db.query(Call).filter(Call.call_id == call_id).first()
    if not c:
        raise HTTPException(404, "Call not found")
    db.delete(c)
    db.commit()
    print(f"[calls] DELETED call_id={call_id} prospect={c.prospect_company!r} se={c.se_name!r}")
    return None


@router.post("/{call_id}/retry", response_model=dict)
def retry_call_analysis(
    call_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-trigger analysis for a failed (or stuck) call. The owning SE can
    retry their own calls; manager/admin can retry any call. Resets status
    to 'pending' then kicks off the analysis thread."""
    c = db.query(Call).filter(Call.call_id == call_id).first()
    if not c:
        raise HTTPException(404, "Call not found")
    if user.role == "se":
        u = db.query(User).filter(User.email == user.email).first()
        if not u or c.se_id != u.id:
            raise HTTPException(403, "Not your call")
    if c.analysis_status == "analyzing":
        return {"status": "already_running",
                "message": "Analysis is currently running — wait for it to complete or fail before retrying."}

    from app.services.upload_analysis import kickoff_analysis
    print(f"[calls] retry triggered for call_id={call_id} by {user.email!r} "
          f"(was status={c.analysis_status!r})")
    kickoff_analysis(c.id, c.call_id)
    return {"status": "started",
            "message": "Analysis restarted. Refresh the page in 30-90 seconds."}


@router.get("/{call_id}", response_model=CallDetail)
def get_call(
    call_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return full scorecard + insights for one call. SE can only see their own."""
    c = db.query(Call).filter(Call.call_id == call_id).first()
    if not c:
        raise HTTPException(404, "Call not found")
    if user.role == "se":
        u = db.query(User).filter(User.email == user.email).first()
        if not u or c.se_id != u.id:
            raise HTTPException(403, "Not your call")
    return CallDetail(
        call={
            "call_id": c.call_id, "se_name": c.se_name, "ae_name": c.ae_name,
            "prospect_company": c.prospect_company, "prospect_industry": c.prospect_industry,
            "stated_use_case": c.stated_use_case, "call_type": c.call_type,
            "duration_min": c.duration_min, "source": c.source,
            "date": (c.call_date or c.created_at).isoformat(),
            # Lifecycle fields — drive the UI between Analyzing / Failed / Done
            "analysis_status": c.analysis_status or "done",
            "analysis_started_at": c.analysis_started_at.isoformat() if c.analysis_started_at else None,
            "analysis_error": c.analysis_error,
        },
        scorecard=(c.scorecard and {
            "weighted_final": c.scorecard.weighted_final,
            "industry_percentile": c.scorecard.industry_percentile,
            "per_criterion_score": c.scorecard.per_criterion,
            "scores": c.scorecard.sub_scores,
            "qualitative": c.scorecard.qualitative,
            "weights_applied": c.scorecard.weights_applied,
            "not_assessable": c.scorecard.not_assessable or {},
            "prompt_version": c.scorecard.prompt_version,
        }),
        insights=(c.insights and c.insights.data),
    )
