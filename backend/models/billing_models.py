from datetime import datetime, UTC

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text

from database import Base


class BillingPlan(Base):
    """Represents a pricing plan that can be assigned to an organisation."""

    __tablename__ = "billing_plans"

    id = Column(Integer, primary_key=True, index=True)
    organisation_id = Column(
        Integer,
        ForeignKey("organisations.id"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False)
    price_per_unit = Column(Float, default=0.0, nullable=False)
    currency = Column(String(10), default="USD", nullable=False)
    billing_interval = Column(String(30), default="monthly", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class BillingRecord(Base):
    """Stores billed transactions for usage that was consumed by a user."""

    __tablename__ = "billing_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    organisation_id = Column(
        Integer,
        ForeignKey("organisations.id"),
        nullable=False,
        index=True,
    )
    usage_event_id = Column(
        Integer,
        ForeignKey("usage_events.id"),
        nullable=True,
        index=True,
    )
    amount = Column(Float, default=0.0, nullable=False)
    currency = Column(String(10), default="USD", nullable=False)
    status = Column(String(30), default="pending", nullable=False)
    invoice_id = Column(String(100), unique=True, nullable=True)
    description = Column(Text, nullable=True)
    billing_period_start = Column(DateTime, nullable=False)
    billing_period_end = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    billed_at = Column(DateTime, nullable=True)
