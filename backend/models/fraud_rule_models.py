from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text

from database import Base


class FraudRule(Base):
    """Configurable policy rule used by the fraud scoring engine."""

    __tablename__ = "fraud_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    rule_code = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    organisation_id = Column(Integer, ForeignKey("organisations.id"), nullable=True, index=True)
    reason_code = Column(String(50), nullable=False, index=True)
    weight = Column(Float, nullable=False)
    field_name = Column(String(100), nullable=False, index=True)
    operator = Column(String(30), nullable=False, index=True)
    comparison_value = Column(JSON, nullable=True)
    secondary_field_name = Column(String(100), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    priority = Column(Integer, default=100, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
