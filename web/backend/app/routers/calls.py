"""List + detail endpoints for calls (real DB)."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, get_current_user
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
        },
        scorecard=(c.scorecard and {
            "weighted_final": c.scorecard.weighted_final,
            "industry_percentile": c.scorecard.industry_percentile,
            "per_criterion_score": c.scorecard.per_criterion,
            "scores": c.scorecard.sub_scores,
            "qualitative": c.scorecard.qualitative,
            "weights_applied": c.scorecard.weights_applied,
            "prompt_version": c.scorecard.prompt_version,
        }),
        insights=(c.insights and c.insights.data),
    )
