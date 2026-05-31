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

import secrets
import string
from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.db import get_db
from app.deps import CurrentUser, get_current_user, require_role
from app.models import User


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


@router.post("/granola/sync",
             dependencies=[Depends(require_role("admin", "manager"))])
def granola_sync_now():
    """Manually trigger a Granola sync. Returns stats from the run."""
    from app.services.granola_sync import run_sync
    return run_sync()


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
    user = User(
        email=email,
        name=req.name.strip(),
        role=req.role,
        pwd_hash=hash_password(pwd),
        is_active=True,
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
