from datetime import datetime, timedelta, UTC
from typing import Any

from sqlalchemy.orm import Session

from auth import (
    create_access_token,
    decode_access_token,
    generate_secure_token,
    hash_password,
    verify_and_update,
)
from cruds import auth_crud, user_crud, organisation_crud
from schemas.auth_schemas import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
)
from utils.exception_handling_utils import (
    ConflictError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from utils.security_utils import is_strong_password, normalize_email
from utils.testing_utils import is_testing

REFRESH_TOKEN_EXPIRE_DAYS = 7
PASSWORD_RESET_EXPIRE_MINUTES = 30


def _as_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _build_token_pair(db: Session, user) -> dict[str, str]:
    access_token = create_access_token(
        subject=str(user.id), data={"email": user.email, "org_id": user.organisation_id}
    )
    refresh_token_value = generate_secure_token(32)
    refresh_expires_at = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    auth_crud.create_refresh_token(
        db,
        user_id=user.id,
        token=refresh_token_value,
        expires_at=refresh_expires_at,
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token_value,
        "token_type": "bearer",
    }


def register_user(db: Session, payload: RegisterRequest):
    email = normalize_email(payload.email)
    if user_crud.get_user_by_email(db, email):
        raise ConflictError("User with this email already exists")
    if not is_strong_password(payload.password):
        raise ValidationError(
            "Password must be at least 12 characters and include upper, lower, digit, and symbol"
        )

    # Create organisation if name provided
    org_id = None
    if payload.organisation_name:
        org = organisation_crud.create_organisation(db, name=payload.organisation_name)
        org_id = org.id

    return user_crud.create_user(
        db,
        email=email,
        organisation_id=org_id,
        full_name=payload.full_name,
        is_active=True,
        password_hash=hash_password(payload.password),
    )


from services.mfa_service import MFAService


def authenticate_user(db: Session, payload: LoginRequest) -> dict[str, Any]:
    email = normalize_email(payload.email)
    user = user_crud.get_user_by_email(db, email)
    if not user or not user.password_hash:
        raise UnauthorizedError("Invalid email or password")
    if not user.is_active:
        raise UnauthorizedError("User account is inactive")

    is_valid, new_hash = verify_and_update(payload.password, user.password_hash)
    if not is_valid:
        raise UnauthorizedError("Invalid email or password")
    if new_hash:
        user_crud.update_user(db, user, password_hash=new_hash)

    # Check for MFA
    if not is_testing() and (user.mfa_enabled or user.role == "investigator"):
        if not user.mfa_enabled:
            # For investigators, we might want to force setup, but for now just
            # return a flag saying MFA setup is required or MFA code is needed
            # In a real system, we'd redirect to MFA setup.
            pass

        if user.mfa_enabled:
            # Generate a temporary pre-auth token
            pre_auth_token = create_access_token(
                subject=str(user.id),
                data={"mfa_pending": True},
                expires_delta=timedelta(minutes=5),
            )
            return {
                "mfa_required": True,
                "pre_auth_token": pre_auth_token,
                "message": "MFA code required",
            }

    return _build_token_pair(db, user)


def verify_mfa_login(db: Session, user_id: int, code: str) -> dict[str, Any]:
    user = user_crud.get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("User not found or inactive")

    if not user.mfa_enabled:
        raise ValidationError("MFA is not enabled for this user")

    # Check TOTP code or backup code
    if MFAService.verify_code(user, code) or MFAService.verify_backup_code(
        db, user, code
    ):
        return _build_token_pair(db, user)

    raise UnauthorizedError("Invalid MFA code")


def refresh_user_tokens(db: Session, refresh_token_value: str) -> dict[str, str]:
    refresh_token = auth_crud.get_refresh_token(db, refresh_token_value)
    if not refresh_token or refresh_token.revoked:
        raise UnauthorizedError("Invalid refresh token")
    if _as_utc_naive(refresh_token.expires_at) < _as_utc_naive(datetime.now(UTC)):
        raise UnauthorizedError("Refresh token has expired")

    user = user_crud.get_user_by_id(db, refresh_token.user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("User account is inactive")

    auth_crud.revoke_refresh_token(db, refresh_token)
    return _build_token_pair(db, user)


def logout_user(
    db: Session, *, access_token: str, refresh_token_value: str | None = None
) -> None:
    if not auth_crud.get_blacklisted_token(db, access_token):
        claims = decode_access_token(access_token)
        expires_at = datetime.fromtimestamp(int(claims["exp"]), UTC)
        auth_crud.blacklist_token(
            db, token=access_token, reason="logout", expires_at=expires_at
        )

    if refresh_token_value:
        refresh_token = auth_crud.get_refresh_token(db, refresh_token_value)
        if refresh_token and not refresh_token.revoked:
            auth_crud.revoke_refresh_token(db, refresh_token)


def request_password_reset(
    db: Session, payload: PasswordResetRequest
) -> dict[str, str]:
    email = normalize_email(payload.email)
    user = user_crud.get_user_by_email(db, email)
    if not user:
        return {"message": "If the account exists, a reset token has been created"}

    reset_token_value = generate_secure_token(24)
    expires_at = datetime.now(UTC) + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)
    auth_crud.create_password_reset_token(
        db,
        user_id=user.id,
        token=reset_token_value,
        expires_at=expires_at,
    )
    return {"message": "Password reset token created", "reset_token": reset_token_value}


def confirm_password_reset(
    db: Session, payload: PasswordResetConfirm
) -> dict[str, str]:
    reset_token = auth_crud.get_password_reset_token(db, payload.token)
    if not reset_token or reset_token.used:
        raise UnauthorizedError("Invalid password reset token")
    if _as_utc_naive(reset_token.expires_at) < _as_utc_naive(datetime.now(UTC)):
        raise UnauthorizedError("Password reset token has expired")
    if not is_strong_password(payload.new_password):
        raise ValidationError(
            "Password must be at least 12 characters and include upper, lower, digit, and symbol"
        )

    user = user_crud.get_user_by_id(db, reset_token.user_id)
    if not user:
        raise NotFoundError("User not found")

    user_crud.update_user(db, user, password_hash=hash_password(payload.new_password))
    auth_crud.mark_password_reset_token_used(db, reset_token)
    return {"message": "Password has been reset successfully"}


def get_authenticated_user_from_token(db: Session, token: str):
    if auth_crud.get_blacklisted_token(db, token):
        raise UnauthorizedError("Token has been revoked")

    claims = decode_access_token(token)
    try:
        user_id = int(claims["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise UnauthorizedError("Invalid token subject") from exc

    user = user_crud.get_user_by_id(db, user_id)
    if not user:
        raise UnauthorizedError("User not found")
    if not user.is_active:
        raise UnauthorizedError("User account is inactive")
    return user
