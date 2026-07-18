"""CRUD operations for BIN (Bank Identification Number) lookups."""

from sqlalchemy.orm import Session

from models.bin_lookup_models import BINLookup


def get_bin_by_number(db: Session, bin_number: str) -> BINLookup | None:
    """Get BIN data by the BIN number (first 6-10 digits of card)."""
    # Normalize to first 6 digits for lookup
    normalized_bin = bin_number[:6] if len(bin_number) >= 6 else bin_number
    return db.query(BINLookup).filter(BINLookup.bin_number == normalized_bin).first()


def get_bin_by_card_number(db: Session, card_number: str) -> BINLookup | None:
    """Extract BIN from full card number and lookup."""
    # Extract first 6 digits as BIN
    bin_digits = card_number[:6] if len(card_number) >= 6 else card_number
    return get_bin_by_number(db, bin_digits)


def create_bin_lookup(
    db: Session,
    *,
    bin_number: str,
    card_brand: str | None = None,
    card_type: str | None = None,
    card_category: str | None = None,
    issuing_bank: str | None = None,
    issuing_country_code: str | None = None,
    issuing_country_name: str | None = None,
    is_prepaid: bool = False,
    is_commercial: bool = False,
    risk_score: int = 0,
) -> BINLookup:
    """Create a new BIN lookup entry."""
    # Normalize to 6 digits
    normalized_bin = bin_number[:6] if len(bin_number) >= 6 else bin_number
    
    bin_entry = BINLookup(
        bin_number=normalized_bin,
        card_brand=card_brand,
        card_type=card_type,
        card_category=card_category,
        issuing_bank=issuing_bank,
        issuing_country_code=issuing_country_code,
        issuing_country_name=issuing_country_name,
        is_prepaid=is_prepaid,
        is_commercial=is_commercial,
        risk_score=risk_score,
    )
    db.add(bin_entry)
    db.commit()
    db.refresh(bin_entry)
    return bin_entry


def list_bin_lookups(
    db: Session,
    *,
    issuing_country_code: str | None = None,
    card_brand: str | None = None,
    limit: int = 100,
) -> list[BINLookup]:
    """List BIN lookup entries with optional filtering."""
    query = db.query(BINLookup)
    if issuing_country_code:
        query = query.filter(BINLookup.issuing_country_code == issuing_country_code)
    if card_brand:
        query = query.filter(BINLookup.card_brand == card_brand)
    return query.limit(limit).all()


def get_high_risk_bins(db: Session, min_risk_score: int = 50, limit: int = 100) -> list[BINLookup]:
    """Get BIN entries with elevated risk scores."""
    return db.query(BINLookup).filter(
        BINLookup.risk_score >= min_risk_score
    ).limit(limit).all()
