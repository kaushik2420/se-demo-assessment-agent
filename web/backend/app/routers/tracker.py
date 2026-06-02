"""
Tracker UI endpoints — list, detail, edit, CSV export.

Permission model (v2):
  - Everyone (SE/manager/CEO/admin) sees all rows.
  - Only admin + manager can edit a row (re-assign SE, change kind/product/links/status/dates).
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, get_current_user, require_role
from app.models import TrackerRequest, User


router = APIRouter()


class TrackerItem(BaseModel):
    id: int
    requested_date: Optional[str]
    eta: Optional[str]
    se_name: Optional[str]
    se_email: Optional[str]
    engineer_name: Optional[str]
    details: Optional[str]
    comments: Optional[str]
    status: str
    slack_url: Optional[str]
    channel_name: Optional[str]
    # v2 fields
    product: Optional[str] = None       # SurveySparrow | ThriveSparrow | SparrowDesk | Unknown
    kind: Optional[str] = None          # issue | request
    l2_url: Optional[str] = None
    jira_url: Optional[str] = None
    last_synced_at: Optional[str] = None
    last_updated_at: str
    days_stale: int
    created_at: str


def _to_item(row: TrackerRequest) -> TrackerItem:
    now = datetime.now(tz=row.last_updated_at.tzinfo) if row.last_updated_at and row.last_updated_at.tzinfo else datetime.now(timezone.utc)
    return TrackerItem(
        id=row.id,
        requested_date=row.requested_date.isoformat() if row.requested_date else None,
        eta=row.eta.isoformat() if row.eta else None,
        se_name=row.se_name,
        se_email=row.se_email,
        engineer_name=row.engineer_name,
        details=row.details,
        comments=row.comments,
        status=row.status,
        slack_url=row.slack_url,
        channel_name=row.channel_name,
        product=row.product,
        kind=row.kind,
        l2_url=row.l2_url,
        jira_url=row.jira_url,
        last_synced_at=row.last_synced_at.isoformat() if row.last_synced_at else None,
        last_updated_at=row.last_updated_at.isoformat() if row.last_updated_at else now.isoformat(),
        days_stale=(now - row.last_updated_at).days if row.last_updated_at else 0,
        created_at=row.created_at.isoformat() if row.created_at else now.isoformat(),
    )


def _query(db: Session):
    # v2: every authenticated user sees every tracker row.
    return db.query(TrackerRequest).order_by(TrackerRequest.last_updated_at.desc())


@router.get("", response_model=List[TrackerItem])
def list_tracker(
    user: CurrentUser = Depends(get_current_user),  # auth required, but no filter applied
    db: Session = Depends(get_db),
):
    rows = _query(db).limit(500).all()
    return [_to_item(r) for r in rows]


@router.get("/ses", response_model=List[dict])
def list_ses(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Helper for the edit drawer's SE dropdown — returns every user with role=se."""
    rows = db.query(User).filter(User.role == "se").order_by(User.name).all()
    return [{"id": u.id, "name": u.name, "email": u.email} for u in rows]


@router.get("/{item_id}", response_model=TrackerItem)
def get_tracker_item(
    item_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(TrackerRequest).filter(TrackerRequest.id == item_id).first()
    if not row:
        raise HTTPException(404, "Not found")
    return _to_item(row)


# -------------------------------------------------------------------------
# Edit (admin + manager)
# -------------------------------------------------------------------------

class TrackerPatch(BaseModel):
    """All fields are optional — omitted keys are left unchanged."""
    se_email: Optional[str] = Field(default=None, description="Re-assign to this SE — must exist in users table")
    engineer_name: Optional[str] = None
    details: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern="^(open|closed)$")
    product: Optional[str] = Field(default=None, description="SurveySparrow | ThriveSparrow | SparrowDesk | Unknown")
    kind: Optional[str] = Field(default=None, pattern="^(issue|request|)$")
    l2_url: Optional[str] = None
    jira_url: Optional[str] = None
    requested_date: Optional[str] = None  # ISO date "YYYY-MM-DD"
    eta: Optional[str] = None             # ISO date "YYYY-MM-DD"


def _parse_iso_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        from datetime import date as _d
        d = _d.fromisoformat(str(s)[:10])
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    except Exception:
        return None


@router.patch("/{item_id}", response_model=TrackerItem,
              dependencies=[Depends(require_role("admin", "manager"))])
def update_tracker_item(
    item_id: int,
    patch: TrackerPatch,
    db: Session = Depends(get_db),
):
    """Edit a tracker row. Admin/manager only. Empty strings → null."""
    row = db.query(TrackerRequest).filter(TrackerRequest.id == item_id).first()
    if not row:
        raise HTTPException(404, "Not found")

    data = patch.model_dump(exclude_unset=True)

    # SE re-assignment — resolve email → name from User table (so dropdown
    # value stays in sync with the displayed name and we don't fall back to
    # stale Slack names)
    if "se_email" in data:
        new_email = (data["se_email"] or "").strip().lower() or None
        row.se_email = new_email
        if new_email:
            u = db.query(User).filter(User.email == new_email).first()
            row.se_name = u.name if u else row.se_name
        else:
            row.se_name = None

    for k in ("engineer_name", "details", "status", "product", "kind", "l2_url", "jira_url"):
        if k in data:
            v = data[k]
            if isinstance(v, str):
                v = v.strip() or None
            setattr(row, k, v)

    if "requested_date" in data:
        row.requested_date = _parse_iso_date(data["requested_date"])
    if "eta" in data:
        row.eta = _parse_iso_date(data["eta"])

    row.last_updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _to_item(row)


@router.get("/export.csv")
def export_csv(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download all tracker rows as CSV."""
    rows = _query(db).all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "Requested Date", "ETA", "Product", "Kind", "SE Name", "Engineer/Product Person",
        "Details of Request", "Comments", "L2 URL", "Jira URL", "Status",
        "Days Since Update", "Slack Channel", "Slack URL",
    ])
    for r in rows:
        days = ""
        if r.last_updated_at:
            now = datetime.now(tz=r.last_updated_at.tzinfo) if r.last_updated_at.tzinfo else datetime.now(timezone.utc)
            days = (now - r.last_updated_at).days
        w.writerow([
            r.requested_date.strftime("%Y-%m-%d") if r.requested_date else "",
            r.eta.strftime("%Y-%m-%d") if r.eta else "",
            r.product or "",
            r.kind or "",
            r.se_name or "",
            r.engineer_name or "",
            (r.details or "").replace("\n", " "),
            (r.comments or "").replace("\r", ""),
            r.l2_url or "",
            r.jira_url or "",
            r.status,
            days,
            r.channel_name or "",
            r.slack_url or "",
        ])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="se-coach-tracker-{datetime.utcnow():%Y%m%d}.csv"'},
    )
