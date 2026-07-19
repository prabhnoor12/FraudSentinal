from datetime import datetime, UTC

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String

from database import Base


class UsageLimit(Base):
    """Defines usage limits for users or organisations."""

    __tablename__ = "usage_limits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    organisation_id = Column(
        Integer,
        ForeignKey("organisations.id"),
        nullable=True,
        index=True,
    )
    limit_type = Column(String(50), nullable=False, index=True)
    limit_value = Column(Float, default=0.0, nullable=False)
    period = Column(String(30), default="monthly", nullable=False)
    is_active = Column(String(10), default="true", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class LimitUsageRecord(Base):
    """Stores current usage against a configured limit."""

    __tablename__ = "limit_usage_records"

    id = Column(Integer, primary_key=True, index=True)
    usage_limit_id = Column(
        Integer,
        ForeignKey("usage_limits.id"),
        nullable=False,
        index=True,
    )
    current_usage = Column(Float, default=0.0, nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
