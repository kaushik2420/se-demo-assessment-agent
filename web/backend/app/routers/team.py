"""
Team management endpoints — listing users and onboarding new ones from the UI.

Permission model:
  - Admin (you): can create any role (se, manager, ceo, admin)
  - Manager (Sushmitha): can create SEs only — can't elevate other users or onboard managers
  - SE / CEO: blocked from this surface

Returned password is shown ONCE in the response — there's no way to retrieve it
later. The UI must surface it immediately and let the user copy it before
navigating away.
"""

from __future__ import annotations

import os
import secrets
import string
from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.db import get_db
from app.deps import CurrentUser, get_current_user, require_role
from app.models import Call, User


router = APIRouter()


# ----------------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------------

Role = Literal["se", "manager", "ceo", "admin"]


class CreateUserRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    role: Role
    title: Optional[str] = Field(default=None, max_length=255)


class CreateUserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str
    one_time_password: str
    created_at: str


class UserListItem(BaseModel):
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    created_at: str
    slack_user_id: Optional[str] = None


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _gen_password(n: int = 14) -> str:
    """Generate a memorable-enough one-time password (no special chars that
    break in shell / autofill / Slack DMs)."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


# ----------------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------------

@router.get("/users", response_model=List[UserListItem],
            dependencies=[Depends(require_role("admin", "manager"))])
def list_users(db: Session = Depends(get_db)):
    """List all users in the system."""
    rows = db.query(User).order_by(User.created_at).all()
    return [
        UserListItem(
            id=u.id, email=u.email, name=u.name, role=u.role,
            is_active=u.is_active,
            created_at=u.created_at.isoformat(),
            slack_user_id=u.slack_user_id,
        )
        for u in rows
    ]


# ----------------------------------------------------------------------------
# Granola sync endpoints
# ----------------------------------------------------------------------------

@router.get("/granola/status",
            dependencies=[Depends(require_role("admin", "manager"))])
def granola_status():
    """Snapshot of Granola sync state for the admin UI."""
    from app.services.granola_sync import get_status
    return get_status()


@router.get("/notion/status",
            dependencies=[Depends(require_role("admin", "manager"))])
def notion_status():
    """Snapshot of Notion integration state for the admin UI."""
    from app.services.notion_sync import get_status
    return get_status()


@router.post("/notion/backfill",
             dependencies=[Depends(require_role("admin"))])
def notion_backfill(
    limit: int = Query(50, le=200, description="Max calls to backfill in one run"),
    db: Session = Depends(get_db),
):
    """
    One-shot backfill: push already-analyzed calls into Notion.
    Admin-only. Idempotent — dedupes on (Customer Name, Date), so safe to re-run.
    Processes up to `limit` calls (newest-first); call again to continue if more remain.
    """
    from app.services.notion_sync import push_call

    calls = (db.query(Call).filter(Call.scorecard.has())
               .order_by(Call.created_at.desc()).limit(limit).all())

    stats = {
        "total_considered": len(calls),
        "created": 0, "updated": 0, "skipped": 0, "errors": [],
        "details": [],
    }

    for c in calls:
        try:
            result = push_call(
                call_data={
                    "prospect_company": c.prospect_company,
                    "call_date": c.call_date or c.created_at,
                    "call_type": c.call_type,
                    "se_name": c.se_name,
                    "ae_name": c.ae_name,
                    "stated_use_case": c.stated_use_case,
                },
                insights=(c.insights.data if c.insights else None),
            )
            entry = {"call_id": c.call_id, "prospect": c.prospect_company,
                     "result": result.get("action") or "skipped",
                     "reason": result.get("reason")}
            stats["details"].append(entry)
            if not result.get("pushed"):
                stats["skipped"] += 1
                if result.get("reason"):
                    stats["errors"].append(f"{c.prospect_company}: {result['reason']}")
            elif result.get("action") == "created":
                stats["created"] += 1
            elif result.get("action") == "updated":
                stats["updated"] += 1
        except Exception as e:
            stats["errors"].append(f"{c.prospect_company}: {e}")

    return stats


@router.post("/users/refresh-slack-ids",
             dependencies=[Depends(require_role("admin"))])
def refresh_slack_ids(force: bool = False, db: Session = Depends(get_db)):
    """Backfill or refresh the cached Slack user ID for every user.

    By default only users with an empty slack_user_id are looked up — cheap
    and idempotent. Pass `?force=true` to re-resolve every user (e.g. after
    a workspace migration). Each user requires one Slack `users.lookupByEmail`
    call; rate limit on that endpoint is ~50/min, comfortable for any team
    size we care about."""
    from app.services.slack_tracker import _find_user_id_by_email

    if not os.getenv("SLACK_BOT_TOKEN"):
        return {"ok": False, "reason": "SLACK_BOT_TOKEN not set"}

    q = db.query(User)
    if not force:
        q = q.filter(User.slack_user_id.is_(None))
    candidates = q.all()

    stats: dict = {"checked": len(candidates), "resolved": 0,
                   "not_found": 0, "errors": [], "force": force}
    for u in candidates:
        try:
            uid = _find_user_id_by_email(u.email)
            if uid:
                u.slack_user_id = uid
                stats["resolved"] += 1
            else:
                stats["not_found"] += 1
                stats["errors"].append(f"{u.email}: no Slack user found")
        except Exception as e:
            stats["errors"].append(f"{u.email}: {e}")
    db.commit()
    print(f"[team.refresh_slack_ids] {stats}")
    return stats


@router.post("/granola/sync",
             dependencies=[Depends(require_role("admin", "manager"))])
def granola_sync_now(bg: BackgroundTasks):
    """Start a Granola sync in the background. Returns immediately. Poll
    /team/granola/status to see progress (`in_progress` flag) and the last
    completed run's stats (`last_result`)."""
    from app.services.granola_sync import run_sync, _is_in_progress
    if _is_in_progress():
        return {"status": "already_running",
                "message": "A sync is already running. Poll status for results."}
    bg.add_task(run_sync)
    return {"status": "started",
            "message": "Sync started in background. Refresh status to see progress."}


