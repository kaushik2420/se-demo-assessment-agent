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
    # Analysis status — tracked across upload → background analysis lifecycle.
    # Values: 'pending' (just uploaded) | 'analyzing' (worker picked it up)
    #       | 'done' (scorecard + insights persisted) | 'failed' (caller can retry)
    analysis_status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    analysis_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    analysis_error: Mapped[Optional[str]] = mapped_column(Text)
    # Deal-anatomy enrichment — fields SEs fill in once they have the data.
    # Auto-fill where possible from insights; SEs override / add what's missing.
    deal_outcome: Mapped[Optional[str]] = mapped_column(String(16), index=True)  # open | won | lost | no_decision
    closed_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    go_live_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    discovery_source_override: Mapped[Optional[str]] = mapped_column(String(32))
    aha_moment_override: Mapped[Optional[str]] = mapped_column(Text)
    enrichment_notes: Mapped[Optional[str]] = mapped_column(Text)
    # HubSpot / CRM data — entered manually until we wire a real CRM sync.
    # deal_value is treated as a single currency for aggregations; the
    # currency code lets the UI display the right symbol per-row. SEs are
    # asked to enter USD-equivalent when they want totals to be meaningful.
    deal_value: Mapped[Optional[float]] = mapped_column(Float)
    deal_currency: Mapped[Optional[str]] = mapped_column(String(8), default="USD")
    deal_stage: Mapped[Optional[str]] = mapped_column(String(32), index=True)  # see DEAL_STAGES below
    crm_deal_url: Mapped[Optional[str]] = mapped_column(String(1024))
    expected_close_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    enrichment_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    enrichment_updated_by: Mapped[Optional[str]] = mapped_column(String(255))
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
    # Visual-only sub-criteria the model couldn't assess from transcript;
    # shape: {criterion_name: [sub_name, ...]}. Excluded from weighted_final.
    not_assessable: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
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


class TrackerRequest(Base):
    """A request tracked via the @SE Coach Slack tag."""
    __tablename__ = "tracker_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_ts: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    channel_id: Mapped[str] = mapped_column(String(64), index=True)
    channel_name: Mapped[Optional[str]] = mapped_column(String(255))
    slack_url: Mapped[Optional[str]] = mapped_column(String(512))

    requested_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    eta: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    se_email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    se_name: Mapped[Optional[str]] = mapped_column(String(255))
    engineer_name: Mapped[Optional[str]] = mapped_column(String(255))

    details: Mapped[Optional[str]] = mapped_column(Text)
    comments: Mapped[Optional[str]] = mapped_column(Text)  # timestamped accumulator

    # v2 fields — categorization extracted from the thread context
    product: Mapped[Optional[str]] = mapped_column(String(32))   # SurveySparrow | ThriveSparrow | SparrowDesk | Unknown
    kind: Mapped[Optional[str]] = mapped_column(String(16))      # issue | request
    l2_url: Mapped[Optional[str]] = mapped_column(String(1024))  # L2/Zendesk ticket link
    jira_url: Mapped[Optional[str]] = mapped_column(String(1024))

    status: Mapped[str] = mapped_column(String(16), default="open", index=True)  # open | closed

    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # daily-cron checkpoint
    reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class CoachingAction(Base):
    __tablename__ = "coaching_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    se_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    month: Mapped[str] = mapped_column(String(10))            # YYYY-MM
    action_text: Mapped[str] = mapped_column(Text)
    set_by: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | completed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
