from datetime import datetime, UTC

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text

from database import Base


class UsageEvent(Base):
    """Tracks user usage events that can later be billed."""

    __tablename__ = "usage_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    organisation_id = Column(
        Integer,
        ForeignKey("organisations.id"),
        nullable=False,
        index=True,
    )
    event_type = Column(String(100), nullable=False, index=True)
    units = Column(Float, default=1.0, nullable=False)
    unit_type = Column(String(50), default="request", nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(30), default="recorded", nullable=False)
    recorded_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    billed_at = Column(DateTime, nullable=True)


class UsageSummary(Base):
    """Stores monthly or period-based usage totals for a user or organisation."""

    __tablename__ = "usage_summaries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    organisation_id = Column(
        Integer,
        ForeignKey("organisations.id"),
        nullable=False,
        index=True,
    )
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    total_units = Column(Float, default=0.0, nullable=False)
    currency = Column(String(10), default="USD", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
