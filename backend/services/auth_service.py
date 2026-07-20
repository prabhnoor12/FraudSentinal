from datetime import datetime, timedelta, UTC
import os
from typing import Any

from cryptography.fernet import Fernet
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
    APIKeyCreateRequest,
    APIKeyRotateRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    ServiceAccountCreate,
)
from utils.exception_handling_utils import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from utils.security_utils import (
    derive_fernet_key,
    fingerprint_token,
    generate_api_key,
    is_strong_password,
    mask_sensitive_data,
    normalize_email,
)
from utils.testing_utils import is_testing

REFRESH_TOKEN_EXPIRE_DAYS = 7
PASSWORD_RESET_EXPIRE_MINUTES = 30
API_KEY_DEFAULT_EXPIRE_DAYS = 90
API_KEY_ROTATION_DAYS = 60
API_KEY_EXPIRY_ALERT_DAYS = 14


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


def _get_api_key_cipher() -> Fernet:
    secret_key = os.getenv("SECRET_KEY") or "fraudsentinel-dev-secret-key"
    return Fernet(derive_fernet_key(secret_key).encode("ascii"))


def _encrypt_api_key(raw_key: str) -> str:
    return _get_api_key_cipher().encrypt(raw_key.encode("utf-8")).decode("utf-8")


def _normalize_scopes(scopes: list[str]) -> list[str]:
    cleaned = sorted({scope.strip() for scope in scopes if scope and scope.strip()})
    if not cleaned:
        raise ValidationError("At least one API scope is required")
    return cleaned


def _validate_user_can_manage_org(user, organisation_id: int) -> None:
    if user.organisation_id != organisation_id and user.role != "admin":
        raise ForbiddenError("You cannot manage service accounts for this organisation")


def _ensure_service_account_in_org(service_account, organisation_id: int) -> None:
    if service_account.organisation_id != organisation_id:
        raise NotFoundError("Service account not found")


