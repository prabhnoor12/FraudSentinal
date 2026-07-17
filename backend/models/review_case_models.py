from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text

from database import Base


class ReviewCase(Base):
    __tablename__ = "review_cases"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False, index=True)
    decision_id = Column(Integer, ForeignKey("decisions.id"), nullable=False, index=True, unique=True)
    organisation_id = Column(Integer, ForeignKey("organisations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(30), default="open", nullable=False, index=True)
    resolution = Column(String(30), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    case_metadata = Column("metadata", JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    resolved_at = Column(DateTime, nullable=True, index=True)
