from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from database import Base


class OrganisationSettings(Base):
    """Minimal settings for an organisation."""

    __tablename__ = "organisation_settings"

    id = Column(Integer, primary_key=True, index=True)
    organisation_id = Column(
        Integer,
        ForeignKey("organisations.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    currency = Column(String(10), default="USD", nullable=False)
    timezone = Column(String(50), default="UTC", nullable=False)
    
    # Fraud Engine Thresholds
    review_threshold = Column(Integer, default=40, nullable=False)
    decline_threshold = Column(Integer, default=70, nullable=False)
    
    enable_billing = Column(Boolean, default=True, nullable=False)
    enable_usage_tracking = Column(Boolean, default=True, nullable=False)
    notification_email = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
