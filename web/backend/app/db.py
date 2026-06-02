"""SQLAlchemy session + engine setup. Postgres in prod, SQLite for local dev."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


def _db_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///./se_coach.db")
    # Render's free Postgres uses postgres:// — SQLAlchemy 2.x wants postgresql+psycopg://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(_db_url(), pool_pre_ping=True, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    """FastAPI dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create tables (run on first deploy). Also handles idempotent column adds
    for fields added after the initial schema (since SQLAlchemy's create_all
    only creates missing tables, not missing columns)."""
    from app import models  # noqa: F401  — register models
    from sqlalchemy import text
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        # Idempotent column adds — safe to run on every boot
        try:
            conn.execute(text(
                "ALTER TABLE calls ADD COLUMN IF NOT EXISTS external_id VARCHAR(128)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_calls_external_id ON calls(external_id)"
            ))
            # not_assessable was added in v2 prompts (Jun 2026) — visual sub-criteria
            # that Claude couldn't score from a transcript-only call.
            conn.execute(text(
                "ALTER TABLE scorecards ADD COLUMN IF NOT EXISTS not_assessable JSON"
            ))
            # Tracker v2 (Jun 2026) — product/kind categorization + L2/Jira URL columns
            # + last_synced_at for the daily thread refresh cron.
            conn.execute(text(
                "ALTER TABLE tracker_requests ADD COLUMN IF NOT EXISTS product VARCHAR(32)"
            ))
            conn.execute(text(
                "ALTER TABLE tracker_requests ADD COLUMN IF NOT EXISTS kind VARCHAR(16)"
            ))
            conn.execute(text(
                "ALTER TABLE tracker_requests ADD COLUMN IF NOT EXISTS l2_url VARCHAR(1024)"
            ))
            conn.execute(text(
                "ALTER TABLE tracker_requests ADD COLUMN IF NOT EXISTS jira_url VARCHAR(1024)"
            ))
            conn.execute(text(
                "ALTER TABLE tracker_requests ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMP WITH TIME ZONE"
            ))
            conn.commit()
        except Exception as e:
            print(f"[init_db] non-fatal: {e}")
