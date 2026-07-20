from fastapi import APIRouter, Body, Depends, Request, status
from sqlalchemy.orm import Session

from auth import oauth2_scheme
from database import get_db
from schemas.auth_schemas import (
    AuthUserOut,
    LoginRequest,
    MFALoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from services.audit_service import AuditService
from services import auth_service
from utils.exception_handling_utils import AppException, UnauthorizedError
from utils.security_utils import get_request_client_ip, hash_value


router = APIRouter(prefix="/auth", tags=["auth"])


def _audit_context(request: Request) -> dict[str, str | None]:
    return {
        "ip_address": get_request_client_ip(request),
        "user_agent": request.headers.get("user-agent"),
    }


def get_authenticated_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return auth_service.get_authenticated_user_from_token(db, token)


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
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    current_user = auth_service.get_authenticated_user_from_token(db, token)
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
def me(current_user=Depends(get_authenticated_user)):
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
