from datetime import datetime, UTC

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String

from database import Base


class Transaction(Base):
    """Stores the normalized transaction payload evaluated by the fraud engine."""

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    organisation_id = Column(Integer, ForeignKey("organisations.id"), nullable=False, index=True)
    external_transaction_id = Column(String(100), nullable=True, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, index=True)
    payment_method = Column(String(50), nullable=False, index=True)
    channel = Column(String(50), default="api", nullable=False, index=True)
    customer_id = Column(String(100), nullable=True, index=True)
    customer_email = Column(String(255), nullable=True, index=True)
    billing_country = Column(String(2), nullable=True)
    shipping_country = Column(String(2), nullable=True)
    ip_address = Column(String(64), nullable=True)
    device_id = Column(String(255), nullable=True)
    account_age_days = Column(Integer, nullable=True)
    transactions_last_24h = Column(Integer, default=0, nullable=False)
    failed_attempts_last_24h = Column(Integer, default=0, nullable=False)
    transaction_metadata = Column("metadata", JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True)
