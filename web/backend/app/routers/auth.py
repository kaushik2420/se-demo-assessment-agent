"""Login + current-user endpoints (real DB)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import create_access_token, verify_password
from app.db import get_db
from app.deps import CurrentUser, get_current_user
from app.models import User


router = APIRouter()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str


@router.post("/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username.lower(), User.is_active.is_(True)).first()
    if not user or not verify_password(form.password, user.pwd_hash):
        # Don't reveal whether email exists — generic 401
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    token = create_access_token(user.email, role=user.role)
    return TokenResponse(access_token=token, role=user.role, name=user.name)


class MeResponse(BaseModel):
    email: str
    role: str
    name: str


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email == user.email).first()
    if not u:
        raise HTTPException(404, "User not found")
    return MeResponse(email=u.email, role=u.role, name=u.name)
