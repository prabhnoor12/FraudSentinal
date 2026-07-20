from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from cruds import device_fingerprint_crud
from schemas.transaction_schemas import TransactionCreate


def _normalize_user_agent(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    lowered = user_agent.lower()
    browser = "unknown"
    os_name = "unknown"

    if "chrome" in lowered and "edg" not in lowered:
        browser = "chrome"
    elif "firefox" in lowered:
        browser = "firefox"
    elif "safari" in lowered and "chrome" not in lowered:
        browser = "safari"
    elif "edg" in lowered:
        browser = "edge"

    if "windows" in lowered:
        os_name = "windows"
    elif "mac" in lowered or "darwin" in lowered:
        os_name = "macos"
    elif "linux" in lowered:
        os_name = "linux"
    elif "android" in lowered:
        os_name = "android"
    elif "iphone" in lowered or "ios" in lowered:
        os_name = "ios"

    return f"{browser}:{os_name}"


def _extract_components(payload: TransactionCreate) -> dict:
    metadata = payload.metadata or {}
    components = {
        "device_id": payload.device_id,
        "user_agent": _normalize_user_agent(metadata.get("user_agent")),
        "language": metadata.get("accept_language"),
        "encoding": metadata.get("accept_encoding"),
        "screen": metadata.get("screen_resolution"),
        "timezone": metadata.get("timezone"),
        "ip_country_code": metadata.get("ip_country_code"),
    }
    return {key: value for key, value in components.items() if value not in (None, "", [])}


def build_device_fingerprint(payload: TransactionCreate) -> dict[str, object]:
    components = _extract_components(payload)
    if not components:
        return {
            "fingerprint": None,
            "components": {},
            "confidence": 0.0,
        }

    fingerprint_source = json.dumps(components, sort_keys=True)
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
    confidence = min(len(components) / 6, 1.0)
    return {
        "fingerprint": fingerprint,
        "components": components,
        "confidence": round(confidence, 2),
    }


def get_device_signals(db: Session, payload: TransactionCreate) -> dict[str, object]:
    fingerprint_data = build_device_fingerprint(payload)
    fingerprint = fingerprint_data["fingerprint"]
    if not fingerprint:
        return {
            "device_fingerprint": None,
            "device_fingerprint_confidence": 0.0,
            "known_devices_count": 0,
            "new_device": False,
        }

    known_devices = device_fingerprint_crud.list_known_device_fingerprints(
        db,
        organisation_id=payload.organisation_id,
        user_id=payload.user_id,
        customer_id=payload.customer_id,
    )
    known_fingerprints = {device.fingerprint for device in known_devices}
    known_devices_count = len(known_devices)
    new_device = bool(known_devices_count) and fingerprint not in known_fingerprints

    return {
        "device_fingerprint": fingerprint,
        "device_fingerprint_confidence": fingerprint_data["confidence"],
        "known_devices_count": known_devices_count,
        "new_device": new_device,
        "device_fingerprint_components": fingerprint_data["components"],
    }


def remember_device_fingerprint(
    db: Session,
    payload: TransactionCreate,
    *,
    commit: bool = True,
) -> None:
    fingerprint_data = build_device_fingerprint(payload)
    fingerprint = fingerprint_data["fingerprint"]
    if not fingerprint:
        return

    seen_at = datetime.now(UTC)
    existing = device_fingerprint_crud.get_known_device_fingerprint(
        db,
        organisation_id=payload.organisation_id,
        user_id=payload.user_id,
        customer_id=payload.customer_id,
        fingerprint=fingerprint,
    )
    if existing:
        device_fingerprint_crud.update_device_fingerprint(
            db,
            existing,
            commit=commit,
            confidence=float(fingerprint_data["confidence"]),
            components=dict(fingerprint_data["components"]),
            seen_at=seen_at,
        )
        return

    device_fingerprint_crud.create_device_fingerprint(
        db,
        commit=commit,
        organisation_id=payload.organisation_id,
        user_id=payload.user_id,
        customer_id=payload.customer_id,
        fingerprint=fingerprint,
        confidence=float(fingerprint_data["confidence"]),
        components=dict(fingerprint_data["components"]),
        first_seen_at=seen_at,
        last_seen_at=seen_at,
        seen_count=1,
    )
