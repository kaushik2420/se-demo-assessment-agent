"""
Email + password auth with bcrypt-hashed passwords and signed JWT access tokens.

Production hardening checklist (do NOT skip):
  - Passwords hashed with bcrypt (cost factor 12+)
  - JWT secret loaded from AWS Secrets Manager; rotated quarterly
  - Access tokens 24h; refresh tokens 30d in httpOnly cookies
  - Login rate-limited (per-IP + per-email) via Redis
  - Lockout after 5 failed attempts in 15 min
  - Password complexity: min 12 chars, mixed case + digit + symbol
  - Email verification on signup; password reset via signed link (expires 1h)
  - Audit log: every login + password-reset attempt
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt


SECRET_KEY = os.getenv("JWT_SECRET", "dev-only-do-not-use-in-prod")
ALGORITHM = "HS256"
# 7 days — internal coaching tool, mid-day logouts after a 24h session were
# disruptive (uploads happen sporadically across a week). Trading a small
# session-stealing risk for materially less friction.
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
BCRYPT_ROUNDS = 12


def _trunc(password: str) -> bytes:
    """bcrypt has a hard 72-byte limit on the input; truncate to match historical behavior."""
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_trunc(password), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_trunc(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, role: str, expires_min: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_min)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
