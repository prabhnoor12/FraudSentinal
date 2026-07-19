from datetime import datetime, UTC

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String

from database import Base


class RiskSignal(Base):
    __tablename__ = "risk_signals"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(
        Integer, ForeignKey("transactions.id"), nullable=False, index=True
    )
    decision_id = Column(
        Integer, ForeignKey("decisions.id"), nullable=False, index=True
    )
    organisation_id = Column(
        Integer, ForeignKey("organisations.id"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    rule_id = Column(Integer, ForeignKey("fraud_rules.id"), nullable=True, index=True)
    rule_code = Column(String(100), nullable=False, index=True)
    reason_code = Column(String(50), nullable=False, index=True)
    weight = Column(Float, nullable=False)
    details = Column(JSON, default=dict, nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )
