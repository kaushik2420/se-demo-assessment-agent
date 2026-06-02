"""
Tracker UI endpoints — list, detail, edit, CSV export.

Permission model (v2):
  - Everyone (SE/manager/CEO/admin) sees all rows.
  - Only admin + manager can edit a row (re-assign SE, change kind/product/links/status/dates).

Route ordering matters: static paths (/ses, /reextract/*, /export.csv) MUST be
declared before the catch-all /{item_id}, otherwise FastAPI's int converter
422s on non-numeric segments before they reach the right handler.
"""

from __future__ import annotations

import csv
import io
import traceback
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
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


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure tz-aware. SQLite (local dev) returns naive datetimes for
    DateTime(timezone=True) columns; we attribute UTC so arithmetic doesn't
    crash with a `naive vs aware` TypeError that would 500 the list endpoint."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _to_item(row: TrackerRequest) -> TrackerItem:
    last_upd = _aware(row.last_updated_at)
    created = _aware(row.created_at)
    requested = _aware(row.requested_date)
    eta = _aware(row.eta)
    last_synced = _aware(row.last_synced_at)
    now = datetime.now(timezone.utc)

    return TrackerItem(
        id=row.id,
        requested_date=requested.isoformat() if requested else None,
        eta=eta.isoformat() if eta else None,
        se_name=row.se_name,
        se_email=row.se_email,
        engineer_name=row.engineer_name,
        details=row.details,
        comments=row.comments,
        status=row.status or "open",
        slack_url=row.slack_url,
        channel_name=row.channel_name,
        product=row.product,
        kind=row.kind,
        l2_url=row.l2_url,
        jira_url=row.jira_url,
        last_synced_at=last_synced.isoformat() if last_synced else None,
        last_updated_at=last_upd.isoformat() if last_upd else now.isoformat(),
        days_stale=(now - last_upd).days if last_upd else 0,
        created_at=created.isoformat() if created else now.isoformat(),
    )


def _query(db: Session):
    # v2: every authenticated user sees every tracker row.
    return db.query(TrackerRequest).order_by(TrackerRequest.last_updated_at.desc())


# -------------------------------------------------------------------------
# List + dropdown helpers
# -------------------------------------------------------------------------

@router.get("", response_model=List[TrackerItem])
def list_tracker(
    user: CurrentUser = Depends(get_current_user),  # auth required, no row-level filter
    db: Session = Depends(get_db),
):
    """List all tracker rows. Defensive — if one row fails to serialize, log
    it and skip rather than 500ing the whole response."""
    print(f"[tracker.list] user={user.email!r} role={user.role!r}")
    out: list[TrackerItem] = []
    skipped: list[str] = []
    for r in _query(db).limit(500).all():
        try:
            out.append(_to_item(r))
        except Exception as e:
            skipped.append(f"row {r.id}: {type(e).__name__}: {e}")
            print(f"[tracker.list] skipped row #{r.id}: {e}")
            traceback.print_exc()
    if skipped:
        print(f"[tracker.list] returned {len(out)} rows, skipped {len(skipped)}")
    return out


@router.get("/ses", response_model=List[dict])
def list_ses(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Helper for the edit drawer's SE dropdown — returns every user with role=se."""
    rows = db.query(User).filter(User.role == "se").order_by(User.name).all()
    return [{"id": u.id, "name": u.name, "email": u.email} for u in rows]


# -------------------------------------------------------------------------
# Re-extract existing rows under the v2 prompt (admin) — declared BEFORE
# the /{item_id} catch-all so the int converter doesn't 422 these.
# -------------------------------------------------------------------------

@router.get("/reextract/status",
            dependencies=[Depends(require_role("admin"))])
def reextract_status():
    from app.services.tracker_reextract import get_status
    return get_status()


@router.post("/reextract",
             dependencies=[Depends(require_role("admin"))])
def reextract_now(
    bg: BackgroundTasks,
    mode: str = Query("outdated", pattern="^(outdated|all)$"),
    limit: Optional[int] = Query(None, description="Cap number of rows processed"),
):
    """Re-fetch the Slack thread for matching rows and run the v2 extraction.
    Backfill-only — preserves any manual edits. Admin only.
    Poll /tracker/reextract/status for progress and results."""
    from app.services.tracker_reextract import is_in_progress, run_reextract
    if is_in_progress():
        return {"status": "already_running",
                "message": "A re-extract is already running. Poll status for results."}

    def _runner():
        try:
            run_reextract(mode=mode, limit=limit)
        except Exception as e:
            print(f"[tracker.reextract] CRASHED: {e}")
            traceback.print_exc()

    bg.add_task(_runner)
    return {"status": "started", "mode": mode, "limit": limit,
            "message": "Re-extract started in background. Refresh status to see progress."}


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
        last_upd = _aware(r.last_updated_at)
        if last_upd:
            days = (datetime.now(timezone.utc) - last_upd).days
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


# -------------------------------------------------------------------------
# Catch-all by int id — declared LAST so the static paths above win
# -------------------------------------------------------------------------

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


@router.delete("/{item_id}", status_code=204,
               dependencies=[Depends(require_role("admin", "manager"))])
def delete_tracker_item(
    item_id: int,
    db: Session = Depends(get_db),
):
    """Hard-delete a tracker row. Manager/admin only. Used to clean up test data."""
    row = db.query(TrackerRequest).filter(TrackerRequest.id == item_id).first()
    if not row:
        raise HTTPException(404, "Not found")
    db.delete(row)
    db.commit()
    print(f"[tracker] DELETED row #{item_id} details={(row.details or '')[:60]!r}")
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
