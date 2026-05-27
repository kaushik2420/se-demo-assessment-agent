"""
Admin CLI — for kaushik to manage users from the command line.

Usage (from web/backend/):
    python -m app.admin init-db
    python -m app.admin create-user <email> "<name>" <role> [password]
    python -m app.admin list-users
    python -m app.admin set-password <email> <new_password>
    python -m app.admin set-coaching-action <se_email> "<action text>"

Roles: se | manager | ceo | admin
If <password> is omitted on create-user, a random 16-char one is generated and printed once.
"""

from __future__ import annotations

import secrets
import string
import sys
from datetime import datetime, timezone

from app.auth import hash_password
from app.db import SessionLocal, init_db
from app.models import CoachingAction, User


def _gen_password(n: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(n))


def cmd_init_db():
    init_db()
    print("✓ Tables created")


def cmd_create_user(email: str, name: str, role: str, password: str | None = None):
    if role not in ("se", "manager", "ceo", "admin"):
        print(f"✗ Invalid role: {role}. Use se | manager | ceo | admin")
        sys.exit(1)
    pwd = password or _gen_password()
    with SessionLocal() as db:
        existing = db.query(User).filter(User.email == email.lower()).first()
        if existing:
            print(f"✗ User {email} already exists. Use set-password to update.")
            sys.exit(1)
        user = User(email=email.lower(), name=name, role=role, pwd_hash=hash_password(pwd))
        db.add(user)
        db.commit()
    print(f"✓ Created {role} user: {email}")
    print(f"  Name:     {name}")
    print(f"  Password: {pwd}   ← share this once via secure channel; user can change later")


def cmd_list_users():
    with SessionLocal() as db:
        users = db.query(User).order_by(User.created_at).all()
        if not users:
            print("(no users yet — run create-user)")
            return
        print(f"{'EMAIL':40s} {'NAME':25s} {'ROLE':10s} {'CREATED'}")
        print("-" * 90)
        for u in users:
            print(f"{u.email:40s} {u.name:25s} {u.role:10s} {u.created_at:%Y-%m-%d}")


def cmd_set_password(email: str, password: str):
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email.lower()).first()
        if not user:
            print(f"✗ No user with email {email}")
            sys.exit(1)
        user.pwd_hash = hash_password(password)
        db.commit()
    print(f"✓ Password updated for {email}")


def cmd_set_coaching_action(se_email: str, action_text: str):
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == se_email.lower(), User.role == "se").first()
        if not user:
            print(f"✗ No SE with email {se_email}")
            sys.exit(1)
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        existing = db.query(CoachingAction).filter(
            CoachingAction.se_id == user.id, CoachingAction.month == month
        ).first()
        if existing:
            existing.action_text = action_text
            existing.status = "open"
        else:
            db.add(CoachingAction(se_id=user.id, month=month, action_text=action_text,
                                  set_by="kaushik", status="open"))
        db.commit()
    print(f"✓ Coaching action set for {se_email} ({month})")


def _usage():
    print(__doc__)
    sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        _usage()
    cmd, *args = sys.argv[1:]
    try:
        if cmd == "init-db":
            cmd_init_db()
        elif cmd == "create-user":
            cmd_create_user(*args)
        elif cmd == "list-users":
            cmd_list_users()
        elif cmd == "set-password":
            cmd_set_password(*args)
        elif cmd == "set-coaching-action":
            cmd_set_coaching_action(*args)
        else:
            _usage()
    except TypeError as e:
        print(f"✗ Wrong arguments for {cmd}: {e}")
        _usage()
