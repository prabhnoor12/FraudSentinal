"""Routes for IP Geolocation and BIN Lookup enrichment management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from auth import get_current_org_id, get_db

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

    geo = get_geolocation_by_ip(db, ip_address)
    if not geo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No geolocation data found for IP: {ip_address}",
        )

    return {
        "ip_address": ip_address,
        "country_code": geo.country_code,
        "region": geo.region,
        "city": geo.city,
        "latitude": geo.latitude,
        "longitude": geo.longitude,
        "isp": geo.isp,
        "data_source": "local",
    }


@router.get("/ip-geolocation/list")
def list_ip_geolocations(
    country_code: str | None = Query(None, description="Filter by country code"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org_id),
) -> dict[str, Any]:
    """List IP geolocation entries with optional filtering."""
    from cruds.ip_geolocation_crud import list_ip_geolocations

    geos = list_ip_geolocations(db, country_code=country_code, limit=limit)

    return {
        "total": len(geos),
        "country_filter": country_code,
        "data": [
            {
                "id": g.id,
                "ip_start": g.ip_start,
                "ip_end": g.ip_end,
                "country_code": g.country_code,
                "region": g.region,
                "city": g.city,
            }
            for g in geos
        ],
    }


# BIN Lookup Routes


@router.get("/bin-lookup/lookup")
def lookup_bin(
    bin_number: str | None = Query(None, description="BIN number (first 6 digits of card)"),
    card_number: str | None = Query(None, description="Full card number (BIN will be extracted)"),
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

    if bin_number:
        bin_data = get_bin_by_number(db, bin_number)
    else:
        bin_data = get_bin_by_card_number(db, card_number)

    if not bin_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No BIN data found for: {bin_number or card_number[:6] + '******'}",
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


@router.get("/bin-lookup/list")
def list_bin_lookups(
    card_brand: str | None = Query(None, description="Filter by card brand"),
    issuing_country: str | None = Query(None, description="Filter by issuing country"),
    high_risk_only: bool = Query(False, description="Only show high-risk BINs"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org_id),
) -> dict[str, Any]:
    """List BIN lookup entries with optional filtering."""
    from cruds.bin_lookup_crud import get_high_risk_bins, list_bin_lookups

    if high_risk_only:
        bins = get_high_risk_bins(db, limit=limit)
    else:
        bins = list_bin_lookups(
            db,
            card_brand=card_brand,
            issuing_country=issuing_country,
            limit=limit,
        )

    return {
        "total": len(bins),
        "filters": {
            "card_brand": card_brand,
            "issuing_country": issuing_country,
            "high_risk_only": high_risk_only,
        },
        "data": [
            {
                "id": b.id,
                "bin_number": b.bin_number,
                "card_brand": b.card_brand,
                "card_type": b.card_type,
                "issuing_bank": b.issuing_bank,
                "issuing_country_code": b.issuing_country_code,
                "is_prepaid": b.is_prepaid,
                "risk_score": b.risk_score,
            }
            for b in bins
        ],
    }


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
    card_number: str | None = Query(None, description="Card number to test (BIN will be extracted)"),
    billing_country: str | None = Query(None, description="Billing country for mismatch detection"),
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org_id),
) -> dict[str, Any]:
    """Test endpoint to verify enrichment signals are working."""
    from services.enrichment_service import (
        enrich_transaction_signals,
        get_enriched_transaction_data,
    )

    # Get enrichment signals
    signals = enrich_transaction_signals(
        db,
        ip_address=ip_address,
        card_number=card_number,
        billing_country=billing_country,
    )

    # Get flat enrichment data for rule engine
    enrichment_data = get_enriched_transaction_data(
        db,
        ip_address=ip_address,
        card_number=card_number,
        billing_country=billing_country,
    )

    return {
        "ip_address": ip_address,
        "card_number": card_number[:6] + "******" if card_number else None,
        "billing_country": billing_country,
        "signals": {
            "ip_geolocation_available": signals.ip_geolocation.available,
            "ip_country": signals.ip_geolocation.country_code if signals.ip_geolocation.available else None,
            "ip_billing_country_mismatch": signals.ip_geolocation.country_mismatch if signals.ip_geolocation.available else None,
            "bin_lookup_available": signals.bin_data.available,
            "card_brand": signals.bin_data.card_brand if signals.bin_lookup.available else None,
            "card_type": signals.bin_data.card_type if signals.bin_lookup.available else None,
            "is_prepaid": signals.bin_data.is_prepaid if signals.bin_lookup.available else None,
            "issuing_country": signals.bin_data.issuing_country if signals.bin_lookup.available else None,
        },
        "enrichment_data_for_rules": enrichment_data,
        "data_source": "local",
    }
