"""BIN (Bank Identification Number) lookup models for signal enrichment."""

from datetime import datetime, UTC

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from database import Base


class BINLookup(Base):
    """Stores BIN data for local lookup (no external API)."""

    __tablename__ = "bin_lookups"

    id = Column(Integer, primary_key=True, index=True)
    bin_number = Column(String(10), unique=True, nullable=False, index=True)
    card_brand = Column(String(50), nullable=True)  # visa, mastercard, amex, etc.
    card_type = Column(String(50), nullable=True)  # credit, debit, prepaid
    card_category = Column(String(100), nullable=True)  # classic, gold, platinum
    issuing_bank = Column(String(200), nullable=True)
    issuing_country_code = Column(String(2), nullable=True, index=True)
    issuing_country_name = Column(String(100), nullable=True)
    is_prepaid = Column(Boolean, default=False, nullable=False)
    is_commercial = Column(Boolean, default=False, nullable=False)
    risk_score = Column(Integer, default=0, nullable=False)  # Internal risk rating
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
