"""
Tracker UI endpoints — list, detail, CSV export.

Permission model:
  - SE: sees only their own tracker rows
  - Manager / Admin: sees all rows
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import CurrentUser, get_current_user
from app.models import TrackerRequest


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
    last_updated_at: str
    days_stale: int
    created_at: str


def _to_item(row: TrackerRequest) -> TrackerItem:
    now = datetime.now(tz=row.last_updated_at.tzinfo) if row.last_updated_at.tzinfo else datetime.utcnow()
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
        last_updated_at=row.last_updated_at.isoformat(),
        days_stale=(now - row.last_updated_at).days,
        created_at=row.created_at.isoformat(),
    )


def _query(db: Session, user: CurrentUser):
    q = db.query(TrackerRequest).order_by(TrackerRequest.last_updated_at.desc())
    if user.role == "se":
        q = q.filter(TrackerRequest.se_email == user.email)
    return q


@router.get("", response_model=List[TrackerItem])
def list_tracker(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = _query(db, user).limit(500).all()
    return [_to_item(r) for r in rows]


@router.get("/{item_id}", response_model=TrackerItem)
def get_tracker_item(
    item_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(TrackerRequest).filter(TrackerRequest.id == item_id).first()
    if not row:
        raise HTTPException(404, "Not found")
    if user.role == "se" and row.se_email != user.email:
        raise HTTPException(403, "Not yours")
    return _to_item(row)


@router.get("/export.csv")
def export_csv(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download all visible tracker rows as CSV (in the format from spec)."""
    rows = _query(db, user).all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "Requested Date", "ETA", "SE Name", "Engineer/Product Person",
        "Details of Request", "Comments", "Status", "Days Since Update",
        "Slack Channel", "Slack URL",
    ])
    for r in rows:
        w.writerow([
            r.requested_date.strftime("%Y-%m-%d") if r.requested_date else "",
            r.eta.strftime("%Y-%m-%d") if r.eta else "",
            r.se_name or "",
            r.engineer_name or "",
            (r.details or "").replace("\n", " "),
            (r.comments or "").replace("\r", ""),
            r.status,
            (datetime.now(tz=r.last_updated_at.tzinfo) - r.last_updated_at).days if r.last_updated_at else "",
            r.channel_name or "",
            r.slack_url or "",
        ])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="se-coach-tracker-{datetime.utcnow():%Y%m%d}.csv"'},
    )
