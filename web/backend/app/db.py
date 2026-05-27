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
    """Create tables (run on first deploy)."""
    from app import models  # noqa: F401  — register models
    Base.metadata.create_all(bind=engine)