def _build_api_key_response(api_key, *, raw_key: str | None = None) -> dict[str, Any]:
    return {
        "id": api_key.id,
        "name": api_key.name,
        "key_prefix": api_key.key_prefix,
        "masked_key": mask_sensitive_data(raw_key or api_key.key_prefix, keep=4),
        "raw_key": raw_key,
        "scopes": api_key.scopes or [],
        "is_active": api_key.is_active,
        "expires_at": api_key.expires_at,
        "rotation_due_at": api_key.rotation_due_at,
        "revoked_at": api_key.revoked_at,
        "created_at": api_key.created_at,
        "last_used_at": api_key.last_used_at,
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

    response = {"message": "If the account exists, a reset token has been created"}
    if is_testing():
        response["reset_token"] = reset_token_value
    return response


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


def create_service_account_service(
    db: Session, actor_user, payload: ServiceAccountCreate
):
    if not organisation_crud.get_organisation_by_id(db, payload.organisation_id):
        raise NotFoundError("Organisation not found")
    _validate_user_can_manage_org(actor_user, payload.organisation_id)
    return auth_crud.create_service_account(
        db,
        organisation_id=payload.organisation_id,
        created_by_user_id=actor_user.id,
        name=payload.name,
        description=payload.description,
        scopes=_normalize_scopes(payload.scopes),
        expires_at=payload.expires_at,
    )


def list_service_accounts_service(db: Session, actor_user):
    organisation_id = None if actor_user.role == "admin" else actor_user.organisation_id
    return auth_crud.list_service_accounts(db, organisation_id=organisation_id)


def create_service_account_api_key_service(
    db: Session,
    actor_user,
    service_account_id: int,
    payload: APIKeyCreateRequest,
) -> dict[str, Any]:
    service_account = auth_crud.get_service_account_by_id(db, service_account_id)
    if not service_account:
        raise NotFoundError("Service account not found")

    _validate_user_can_manage_org(actor_user, service_account.organisation_id)
    scopes = _normalize_scopes(payload.scopes or service_account.scopes or [])
    raw_key = generate_api_key(prefix="fs_live_", length=24)
    expires_at = payload.expires_at or (
        datetime.now(UTC) + timedelta(days=API_KEY_DEFAULT_EXPIRE_DAYS)
    )
    rotation_due_at = datetime.now(UTC) + timedelta(days=API_KEY_ROTATION_DAYS)
    api_key = auth_crud.create_api_key(
        db,
        service_account_id=service_account.id,
        name=payload.name,
        key_prefix=raw_key[:16],
        key_fingerprint=fingerprint_token(raw_key),
        encrypted_secret=_encrypt_api_key(raw_key),
        scopes=scopes,
        expires_at=expires_at,
        rotation_due_at=rotation_due_at,
    )
    return _build_api_key_response(api_key, raw_key=raw_key)


def list_service_account_api_keys_service(
    db: Session, actor_user, service_account_id: int
) -> list[dict[str, Any]]:
    service_account = auth_crud.get_service_account_by_id(db, service_account_id)
    if not service_account:
        raise NotFoundError("Service account not found")
    _validate_user_can_manage_org(actor_user, service_account.organisation_id)
    api_keys = auth_crud.list_api_keys(db, service_account_id=service_account.id)
    return [_build_api_key_response(api_key) for api_key in api_keys]


def rotate_service_account_api_key_service(
    db: Session,
    actor_user,
    service_account_id: int,
    api_key_id: int,
    payload: APIKeyRotateRequest,
) -> dict[str, Any]:
    service_account = auth_crud.get_service_account_by_id(db, service_account_id)
    if not service_account:
        raise NotFoundError("Service account not found")
    _validate_user_can_manage_org(actor_user, service_account.organisation_id)

    existing_key = auth_crud.get_api_key_by_id(db, api_key_id)
    if not existing_key or existing_key.service_account_id != service_account.id:
        raise NotFoundError("API key not found")

    auth_crud.update_api_key(
        db,
        existing_key,
        is_active=False,
        revoked_at=datetime.now(UTC),
    )
    return create_service_account_api_key_service(
        db,
        actor_user,
        service_account_id,
        APIKeyCreateRequest(
            name=payload.name or existing_key.name,
            scopes=payload.scopes or existing_key.scopes or [],
            expires_at=payload.expires_at or existing_key.expires_at,
        ),
    )


def revoke_service_account_api_key_service(
    db: Session, actor_user, service_account_id: int, api_key_id: int
) -> dict[str, str]:
    service_account = auth_crud.get_service_account_by_id(db, service_account_id)
    if not service_account:
        raise NotFoundError("Service account not found")
    _validate_user_can_manage_org(actor_user, service_account.organisation_id)

    api_key = auth_crud.get_api_key_by_id(db, api_key_id)
    if not api_key or api_key.service_account_id != service_account.id:
        raise NotFoundError("API key not found")

    auth_crud.update_api_key(
        db,
        api_key,
        is_active=False,
        revoked_at=datetime.now(UTC),
    )
    return {"message": "API key revoked successfully"}


def list_api_key_rotation_alerts_service(db: Session, actor_user) -> list[dict[str, Any]]:
    organisation_id = None if actor_user.role == "admin" else actor_user.organisation_id
    service_accounts = auth_crud.list_service_accounts(db, organisation_id=organisation_id)
    alerts: list[dict[str, Any]] = []
    now = datetime.now(UTC)
    threshold = now + timedelta(days=API_KEY_EXPIRY_ALERT_DAYS)
    for service_account in service_accounts:
        for api_key in auth_crud.list_api_keys(db, service_account_id=service_account.id):
            if not api_key.is_active:
                continue
            rotation_due = api_key.rotation_due_at and api_key.rotation_due_at <= threshold
            expiry_due = api_key.expires_at and api_key.expires_at <= threshold
            if rotation_due or expiry_due:
                alerts.append(
                    {
                        "service_account_id": service_account.id,
                        "service_account_name": service_account.name,
                        "api_key_id": api_key.id,
                        "api_key_name": api_key.name,
                        "rotation_due_at": api_key.rotation_due_at,
                        "expires_at": api_key.expires_at,
                    }
                )
    return alerts


def authenticate_api_key(db: Session, raw_key: str):
    api_key = auth_crud.get_api_key_by_secret(db, raw_key)
    if not api_key or not api_key.is_active:
        raise UnauthorizedError("Invalid API key")

    now = datetime.now(UTC)
    if api_key.revoked_at is not None:
        raise UnauthorizedError("API key has been revoked")
    if api_key.expires_at and _as_utc_naive(api_key.expires_at) < _as_utc_naive(now):
        raise UnauthorizedError("API key has expired")
    if api_key.rotation_due_at and _as_utc_naive(api_key.rotation_due_at) < _as_utc_naive(
        now
    ):
        raise UnauthorizedError("API key rotation is required before further use")

    service_account = auth_crud.get_service_account_by_id(db, api_key.service_account_id)
    if not service_account or not service_account.is_active:
        raise UnauthorizedError("Service account is inactive")
    if service_account.expires_at and _as_utc_naive(service_account.expires_at) < _as_utc_naive(
        now
    ):
        raise UnauthorizedError("Service account has expired")

    auth_crud.update_api_key(db, api_key, last_used_at=now)
    auth_crud.update_service_account(db, service_account, last_used_at=now)
    return service_account, api_key


def get_authenticated_principal(
    db: Session, *, bearer_token: str | None = None, api_key: str | None = None
):
    from auth_dependencies import AuthenticatedPrincipal

    if bearer_token:
        user = get_authenticated_user_from_token(db, bearer_token)
        return AuthenticatedPrincipal(
            principal_type="user",
            subject_id=str(user.id),
            organisation_id=user.organisation_id,
            scopes={"*"},
            user=user,
        )

    if api_key:
        service_account, persisted_key = authenticate_api_key(db, api_key)
        return AuthenticatedPrincipal(
            principal_type="service_account",
            subject_id=str(service_account.id),
            organisation_id=service_account.organisation_id,
            scopes=set(persisted_key.scopes or service_account.scopes or []),
            service_account=service_account,
            api_key=persisted_key,
        )

    return None
