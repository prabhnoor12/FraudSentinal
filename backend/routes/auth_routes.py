from fastapi import APIRouter, Body, Depends, Request, status
from sqlalchemy.orm import Session

from auth_dependencies import get_current_user
from database import get_db
from schemas.auth_schemas import (
    APIKeyAlertOut,
    APIKeyAlertListResponse,
    APIKeyCreateRequest,
    APIKeyListResponse,
    APIKeyOut,
    APIKeyRotateRequest,
    AuthUserOut,
    LoginRequest,
    MFALoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ServiceAccountCreate,
    ServiceAccountListResponse,
    ServiceAccountOut,
    TokenResponse,
)
from services.audit_service import AuditService
from services import auth_service
from utils.exception_handling_utils import AppException, UnauthorizedError
from utils.pagination_utils import (
    build_paginated_payload,
    normalize_limit,
    normalize_offset,
    normalize_sort_dir,
)
from utils.security_utils import get_request_client_ip, hash_value


router = APIRouter(prefix="/auth", tags=["auth"])


def _audit_context(request: Request) -> dict[str, str | None]:
    return {
        "ip_address": get_request_client_ip(request),
        "user_agent": request.headers.get("user-agent"),
    }


@router.post(
    "/register", response_model=AuthUserOut, status_code=status.HTTP_201_CREATED
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    return auth_service.register_user(db, payload)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.authenticate_user(db, payload)


@router.post("/mfa-login", response_model=TokenResponse)
def mfa_login(
    payload: MFALoginRequest, request: Request, db: Session = Depends(get_db)
):
    # Decode pre_auth_token to get user_id
    claims = auth_service.decode_access_token(payload.pre_auth_token)
    if not claims.get("mfa_pending"):
        raise UnauthorizedError("Invalid pre-authentication token")

    user_id = int(claims["sub"])
    try:
        result = auth_service.verify_mfa_login(db, user_id, payload.code)
    except AppException:
        AuditService.log_security_event(
            db,
            action="mfa_login_failed",
            user_id=user_id,
            resource_type="mfa",
            resource_id=str(user_id),
            details={"reason": "verification_failed"},
            **_audit_context(request),
        )
        raise

    refreshed_claims = auth_service.decode_access_token(result["access_token"])
    AuditService.log_security_event(
        db,
        action="mfa_login_succeeded",
        user_id=user_id,
        organisation_id=refreshed_claims.get("org_id"),
        resource_type="mfa",
        resource_id=str(user_id),
        **_audit_context(request),
    )
    return result


@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(
    payload: RefreshTokenRequest, request: Request, db: Session = Depends(get_db)
):
    try:
        result = auth_service.refresh_user_tokens(db, payload.refresh_token)
    except AppException:
        AuditService.log_security_event(
            db,
            action="refresh_token_rotation_failed",
            resource_type="refresh_token",
            details={"token_fingerprint": hash_value(payload.refresh_token)},
            **_audit_context(request),
        )
        raise

    claims = auth_service.decode_access_token(result["access_token"])
    AuditService.log_security_event(
        db,
        action="refresh_token_rotated",
        user_id=int(claims["sub"]),
        organisation_id=claims.get("org_id"),
        resource_type="refresh_token",
        resource_id=str(claims["sub"]),
        **_audit_context(request),
    )
    return result


@router.post("/logout")
def logout(
    request: Request,
    refresh_token: str | None = Body(default=None, embed=True),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = request.headers.get("Authorization", "").replace("Bearer ", "", 1).strip()
    if not token:
        raise UnauthorizedError("Bearer token is required for logout")
    auth_service.logout_user(db, access_token=token, refresh_token_value=refresh_token)
    AuditService.log_security_event(
        db,
        action="logout",
        user_id=current_user.id,
        organisation_id=current_user.organisation_id,
        resource_type="session",
        resource_id=str(current_user.id),
        details={"refresh_token_supplied": refresh_token is not None},
        **_audit_context(request),
    )
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=AuthUserOut)
def me(current_user=Depends(get_current_user)):
    return current_user


@router.post("/password-reset/request")
def request_password_reset(
    payload: PasswordResetRequest, request: Request, db: Session = Depends(get_db)
):
    result = auth_service.request_password_reset(db, payload)
    AuditService.log_security_event(
        db,
        action="password_reset_requested",
        resource_type="password_reset",
        details={
            "email_hash": hash_value(payload.email.strip().lower()),
            "testing_token_exposed": "reset_token" in result,
        },
        **_audit_context(request),
    )
    return result


@router.post("/password-reset/confirm")
def confirm_password_reset(
    payload: PasswordResetConfirm, request: Request, db: Session = Depends(get_db)
):
    try:
        result = auth_service.confirm_password_reset(db, payload)
    except AppException:
        AuditService.log_security_event(
            db,
            action="password_reset_confirm_failed",
            resource_type="password_reset",
            details={"token_fingerprint": hash_value(payload.token)},
            **_audit_context(request),
        )
        raise

    AuditService.log_security_event(
        db,
        action="password_reset_confirmed",
        resource_type="password_reset",
        details={"token_fingerprint": hash_value(payload.token)},
        **_audit_context(request),
    )
    return result


@router.post(
    "/service-accounts",
    response_model=ServiceAccountOut,
    status_code=status.HTTP_201_CREATED,
)
def create_service_account(
    payload: ServiceAccountCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return auth_service.create_service_account_service(db, current_user, payload)


@router.get("/service-accounts", response_model=ServiceAccountListResponse)
def list_service_accounts(
    request: Request,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    normalized_offset = normalize_offset(offset)
    normalized_limit = normalize_limit(limit, default=100, maximum=200)
    items, total = auth_service.list_service_accounts_service(
        db,
        current_user,
        offset=normalized_offset,
        limit=normalized_limit,
        sort_by=sort_by,
        sort_dir=normalize_sort_dir(sort_dir),
    )
    return build_paginated_payload(
        request=request,
        items=items,
        total=total,
        limit=normalized_limit,
        offset=normalized_offset,
    )


@router.post(
    "/service-accounts/{service_account_id}/keys",
    response_model=APIKeyOut,
    status_code=status.HTTP_201_CREATED,
)
def create_service_account_api_key(
    service_account_id: int,
    payload: APIKeyCreateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return auth_service.create_service_account_api_key_service(
        db, current_user, service_account_id, payload
    )


@router.get(
    "/service-accounts/{service_account_id}/keys",
    response_model=APIKeyListResponse,
)
def list_service_account_api_keys(
    request: Request,
    service_account_id: int,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    normalized_offset = normalize_offset(offset)
    normalized_limit = normalize_limit(limit, default=100, maximum=200)
    items, total = auth_service.list_service_account_api_keys_service(
        db,
        current_user,
        service_account_id,
        offset=normalized_offset,
        limit=normalized_limit,
        sort_by=sort_by,
        sort_dir=normalize_sort_dir(sort_dir),
    )
    return build_paginated_payload(
        request=request,
        items=items,
        total=total,
        limit=normalized_limit,
        offset=normalized_offset,
    )


@router.post(
    "/service-accounts/{service_account_id}/keys/{api_key_id}/rotate",
    response_model=APIKeyOut,
)
def rotate_service_account_api_key(
    service_account_id: int,
    api_key_id: int,
    payload: APIKeyRotateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return auth_service.rotate_service_account_api_key_service(
        db, current_user, service_account_id, api_key_id, payload
    )


@router.post("/service-accounts/{service_account_id}/keys/{api_key_id}/revoke")
def revoke_service_account_api_key(
    service_account_id: int,
    api_key_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return auth_service.revoke_service_account_api_key_service(
        db, current_user, service_account_id, api_key_id
    )


@router.get(
    "/service-accounts/rotation-alerts",
    response_model=APIKeyAlertListResponse,
)
def list_rotation_alerts(
    request: Request,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "rotation_due_at",
    sort_dir: str = "asc",
    current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    normalized_offset = normalize_offset(offset)
    normalized_limit = normalize_limit(limit, default=100, maximum=200)
    items, total = auth_service.list_api_key_rotation_alerts_service(
        db,
        current_user,
        offset=normalized_offset,
        limit=normalized_limit,
        sort_by=sort_by,
        sort_dir=normalize_sort_dir(sort_dir) if sort_by != "rotation_due_at" else sort_dir,
    )
    return build_paginated_payload(
        request=request,
        items=items,
        total=total,
        limit=normalized_limit,
        offset=normalized_offset,
    )
