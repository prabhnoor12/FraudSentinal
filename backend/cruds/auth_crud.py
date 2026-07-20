from sqlalchemy.orm import Session

from models.auth_models import PasswordResetToken, RefreshToken, TokenBlacklist
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
