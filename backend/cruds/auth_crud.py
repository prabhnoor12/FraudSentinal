from sqlalchemy.orm import Session

from models.auth_models import (
    APIKey,
    IdempotencyRecord,
    PasswordResetToken,
    RefreshToken,
    ServiceAccount,
    TokenBlacklist,
)
from utils.security_utils import fingerprint_token


def blacklist_token(
    db: Session,
    *,
    token: str,
    reason: str | None = None,
    expires_at=None,
) -> TokenBlacklist:
    token_fingerprint = fingerprint_token(token)
    blacklisted = TokenBlacklist(
        token=token_fingerprint, reason=reason, expires_at=expires_at
    )
    db.add(blacklisted)
    db.commit()
    db.refresh(blacklisted)
    return blacklisted


def get_blacklisted_token(db: Session, token: str) -> TokenBlacklist | None:
    token_fingerprint = fingerprint_token(token)
    return (
        db.query(TokenBlacklist)
        .filter(TokenBlacklist.token == token_fingerprint)
        .first()
    )


def create_refresh_token(
    db: Session, *, user_id: int, token: str, expires_at
) -> RefreshToken:
    token_fingerprint = fingerprint_token(token)
    refresh_token = RefreshToken(
        user_id=user_id, token=token_fingerprint, expires_at=expires_at
    )
    db.add(refresh_token)
    db.commit()
    db.refresh(refresh_token)
    return refresh_token


def get_refresh_token(db: Session, token: str) -> RefreshToken | None:
    token_fingerprint = fingerprint_token(token)
    return (
        db.query(RefreshToken).filter(RefreshToken.token == token_fingerprint).first()
    )


def revoke_refresh_token(db: Session, refresh_token: RefreshToken) -> RefreshToken:
    refresh_token.revoked = True
    db.commit()
    db.refresh(refresh_token)
    return refresh_token


def create_password_reset_token(
    db: Session,
    *,
    user_id: int,
    token: str,
    expires_at,
) -> PasswordResetToken:
    token_fingerprint = fingerprint_token(token)
    reset_token = PasswordResetToken(
        user_id=user_id, token=token_fingerprint, expires_at=expires_at
    )
    db.add(reset_token)
    db.commit()
    db.refresh(reset_token)
    return reset_token


def get_password_reset_token(db: Session, token: str) -> PasswordResetToken | None:
    token_fingerprint = fingerprint_token(token)
    return (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token == token_fingerprint)
        .first()
    )


def mark_password_reset_token_used(
    db: Session, reset_token: PasswordResetToken
) -> PasswordResetToken:
    reset_token.used = True
    db.commit()
    db.refresh(reset_token)
    return reset_token


def create_service_account(db: Session, **data) -> ServiceAccount:
    service_account = ServiceAccount(**data)
    db.add(service_account)
    db.commit()
    db.refresh(service_account)
    return service_account


def list_service_accounts(
    db: Session, *, organisation_id: int | None = None
) -> list[ServiceAccount]:
    query = db.query(ServiceAccount)
    if organisation_id is not None:
        query = query.filter(ServiceAccount.organisation_id == organisation_id)
    return query.order_by(ServiceAccount.created_at.desc()).all()


def get_service_account_by_id(
    db: Session, service_account_id: int
) -> ServiceAccount | None:
    return (
        db.query(ServiceAccount)
        .filter(ServiceAccount.id == service_account_id)
        .first()
    )


def update_service_account(
    db: Session, service_account: ServiceAccount, **updates
) -> ServiceAccount:
    for field, value in updates.items():
        if value is not None:
            setattr(service_account, field, value)
    db.commit()
    db.refresh(service_account)
    return service_account


def create_api_key(db: Session, **data) -> APIKey:
    api_key = APIKey(**data)
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key


def list_api_keys(
    db: Session, *, service_account_id: int | None = None
) -> list[APIKey]:
    query = db.query(APIKey)
    if service_account_id is not None:
        query = query.filter(APIKey.service_account_id == service_account_id)
    return query.order_by(APIKey.created_at.desc()).all()


def get_api_key_by_id(db: Session, api_key_id: int) -> APIKey | None:
    return db.query(APIKey).filter(APIKey.id == api_key_id).first()


def get_api_key_by_secret(db: Session, raw_key: str) -> APIKey | None:
    fingerprint = fingerprint_token(raw_key)
    return db.query(APIKey).filter(APIKey.key_fingerprint == fingerprint).first()


def update_api_key(db: Session, api_key: APIKey, **updates) -> APIKey:
    for field, value in updates.items():
        if value is not None:
            setattr(api_key, field, value)
    db.commit()
    db.refresh(api_key)
    return api_key


def create_idempotency_record(db: Session, **data) -> IdempotencyRecord:
    record = IdempotencyRecord(**data)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_idempotency_record(
    db: Session,
    *,
    key: str,
    method: str,
    path: str,
    actor_type: str,
    actor_id: str,
) -> IdempotencyRecord | None:
    return (
        db.query(IdempotencyRecord)
        .filter(
            IdempotencyRecord.key == key,
            IdempotencyRecord.method == method,
            IdempotencyRecord.path == path,
            IdempotencyRecord.actor_type == actor_type,
            IdempotencyRecord.actor_id == actor_id,
        )
        .first()
    )
