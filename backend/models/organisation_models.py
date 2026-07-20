from datetime import datetime, UTC

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from database import Base


class Organisation(Base):
    """Basic organisation record used by billing and usage tracking."""

    __tablename__ = "organisations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    plan_code = Column(String(50), default="starter", nullable=False)
    subscription_status = Column(String(30), default="active", nullable=False)
    trial_ends_at = Column(DateTime, nullable=True)
    billing_provider = Column(String(30), nullable=True)
    billing_customer_external_id = Column(String(100), nullable=True, index=True)
    billing_subscription_external_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
