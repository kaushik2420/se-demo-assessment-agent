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
            # Analysis lifecycle tracking on calls — added so the SE sees actual
            # progress vs failure instead of an infinite 'Analyzing…' spinner
            # when the background worker crashes.
            conn.execute(text(
                "ALTER TABLE calls ADD COLUMN IF NOT EXISTS analysis_status VARCHAR(16) DEFAULT 'pending'"
            ))
            conn.execute(text(
                "ALTER TABLE calls ADD COLUMN IF NOT EXISTS analysis_started_at TIMESTAMP WITH TIME ZONE"
            ))
            conn.execute(text(
                "ALTER TABLE calls ADD COLUMN IF NOT EXISTS analysis_error TEXT"
            ))
            # Deal-anatomy enrichment columns (BU dashboard, Jun 2026 v4)
            for stmt in (
                "ALTER TABLE calls ADD COLUMN IF NOT EXISTS deal_outcome VARCHAR(16)",
                "ALTER TABLE calls ADD COLUMN IF NOT EXISTS closed_date TIMESTAMP WITH TIME ZONE",
                "ALTER TABLE calls ADD COLUMN IF NOT EXISTS go_live_date TIMESTAMP WITH TIME ZONE",
                "ALTER TABLE calls ADD COLUMN IF NOT EXISTS discovery_source_override VARCHAR(32)",
                "ALTER TABLE calls ADD COLUMN IF NOT EXISTS aha_moment_override TEXT",
                "ALTER TABLE calls ADD COLUMN IF NOT EXISTS enrichment_notes TEXT",
                "ALTER TABLE calls ADD COLUMN IF NOT EXISTS enrichment_updated_at TIMESTAMP WITH TIME ZONE",
                "ALTER TABLE calls ADD COLUMN IF NOT EXISTS enrichment_updated_by VARCHAR(255)",
                # HubSpot / CRM data — manual until proper sync
                "ALTER TABLE calls ADD COLUMN IF NOT EXISTS deal_value DOUBLE PRECISION",
                "ALTER TABLE calls ADD COLUMN IF NOT EXISTS deal_currency VARCHAR(8) DEFAULT 'USD'",
                "ALTER TABLE calls ADD COLUMN IF NOT EXISTS deal_stage VARCHAR(32)",
                "ALTER TABLE calls ADD COLUMN IF NOT EXISTS crm_deal_url VARCHAR(1024)",
                "ALTER TABLE calls ADD COLUMN IF NOT EXISTS expected_close_date TIMESTAMP WITH TIME ZONE",
                "CREATE INDEX IF NOT EXISTS idx_calls_deal_outcome ON calls(deal_outcome)",
                "CREATE INDEX IF NOT EXISTS idx_calls_deal_stage ON calls(deal_stage)",
            ):
                conn.execute(text(stmt))
            # Backfill existing rows to 'done' (they already have scorecards) —
            # SQL keeps it cheap and idempotent: anything with a scorecard is
            # done, anything without is failed (we can't recover their analysis
            # without re-running, so set to failed so the user can retry).
            conn.execute(text(
                "UPDATE calls SET analysis_status='done' "
                "WHERE analysis_status='pending' "
                "AND id IN (SELECT call_id FROM scorecards)"
            ))
            conn.execute(text(
                "UPDATE calls SET analysis_status='failed', "
                "analysis_error='Pre-existing call without scorecard — click Retry to analyze' "
                "WHERE analysis_status='pending' "
                "AND id NOT IN (SELECT call_id FROM scorecards)"
            ))
            conn.commit()
        except Exception as e:
            print(f"[init_db] non-fatal: {e}")
