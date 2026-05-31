"""SQLAlchemy models for the SE Coach portal."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, JSON, String, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="se")  # se | manager | ceo | admin
    pwd_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    calls: Mapped[list["Call"]] = relationship(back_populates="se", cascade="all, delete-orphan")


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)  # Granola meeting ID etc.
    se_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    se_name: Mapped[str] = mapped_column(String(255))  # denormalized for fast list queries
    ae_name: Mapped[Optional[str]] = mapped_column(String(255))
    prospect_company: Mapped[str] = mapped_column(String(255))
    prospect_industry: Mapped[Optional[str]] = mapped_column(String(255))
    stated_use_case: Mapped[Optional[str]] = mapped_column(Text)
    duration_min: Mapped[Optional[int]] = mapped_column(Integer)
    call_type: Mapped[str] = mapped_column(String(32), default="demo")
    source: Mapped[str] = mapped_column(String(32), default="upload")  # upload | granola
    call_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    transcript: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    se: Mapped[User] = relationship(back_populates="calls")
    scorecard: Mapped[Optional["Scorecard"]] = relationship(back_populates="call", uselist=False, cascade="all, delete-orphan")
    insights: Mapped[Optional["Insights"]] = relationship(back_populates="call", uselist=False, cascade="all, delete-orphan")


class Scorecard(Base):
    __tablename__ = "scorecards"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id"), unique=True, index=True)
    weighted_final: Mapped[float] = mapped_column(Float)
    industry_percentile: Mapped[int] = mapped_column(Integer)
    per_criterion: Mapped[dict] = mapped_column(JSON)         # {criterion: score}
    sub_scores: Mapped[dict] = mapped_column(JSON)            # nested scores with evidence
    qualitative: Mapped[dict] = mapped_column(JSON)           # strengths / gaps / coaching action
    weights_applied: Mapped[dict] = mapped_column(JSON)       # which call-type profile was used
    prompt_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    call: Mapped[Call] = relationship(back_populates="scorecard")


class Insights(Base):
    __tablename__ = "insights"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id"), unique=True, index=True)
    data: Mapped[dict] = mapped_column(JSON)                  # full 9-signal blob
    prompt_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    call: Mapped[Call] = relationship(back_populates="insights")


class CoachingAction(Base):
    __tablename__ = "coaching_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    se_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    month: Mapped[str] = mapped_column(String(10))            # YYYY-MM
    action_text: Mapped[str] = mapped_column(Text)
    set_by: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | completed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
