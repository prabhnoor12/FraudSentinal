"""IP Geolocation lookup models for signal enrichment."""

from datetime import datetime, UTC

from sqlalchemy import Column, DateTime, Integer, String

from database import Base


class IPGeolocation(Base):
    """Stores IP geolocation data for local lookup (no external API)."""

    __tablename__ = "ip_geolocations"

    id = Column(Integer, primary_key=True, index=True)
    ip_start = Column(String(45), nullable=False, index=True)  # IPv4 or IPv6
    ip_end = Column(String(45), nullable=False, index=True)
    country_code = Column(String(2), nullable=False, index=True)
    region = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    latitude = Column(String(20), nullable=True)
    longitude = Column(String(20), nullable=True)
    isp = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
