"""Common dependencies: current user, role guards."""

from __future__ import annotations

from typing import Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.auth import decode_token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

Role = Literal["se", "manager", "ceo", "admin"]


class CurrentUser:
    def __init__(self, email: str, role: Role):
        self.email = email
        self.role = role


def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired token",
            {"WWW-Authenticate": "Bearer"},
        )
    return CurrentUser(email=payload["sub"], role=payload.get("role", "se"))


def require_role(*allowed: Role):
    def _checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return user
    return _checker
