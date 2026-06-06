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


class EnrichmentPatch(BaseModel):
    """Deal-anatomy fields SEs fill in once they have the data.
    All optional — omitted keys are left unchanged. Set a field to empty
    string to clear it."""
    deal_outcome: str | None = None       # "open" | "won" | "lost" | "no_decision"
    closed_date: str | None = None         # ISO "YYYY-MM-DD"
    go_live_date: str | None = None        # ISO "YYYY-MM-DD"
    discovery_source_override: str | None = None  # "referral" | "ae_outbound" | ... | ""
    aha_moment_override: str | None = None
    enrichment_notes: str | None = None
    # HubSpot / CRM fields
    deal_value: float | None = None
    deal_currency: str | None = None        # default USD
    deal_stage: str | None = None
    crm_deal_url: str | None = None
    expected_close_date: str | None = None


# Single source of truth for deal-stage values shown in dropdowns
DEAL_STAGES = (
    "prospecting", "qualified", "demo_scheduled", "demo_completed",
    "proposal", "negotiation", "verbal_commit", "closed_won",
    "closed_lost", "no_decision",
)


def _parse_iso_date_simple(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        from datetime import date as _d, datetime as _dt, timezone as _tz
        d = _d.fromisoformat(str(s)[:10])
        return _dt(d.year, d.month, d.day, tzinfo=_tz.utc)
    except Exception:
        return None


@router.patch("/{call_id}/enrichment", response_model=dict)
def patch_call_enrichment(
    call_id: str,
    patch: EnrichmentPatch,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update enrichment fields on a call. Permissions:
      - owning SE can edit their own call
      - manager / admin can edit any call
      - CEO / BU head can view (via /calls/{id}) but NOT edit (their job is
        consumption; SE / manager owns the data quality loop)
    """
    c = db.query(Call).filter(Call.call_id == call_id).first()
    if not c:
        raise HTTPException(404, "Call not found")

    if user.role == "se":
        u = db.query(User).filter(User.email == user.email).first()
        if not u or c.se_id != u.id:
            raise HTTPException(403, "Not your call")
    elif user.role not in ("manager", "admin"):
        raise HTTPException(403, "Read-only role — ask the SE or a manager to edit")

    data = patch.model_dump(exclude_unset=True)

    if "deal_outcome" in data:
        v = (data["deal_outcome"] or "").strip().lower() or None
        if v and v not in ("open", "won", "lost", "no_decision"):
            raise HTTPException(400, f"Invalid deal_outcome: {v!r}")
        c.deal_outcome = v
    if "closed_date" in data:
        c.closed_date = _parse_iso_date_simple(data["closed_date"])
    if "go_live_date" in data:
        c.go_live_date = _parse_iso_date_simple(data["go_live_date"])
    if "discovery_source_override" in data:
        v = (data["discovery_source_override"] or "").strip() or None
        c.discovery_source_override = v
    if "aha_moment_override" in data:
        v = (data["aha_moment_override"] or "").strip() or None
        c.aha_moment_override = v
    if "enrichment_notes" in data:
        v = (data["enrichment_notes"] or "").strip() or None
        c.enrichment_notes = v
    # HubSpot / CRM fields
    if "deal_value" in data:
        v = data["deal_value"]
        if v in ("", None):
            c.deal_value = None
        else:
            try:
                c.deal_value = float(v)
            except (TypeError, ValueError):
                raise HTTPException(400, "deal_value must be a number or empty")
    if "deal_currency" in data:
        v = (data["deal_currency"] or "").strip().upper() or None
        c.deal_currency = v or "USD"
    if "deal_stage" in data:
        v = (data["deal_stage"] or "").strip().lower() or None
        if v and v not in DEAL_STAGES:
            raise HTTPException(400, f"Invalid deal_stage: {v!r}")
        c.deal_stage = v
    if "crm_deal_url" in data:
        c.crm_deal_url = (data["crm_deal_url"] or "").strip() or None
    if "expected_close_date" in data:
        c.expected_close_date = _parse_iso_date_simple(data["expected_close_date"])

    from datetime import datetime as _dt, timezone as _tz
    c.enrichment_updated_at = _dt.now(_tz.utc)
    c.enrichment_updated_by = user.email
    db.commit()
    print(f"[calls] enrichment updated call_id={call_id} by={user.email!r} "
          f"fields={list(data.keys())}")
    return {
        "ok": True,
        "deal_outcome": c.deal_outcome,
        "closed_date": c.closed_date.isoformat() if c.closed_date else None,
        "go_live_date": c.go_live_date.isoformat() if c.go_live_date else None,
        "discovery_source_override": c.discovery_source_override,
        "aha_moment_override": c.aha_moment_override,
        "enrichment_notes": c.enrichment_notes,
        "deal_value": c.deal_value,
        "deal_currency": c.deal_currency,
        "deal_stage": c.deal_stage,
        "crm_deal_url": c.crm_deal_url,
        "expected_close_date": c.expected_close_date.isoformat() if c.expected_close_date else None,
        "enrichment_updated_at": c.enrichment_updated_at.isoformat(),
        "enrichment_updated_by": c.enrichment_updated_by,
    }


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
            # Deal-anatomy enrichment
            "deal_outcome": c.deal_outcome,
            "closed_date": c.closed_date.isoformat() if c.closed_date else None,
            "go_live_date": c.go_live_date.isoformat() if c.go_live_date else None,
            "discovery_source_override": c.discovery_source_override,
            "aha_moment_override": c.aha_moment_override,
            "enrichment_notes": c.enrichment_notes,
            "enrichment_updated_at": c.enrichment_updated_at.isoformat() if c.enrichment_updated_at else None,
            "enrichment_updated_by": c.enrichment_updated_by,
            # HubSpot / CRM
            "deal_value": c.deal_value,
            "deal_currency": c.deal_currency or "USD",
            "deal_stage": c.deal_stage,
            "crm_deal_url": c.crm_deal_url,
            "expected_close_date": c.expected_close_date.isoformat() if c.expected_close_date else None,
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
