"""Signal enrichment service for fraud detection.

Provides IP geolocation and BIN lookup enrichment without external APIs.
Uses local lookup tables for zero-latency enrichment.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import time
from threading import RLock
from typing import Any

from sqlalchemy.orm import Session

from cruds import bin_lookup_crud, ip_geolocation_crud
from redis import RedisClient, get_redis_url


@dataclass
class IPGeoSignals:
    """IP Geolocation enrichment signals."""

    ip_country_code: str | None = None
    ip_region: str | None = None
    ip_city: str | None = None
    ip_latitude: str | None = None
    ip_longitude: str | None = None
    ip_isp: str | None = None
    geolocation_available: bool = False


@dataclass
class BINSignals:
    """BIN lookup enrichment signals."""

    bin_number: str | None = None
    card_brand: str | None = None
    card_type: str | None = None
    card_category: str | None = None
    issuing_bank: str | None = None
    issuing_country_code: str | None = None
    is_prepaid: bool = False
    is_commercial: bool = False
    bin_risk_score: int = 0
    bin_available: bool = False


@dataclass
class EnrichmentResult:
    """Combined enrichment result with derived fraud signals."""

    ip_geo: IPGeoSignals
    bin_data: BINSignals

    # Derived fraud signals
    ip_billing_country_mismatch: bool = False
    bin_issuing_country_mismatch: bool = False
    high_risk_bin: bool = False
    ip_geo_high_risk: bool = False

    # Raw enrichment data for storage
    raw_signals: dict[str, Any] | None = None


class EnrichmentLookupCache:
    """TTL cache with optional Redis backing for enrichment lookups."""

    def __init__(self) -> None:
        self._memory_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = RLock()
        self._redis_client: RedisClient | None = None
        self._redis_url: str | None = None

    def get(self, key: str) -> dict[str, Any] | None:
        now = time.monotonic()
        with self._lock:
            cached = self._memory_cache.get(key)
            if cached and cached[0] > now:
                return dict(cached[1])
            if cached:
                self._memory_cache.pop(key, None)

        redis_client = self._get_redis_client()
        if redis_client is None:
            return None

        try:
            payload = self._run_redis_call(redis_client.get(key))
        except Exception:
            return None

        if not payload:
            return None

        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        payload = dict(value)
        expires_at = time.monotonic() + ttl_seconds
        with self._lock:
            self._memory_cache[key] = (expires_at, payload)

        redis_client = self._get_redis_client()
        if redis_client is None:
            return

        try:
            self._run_redis_call(
                redis_client.set(
                    key,
                    json.dumps(payload, default=str, sort_keys=True),
                    ex=ttl_seconds,
                )
            )
        except Exception:
            return

    def reset(self) -> None:
        with self._lock:
            self._memory_cache.clear()

    def _get_redis_client(self) -> RedisClient | None:
        redis_url = get_redis_url()
        if not redis_url:
            return None

        with self._lock:
            if self._redis_client and self._redis_url == redis_url:
                return self._redis_client
            self._redis_url = redis_url
            self._redis_client = RedisClient(redis_url)
            return self._redis_client

    @staticmethod
    def _run_redis_call(coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        raise RuntimeError("Blocking Redis cache helper cannot run inside an active loop")


lookup_cache = EnrichmentLookupCache()
IP_GEO_CACHE_TTL_SECONDS = 60 * 60 * 24
BIN_CACHE_TTL_SECONDS = 60 * 60 * 24 * 7


def reset_enrichment_lookup_cache() -> None:
    lookup_cache.reset()


def enrich_transaction_signals(
    db: Session,
    *,
    ip_address: str | None = None,
    card_number: str | None = None,
    billing_country: str | None = None,
    user_id: str | None = None,
) -> EnrichmentResult:
    """Enrich transaction with IP geolocation and BIN lookup signals.

    Args:
        db: Database session
        ip_address: Client IP address
        card_number: Full or partial card number (BIN extracted automatically)
        billing_country: ISO country code from billing address
        user_id: User identifier for velocity tracking

    Returns:
        EnrichmentResult with all signals and derived fraud indicators
    """
    # IP Geolocation enrichment
    ip_geo = _enrich_ip_geolocation(db, ip_address)

    # BIN enrichment
    bin_data = _enrich_bin_data(db, card_number)

    # Build result with derived signals
    result = EnrichmentResult(
        ip_geo=ip_geo,
        bin_data=bin_data,
        ip_billing_country_mismatch=_check_country_mismatch(
            ip_geo.ip_country_code, billing_country
        ),
        bin_issuing_country_mismatch=_check_country_mismatch(
            bin_data.issuing_country_code, billing_country
        ),
        high_risk_bin=bin_data.bin_risk_score >= 50,
        ip_geo_high_risk=_is_high_risk_country(ip_geo.ip_country_code),
    )

    # Store raw signals for audit/debugging
    result.raw_signals = {
        "ip_geo": ip_geo.__dict__,
        "bin_data": bin_data.__dict__,
        "derived": {
            "ip_billing_country_mismatch": result.ip_billing_country_mismatch,
            "bin_issuing_country_mismatch": result.bin_issuing_country_mismatch,
            "high_risk_bin": result.high_risk_bin,
            "ip_geo_high_risk": result.ip_geo_high_risk,
        },
    }

    return result


def _enrich_ip_geolocation(db: Session, ip_address: str | None) -> IPGeoSignals:
    """Get IP geolocation signals."""
    if not ip_address:
        return IPGeoSignals(geolocation_available=False)

    cache_key = f"enrichment:ip_geo:{ip_address}"
    cached = lookup_cache.get(cache_key)
    if cached:
        return IPGeoSignals(**cached)

    try:
        geo = ip_geolocation_crud.get_geolocation_by_ip(db, ip_address)
        if geo:
            signals = IPGeoSignals(
                ip_country_code=geo.country_code,
                ip_region=geo.region,
                ip_city=geo.city,
                ip_latitude=geo.latitude,
                ip_longitude=geo.longitude,
                ip_isp=geo.isp,
                geolocation_available=True,
            )
            lookup_cache.set(cache_key, signals.__dict__, IP_GEO_CACHE_TTL_SECONDS)
            return signals
    except Exception:
        pass  # Fail gracefully if lookup fails

    return IPGeoSignals(geolocation_available=False)


def _enrich_bin_data(db: Session, card_number: str | None) -> BINSignals:
    """Get BIN lookup signals."""
    if not card_number or len(card_number) < 6:
        return BINSignals(bin_available=False)

    normalized_bin = card_number[:6]
    cache_key = f"enrichment:bin:{normalized_bin}"
    cached = lookup_cache.get(cache_key)
    if cached:
        return BINSignals(**cached)

    try:
        bin_data = bin_lookup_crud.get_bin_by_card_number(db, card_number)
        if bin_data:
            signals = BINSignals(
                bin_number=bin_data.bin_number,
                card_brand=bin_data.card_brand,
                card_type=bin_data.card_type,
                card_category=bin_data.card_category,
                issuing_bank=bin_data.issuing_bank,
                issuing_country_code=bin_data.issuing_country_code,
                is_prepaid=bin_data.is_prepaid,
                is_commercial=bin_data.is_commercial,
                bin_risk_score=bin_data.risk_score,
                bin_available=True,
            )
            lookup_cache.set(cache_key, signals.__dict__, BIN_CACHE_TTL_SECONDS)
            return signals
    except Exception:
        pass  # Fail gracefully if lookup fails

    return BINSignals(bin_available=False)


def _check_country_mismatch(detected: str | None, billing: str | None) -> bool:
    """Check if detected country mismatches billing country."""
    if not detected or not billing:
        return False  # Can't determine mismatch if either is missing
    return detected.upper() != billing.upper()


def _is_high_risk_country(country_code: str | None) -> bool:
    """Check if country is in high-risk list.

    This is a simplified check. In production, this should be:
    - Configurable per organization
    - Based on actual fraud rates
    - Updated regularly
    """
    if not country_code:
        return False

    # Example high-risk countries (this should be configurable)
    # This is a placeholder list - real implementation should be data-driven
    high_risk_countries = {
        # This would be populated based on actual fraud data
        # Leaving empty for now as this is organization-specific
    }

    return country_code.upper() in high_risk_countries


# Convenience function for the rule engine
def get_enriched_transaction_data(
    db: Session,
    ip_address: str | None,
    card_number: str | None,
    billing_country: str | None,
) -> dict:
    """Get all enrichment data as a flat dictionary for rule evaluation.

    This format is optimized for the fraud rule engine to easily reference
    enriched signals in rule conditions.
    """
    result = enrich_transaction_signals(
        db,
        ip_address=ip_address,
        card_number=card_number,
        billing_country=billing_country,
    )

    # Flatten to simple key-value pairs for rule engine
    return {
        # IP Geolocation
        "ip_country_code": result.ip_geo.ip_country_code,
        "ip_region": result.ip_geo.ip_region,
        "ip_city": result.ip_geo.ip_city,
        "ip_isp": result.ip_geo.ip_isp,
        "geolocation_available": result.ip_geo.geolocation_available,
        # BIN Data
        "card_brand": result.bin_data.card_brand,
        "card_type": result.bin_data.card_type,
        "card_category": result.bin_data.card_category,
        "issuing_bank": result.bin_data.issuing_bank,
        "issuing_country_code": result.bin_data.issuing_country_code,
        "is_prepaid": result.bin_data.is_prepaid,
        "is_commercial": result.bin_data.is_commercial,
        "bin_risk_score": result.bin_data.bin_risk_score,
        "bin_available": result.bin_data.bin_available,
        # Derived Fraud Signals
        "ip_billing_country_mismatch": result.ip_billing_country_mismatch,
        "bin_issuing_country_mismatch": result.bin_issuing_country_mismatch,
        "high_risk_bin": result.high_risk_bin,
        "ip_geo_high_risk": result.ip_geo_high_risk,
    }