# ----------------------------------------------------------------------------
# Re-analysis (re-score + re-extract under current prompt versions)
# ----------------------------------------------------------------------------

@router.get("/reanalyze/status",
            dependencies=[Depends(require_role("admin"))])
def reanalyze_status():
    """Current prompt versions + last run stats + in-progress flag."""
    from app.services.reanalyze import get_status
    return get_status()


@router.post("/reanalyze",
             dependencies=[Depends(require_role("admin"))])
def reanalyze_now(
    bg: BackgroundTasks,
    mode: str = Query("outdated", pattern="^(outdated|all)$",
                      description="'outdated' (default) only re-runs calls on older prompts; 'all' forces every call"),
    limit: Optional[int] = Query(None, description="Cap on calls processed in this run"),
):
    """Kick off re-analysis as a background task. Admin only.
    Poll /team/reanalyze/status for progress and results."""
    from app.services.reanalyze import is_in_progress, run_reanalysis
    if is_in_progress():
        return {"status": "already_running",
                "message": "A re-analysis is already running. Poll status for results."}

    def _runner():
        try:
            run_reanalysis(mode=mode, limit=limit)
        except Exception as e:
            import traceback
            print(f"[reanalyze] CRASHED: {e}")
            traceback.print_exc()

    bg.add_task(_runner)
    return {"status": "started", "mode": mode, "limit": limit,
            "message": "Re-analysis started in background. Refresh status to see progress."}


# ----------------------------------------------------------------------------
# Users
# ----------------------------------------------------------------------------

@router.post("/users", response_model=CreateUserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    req: CreateUserRequest,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new user. Returns the one-time password — show it once, share it
    securely (DM, 1Password), and ask the user to change it on first login."""

    # Role guard
    if actor.role == "admin":
        pass  # admins can create any role
    elif actor.role == "manager":
        if req.role != "se":
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "Managers can only create SE accounts.")
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Only admins and managers can create users.")

    email = req.email.lower().strip()

    # Duplicate guard
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"A user with email {email} already exists.")

    pwd = _gen_password()
    # Best-effort Slack user-ID lookup at creation time so the first stale
    # reminder for this user can @-mention them without an extra API call.
    slack_user_id = None
    try:
        from app.services.slack_tracker import _find_user_id_by_email
        slack_user_id = _find_user_id_by_email(email)
        if slack_user_id:
            print(f"[team.create_user] resolved slack_user_id for {email}: {slack_user_id}")
        else:
            print(f"[team.create_user] no Slack user found for {email} — backfill later if needed")
    except Exception as e:
        print(f"[team.create_user] slack lookup failed for {email}: {e}")

    user = User(
        email=email,
        name=req.name.strip(),
        role=req.role,
        pwd_hash=hash_password(pwd),
        is_active=True,
        slack_user_id=slack_user_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return CreateUserResponse(
        id=user.id, email=user.email, name=user.name, role=user.role,
        one_time_password=pwd,
        created_at=user.created_at.isoformat(),
    )
