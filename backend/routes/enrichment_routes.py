"""Routes for IP Geolocation and BIN Lookup enrichment management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from auth import get_current_org_id
from database import get_db
from schemas.enrichment_schemas import BINLookupListResponse, IPGeolocationListResponse
from utils.pagination_utils import (
    build_paginated_payload,
    normalize_limit,
    normalize_offset,
    normalize_sort_dir,
)
from utils.security_utils import (
    normalize_card_number,
    normalize_country_code,
    normalize_ip_address,
    passes_luhn_check,
)

router = APIRouter(prefix="/enrichment", tags=["enrichment"])


@router.get("/health")
def enrichment_health_check() -> dict[str, str]:
    """Health check for enrichment services."""
    return {"status": "healthy", "service": "enrichment"}


# IP Geolocation Routes


@router.get("/ip-geolocation/lookup")
def lookup_ip_geolocation(
    ip_address: str = Query(..., description="IP address to lookup"),
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org_id),
) -> dict[str, Any]:
    """Lookup IP geolocation data for a given IP address."""
    from cruds.ip_geolocation_crud import get_geolocation_by_ip

    normalized_ip = normalize_ip_address(ip_address)
    geo = get_geolocation_by_ip(db, normalized_ip)
    if not geo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No geolocation data found for IP: {normalized_ip}",
        )

    return {
        "ip_address": normalized_ip,
        "country_code": geo.country_code,
        "region": geo.region,
        "city": geo.city,
        "latitude": geo.latitude,
        "longitude": geo.longitude,
        "isp": geo.isp,
        "data_source": "local",
    }


@router.get(
    "/ip-geolocation/list",
    response_model=IPGeolocationListResponse,
    summary="List IP geolocation records",
    description="Returns local IP geolocation catalogue entries using the standard v1 paginated list envelope.",
)
def list_ip_geolocations(
    request: Request,
    country_code: str | None = Query(None, description="Filter by country code"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org_id),
) -> dict[str, Any]:
    """List IP geolocation entries with optional filtering."""
    from cruds.ip_geolocation_crud import count_ip_geolocations, list_ip_geolocations

    normalized_offset = normalize_offset(offset)
    normalized_limit = normalize_limit(limit, default=100, maximum=1000)
    geos = list_ip_geolocations(
        db,
        country_code=country_code,
        offset=normalized_offset,
        limit=normalized_limit,
        sort_by=sort_by,
        sort_dir=normalize_sort_dir(sort_dir),
    )
    total = count_ip_geolocations(db, country_code=country_code)
    return build_paginated_payload(
        request=request,
        items=geos,
        total=total,
        limit=normalized_limit,
        offset=normalized_offset,
    )


# BIN Lookup Routes


@router.get("/bin-lookup/lookup")
def lookup_bin(
    bin_number: str | None = Query(
        None, description="BIN number (first 6 digits of card)"
    ),
    card_number: str | None = Query(
        None, description="Full card number (BIN will be extracted)"
    ),
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org_id),
) -> dict[str, Any]:
    """Lookup BIN data for a card."""
    from cruds.bin_lookup_crud import get_bin_by_card_number, get_bin_by_number

    if not bin_number and not card_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either bin_number or card_number must be provided",
        )

    normalized_bin_number = normalize_card_number(bin_number) if bin_number else None
    normalized_card_number = (
        normalize_card_number(card_number) if card_number else None
    )

    if normalized_bin_number is not None and len(normalized_bin_number) != 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="BIN number must be exactly 6 digits",
        )

    if normalized_card_number is not None and len(normalized_card_number) >= 12:
        if not passes_luhn_check(normalized_card_number):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Card number failed validation",
            )

    if bin_number:
        bin_data = get_bin_by_number(db, normalized_bin_number)
    else:
        bin_data = get_bin_by_card_number(db, normalized_card_number)

    if not bin_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No BIN data found for: {normalized_bin_number}"
                if normalized_bin_number
                else f"No BIN data found for: {normalized_card_number[:6] + '******'}"
            ),
        )

    return {
        "bin_number": bin_data.bin_number,
        "card_brand": bin_data.card_brand,
        "card_type": bin_data.card_type,
        "issuing_bank": bin_data.issuing_bank,
        "issuing_country_code": bin_data.issuing_country_code,
        "is_prepaid": bin_data.is_prepaid,
        "risk_score": bin_data.risk_score,
        "data_source": "local",
    }


@router.get(
    "/bin-lookup/list",
    response_model=BINLookupListResponse,
    summary="List BIN lookup records",
    description="Returns local BIN catalogue entries using the standard v1 paginated list envelope.",
)
def list_bin_lookups(
    request: Request,
    card_brand: str | None = Query(None, description="Filter by card brand"),
    issuing_country: str | None = Query(None, description="Filter by issuing country"),
    high_risk_only: bool = Query(False, description="Only show high-risk BINs"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org_id),
) -> dict[str, Any]:
    """List BIN lookup entries with optional filtering."""
    from cruds.bin_lookup_crud import (
        count_bin_lookups,
        count_high_risk_bins,
        get_high_risk_bins,
        list_bin_lookups,
    )

    normalized_offset = normalize_offset(offset)
    normalized_limit = normalize_limit(limit, default=100, maximum=1000)
    if high_risk_only:
        bins = get_high_risk_bins(
            db,
            offset=normalized_offset,
            limit=normalized_limit,
            sort_by=sort_by,
            sort_dir=normalize_sort_dir(sort_dir),
        )
        total = count_high_risk_bins(db)
    else:
        bins = list_bin_lookups(
            db,
            card_brand=card_brand,
            issuing_country_code=issuing_country,
            offset=normalized_offset,
            limit=normalized_limit,
            sort_by=sort_by,
            sort_dir=normalize_sort_dir(sort_dir),
        )
        total = count_bin_lookups(
            db,
            card_brand=card_brand,
            issuing_country_code=issuing_country,
        )

    return build_paginated_payload(
        request=request,
        items=bins,
        total=total,
        limit=normalized_limit,
        offset=normalized_offset,
    )


@router.post("/seed")
def seed_enrichment_data(
    confirm: bool = Query(..., description="Must be True to confirm seeding"),
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org_id),
) -> dict[str, Any]:
    """Seed the database with sample IP geolocation and BIN lookup data."""
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must pass confirm=true to seed data",
        )

    from scripts.seed_enrichment_data import main as seed_main

    try:
        result = seed_main(db)
        return {
            "success": True,
            "ip_geolocations": result.get("ip_geolocations", 0),
            "bin_lookups": result.get("bin_lookups", 0),
            "message": "Enrichment data seeded successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to seed data: {str(e)}",
        ) from e


@router.get("/signals/test")
def test_enrichment_signals(
    ip_address: str | None = Query(None, description="IP address to test"),
    card_number: str | None = Query(
        None, description="Card number to test (BIN will be extracted)"
    ),
    billing_country: str | None = Query(
        None, description="Billing country for mismatch detection"
    ),
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org_id),
) -> dict[str, Any]:
    """Test endpoint to verify enrichment signals are working."""
    from services.enrichment_service import (
        enrich_transaction_signals,
        get_enriched_transaction_data,
    )

    normalized_ip = normalize_ip_address(ip_address) if ip_address else None
    normalized_card_number = (
        normalize_card_number(card_number) if card_number else None
    )
    if normalized_card_number and len(normalized_card_number) >= 12:
        if not passes_luhn_check(normalized_card_number):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Card number failed validation",
            )
    normalized_billing_country = (
        normalize_country_code(billing_country) if billing_country else None
    )

    # Get enrichment signals
    signals = enrich_transaction_signals(
        db,
        ip_address=normalized_ip,
        card_number=normalized_card_number,
        billing_country=normalized_billing_country,
    )

    # Get flat enrichment data for rule engine
    enrichment_data = get_enriched_transaction_data(
        db,
        ip_address=normalized_ip,
        card_number=normalized_card_number,
        billing_country=normalized_billing_country,
    )

    return {
        "ip_address": normalized_ip,
        "card_number": (
            normalized_card_number[:6] + "******" if normalized_card_number else None
        ),
        "billing_country": normalized_billing_country,
        "signals": {
            "ip_geolocation_available": signals.ip_geo.geolocation_available,
            "ip_country": signals.ip_geo.ip_country_code
            if signals.ip_geo.geolocation_available
            else None,
            "ip_billing_country_mismatch": signals.ip_billing_country_mismatch,
            "bin_lookup_available": signals.bin_data.bin_available,
            "card_brand": signals.bin_data.card_brand
            if signals.bin_data.bin_available
            else None,
            "card_type": signals.bin_data.card_type
            if signals.bin_data.bin_available
            else None,
            "is_prepaid": signals.bin_data.is_prepaid
            if signals.bin_data.bin_available
            else None,
            "issuing_country": signals.bin_data.issuing_country_code
            if signals.bin_data.bin_available
            else None,
        },
        "enrichment_data_for_rules": enrichment_data,
        "data_source": "local",
    }
