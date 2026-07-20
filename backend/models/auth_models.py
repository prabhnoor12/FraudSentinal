from datetime import datetime, UTC

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String

from database import Base


class TokenBlacklist(Base):
    """Stores fingerprints of revoked authentication tokens."""

    __tablename__ = "token_blacklist"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(500), unique=True, index=True, nullable=False)
    reason = Column(String(255), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class RefreshToken(Base):
    """Stores fingerprints of refresh tokens associated with a user."""

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String(500), unique=True, index=True, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class PasswordResetToken(Base):
    """Stores fingerprints of password reset requests for a user."""

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String(255), unique=True, index=True, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class ServiceAccount(Base):
    """Represents a machine identity tied to an organisation."""

    __tablename__ = "service_accounts"

    id = Column(Integer, primary_key=True, index=True)
    organisation_id = Column(
        Integer, ForeignKey("organisations.id"), nullable=False, index=True
    )
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    scopes = Column(JSON, default=list, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_used_at = Column(DateTime, nullable=True)


class APIKey(Base):
    """Stores service-account API keys in encrypted/fingerprinted form."""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    service_account_id = Column(
        Integer, ForeignKey("service_accounts.id"), nullable=False, index=True
    )
    name = Column(String(100), nullable=False)
    key_prefix = Column(String(24), nullable=False, index=True)
    key_fingerprint = Column(String(255), unique=True, index=True, nullable=False)
    encrypted_secret = Column(String(1024), nullable=False)
    scopes = Column(JSON, default=list, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    rotation_due_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    last_used_at = Column(DateTime, nullable=True)


class IdempotencyRecord(Base):
    """Stores replay-safe responses for idempotent write requests."""

    __tablename__ = "idempotency_records"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), nullable=False, index=True)
    method = Column(String(10), nullable=False)
    path = Column(String(255), nullable=False)
    actor_type = Column(String(30), nullable=False)
    actor_id = Column(String(100), nullable=False)
    organisation_id = Column(Integer, nullable=True, index=True)
    request_fingerprint = Column(String(255), nullable=False)
    response_status_code = Column(Integer, nullable=False)
    response_body = Column(JSON, nullable=False)
    response_headers = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    expires_at = Column(DateTime, nullable=False)
