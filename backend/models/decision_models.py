from datetime import datetime, UTC

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)

from database import Base


class Decision(Base):
    """Stores the explainable fraud decision generated for a transaction."""

    __tablename__ = "decisions"
    __table_args__ = (
        UniqueConstraint("id", "organisation_id", name="uq_decisions_id_organisation"),
        ForeignKeyConstraint(
            ["transaction_id", "organisation_id"],
            ["transactions.id", "transactions.organisation_id"],
            name="fk_decisions_transaction_org",
        ),
        ForeignKeyConstraint(
            ["user_id", "organisation_id"],
            ["users.id", "users.organisation_id"],
            name="fk_decisions_user_org",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(
        Integer, ForeignKey("transactions.id"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    organisation_id = Column(
        Integer, ForeignKey("organisations.id"), nullable=False, index=True
    )
    risk_score = Column(Float, nullable=False, index=True)
    decision = Column(String(20), nullable=False, index=True)
    reason_codes = Column(JSON, default=list, nullable=False)
    scoring_snapshot = Column(JSON, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )
