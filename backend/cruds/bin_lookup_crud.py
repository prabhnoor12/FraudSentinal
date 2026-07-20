"""CRUD operations for BIN (Bank Identification Number) lookups."""

from sqlalchemy import asc, desc, func
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
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> list[BINLookup]:
    """List BIN lookup entries with optional filtering."""
    query = db.query(BINLookup)
    if issuing_country_code:
        query = query.filter(BINLookup.issuing_country_code == issuing_country_code)
    if card_brand:
        query = query.filter(BINLookup.card_brand == card_brand)
    order_column = {
        "created_at": BINLookup.created_at,
        "updated_at": BINLookup.updated_at,
        "risk_score": BINLookup.risk_score,
        "bin_number": BINLookup.bin_number,
        "id": BINLookup.id,
    }.get(sort_by, BINLookup.created_at)
    order_func = asc if sort_dir == "asc" else desc
    return (
        query.order_by(order_func(order_column), desc(BINLookup.id))
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_high_risk_bins(
    db: Session,
    min_risk_score: int = 50,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "risk_score",
    sort_dir: str = "desc",
) -> list[BINLookup]:
    """Get BIN entries with elevated risk scores."""
    order_column = {
        "created_at": BINLookup.created_at,
        "updated_at": BINLookup.updated_at,
        "risk_score": BINLookup.risk_score,
        "bin_number": BINLookup.bin_number,
        "id": BINLookup.id,
    }.get(sort_by, BINLookup.risk_score)
    order_func = asc if sort_dir == "asc" else desc
    return (
        db.query(BINLookup)
        .filter(BINLookup.risk_score >= min_risk_score)
        .order_by(order_func(order_column), desc(BINLookup.id))
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_bin_lookups(
    db: Session,
    *,
    issuing_country_code: str | None = None,
    card_brand: str | None = None,
) -> int:
    query = db.query(func.count(BINLookup.id))
    if issuing_country_code:
        query = query.filter(BINLookup.issuing_country_code == issuing_country_code)
    if card_brand:
        query = query.filter(BINLookup.card_brand == card_brand)
    return query.scalar() or 0


def count_high_risk_bins(db: Session, min_risk_score: int = 50) -> int:
    return (
        db.query(func.count(BINLookup.id))
        .filter(BINLookup.risk_score >= min_risk_score)
        .scalar()
        or 0
    )
