from datetime import datetime

from sqlalchemy.orm import Session

from models.device_fingerprint_models import DeviceFingerprint


def get_known_device_fingerprint(
    db: Session,
    *,
    organisation_id: int,
    user_id: int,
    customer_id: str | None,
    fingerprint: str,
) -> DeviceFingerprint | None:
    query = db.query(DeviceFingerprint).filter(
        DeviceFingerprint.organisation_id == organisation_id,
        DeviceFingerprint.user_id == user_id,
        DeviceFingerprint.fingerprint == fingerprint,
    )
    if customer_id is None:
        query = query.filter(DeviceFingerprint.customer_id.is_(None))
    else:
        query = query.filter(DeviceFingerprint.customer_id == customer_id)
    return query.first()


def list_known_device_fingerprints(
    db: Session,
    *,
    organisation_id: int,
    user_id: int,
    customer_id: str | None,
) -> list[DeviceFingerprint]:
    query = db.query(DeviceFingerprint).filter(
        DeviceFingerprint.organisation_id == organisation_id,
        DeviceFingerprint.user_id == user_id,
    )
    if customer_id is None:
        query = query.filter(DeviceFingerprint.customer_id.is_(None))
    else:
        query = query.filter(DeviceFingerprint.customer_id == customer_id)
    return query.order_by(DeviceFingerprint.last_seen_at.desc()).all()


def create_device_fingerprint(
    db: Session,
    *,
    commit: bool = True,
    **data,
) -> DeviceFingerprint:
    fingerprint = DeviceFingerprint(**data)
    db.add(fingerprint)
    if commit:
        db.commit()
        db.refresh(fingerprint)
    return fingerprint


def update_device_fingerprint(
    db: Session,
    fingerprint: DeviceFingerprint,
    *,
    commit: bool = True,
    confidence: float,
    components: dict,
    seen_at: datetime,
) -> DeviceFingerprint:
    fingerprint.confidence = confidence
    fingerprint.components = components
    fingerprint.last_seen_at = seen_at
    fingerprint.seen_count += 1
    if commit:
        db.commit()
        db.refresh(fingerprint)
    return fingerprint
