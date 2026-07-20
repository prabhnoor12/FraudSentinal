"""CRUD operations for IP geolocation lookups."""

from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from models.ip_geolocation_models import IPGeolocation


def get_geolocation_by_ip(db: Session, ip_address: str) -> IPGeolocation | None:
    """Get geolocation data for an IP address.

    For IPv4, does a simple range check.
    For production, this should use integer IP representation for accurate range queries.
    """
    # Simple exact match for now
    # In production, convert IP to integer and do: ip_start_int <= ip_int <= ip_end_int
    return (
        db.query(IPGeolocation)
        .filter(
            IPGeolocation.ip_start <= ip_address, IPGeolocation.ip_end >= ip_address
        )
        .first()
    )


def create_ip_geolocation(
    db: Session,
    *,
    ip_start: str,
    ip_end: str,
    country_code: str,
    region: str | None = None,
    city: str | None = None,
    latitude: str | None = None,
    longitude: str | None = None,
    isp: str | None = None,
) -> IPGeolocation:
    """Create a new IP geolocation entry."""
    geo = IPGeolocation(
        ip_start=ip_start,
        ip_end=ip_end,
        country_code=country_code,
        region=region,
        city=city,
        latitude=latitude,
        longitude=longitude,
        isp=isp,
    )
    db.add(geo)
    db.commit()
    db.refresh(geo)
    return geo


def list_ip_geolocations(
    db: Session,
    *,
    country_code: str | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> list[IPGeolocation]:
    """List IP geolocation entries with optional filtering."""
    query = db.query(IPGeolocation)
    if country_code:
        query = query.filter(IPGeolocation.country_code == country_code)
    order_column = {
        "created_at": IPGeolocation.created_at,
        "updated_at": IPGeolocation.updated_at,
        "country_code": IPGeolocation.country_code,
        "id": IPGeolocation.id,
    }.get(sort_by, IPGeolocation.created_at)
    order_func = asc if sort_dir == "asc" else desc
    return (
        query.order_by(order_func(order_column), desc(IPGeolocation.id))
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_ip_geolocations(db: Session, *, country_code: str | None = None) -> int:
    query = db.query(func.count(IPGeolocation.id))
    if country_code:
        query = query.filter(IPGeolocation.country_code == country_code)
    return query.scalar() or 0
