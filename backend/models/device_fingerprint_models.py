from datetime import datetime, UTC

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String

from database import Base


class DeviceFingerprint(Base):
    """Known device fingerprints observed for customer transaction activity."""

    __tablename__ = "device_fingerprints"

    id = Column(Integer, primary_key=True, index=True)
    organisation_id = Column(
        Integer,
        ForeignKey("organisations.id"),
        nullable=False,
        index=True,
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    customer_id = Column(String(100), nullable=True, index=True)
    fingerprint = Column(String(64), nullable=False, index=True)
    confidence = Column(Float, default=0.0, nullable=False)
    components = Column(JSON, default=dict, nullable=False)
    first_seen_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    last_seen_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    seen_count = Column(Integer, default=1, nullable=False)
