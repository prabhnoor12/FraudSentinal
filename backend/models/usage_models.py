from datetime import datetime, UTC

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from database import Base


class UsageEvent(Base):
    """Tracks user usage events that can later be billed."""

    __tablename__ = "usage_events"
    __table_args__ = (
        UniqueConstraint("id", "organisation_id", name="uq_usage_events_id_organisation"),
        ForeignKeyConstraint(
            ["user_id", "organisation_id"],
            ["users.id", "users.organisation_id"],
            name="fk_usage_events_user_org",
        ),
    )

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
    __table_args__ = (
        UniqueConstraint(
            "id", "organisation_id", name="uq_usage_summaries_id_organisation"
        ),
        ForeignKeyConstraint(
            ["user_id", "organisation_id"],
            ["users.id", "users.organisation_id"],
            name="fk_usage_summaries_user_org",
        ),
    )

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
