from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from auth import oauth2_scheme
from database import get_db
from services.audit_service import AuditService
from services import auth_service, mfa_service
from pydantic import BaseModel
from utils.exception_handling_utils import AppException
from utils.security_utils import get_request_client_ip

router = APIRouter(prefix="/mfa", tags=["mfa"])


def _audit_context(request: Request) -> dict[str, str | None]:
    return {
        "ip_address": get_request_client_ip(request),
        "user_agent": request.headers.get("user-agent"),
    }


class MFASetupOut(BaseModel):
    secret: str
    qr_code: str


class MFAVerifyIn(BaseModel):
    secret: str
    code: str


class MFAVerifyOut(BaseModel):
    backup_codes: List[str]


@router.post("/setup", response_model=MFASetupOut)
def setup_mfa(
    request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    """Start MFA setup for the current user."""
    user = auth_service.get_authenticated_user_from_token(db, token)

    if user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA is already enabled")

    secret, qr_code = mfa_service.MFAService.generate_setup_data(user)
    AuditService.log_security_event(
        db,
        action="mfa_setup_started",
        user_id=user.id,
        organisation_id=user.organisation_id,
        resource_type="mfa",
        resource_id=str(user.id),
        **_audit_context(request),
    )
    return {"secret": secret, "qr_code": qr_code}


@router.post("/verify", response_model=MFAVerifyOut)
def verify_mfa(
    payload: MFAVerifyIn,
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """Verify the first MFA code and enable it."""
    user = auth_service.get_authenticated_user_from_token(db, token)

    if user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA is already enabled")

    try:
        backup_codes = mfa_service.MFAService.verify_and_enable(
            db, user, payload.secret, payload.code
        )
    except AppException:
        AuditService.log_security_event(
            db,
            action="mfa_enable_failed",
            user_id=user.id,
            organisation_id=user.organisation_id,
            resource_type="mfa",
            resource_id=str(user.id),
            **_audit_context(request),
        )
        raise

    AuditService.log_security_event(
        db,
        action="mfa_enabled",
        user_id=user.id,
        organisation_id=user.organisation_id,
        resource_type="mfa",
        resource_id=str(user.id),
        **_audit_context(request),
    )
    return {"backup_codes": backup_codes}


@router.post("/disable")
def disable_mfa(
    request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    """Disable MFA (requires secondary auth in real world, but for now just disable)."""
    user = auth_service.get_authenticated_user_from_token(db, token)
    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_backup_codes_hash = None
    db.add(user)
    db.commit()
    AuditService.log_security_event(
        db,
        action="mfa_disabled",
        user_id=user.id,
        organisation_id=user.organisation_id,
        resource_type="mfa",
        resource_id=str(user.id),
        **_audit_context(request),
    )
    return {"message": "MFA disabled successfully"}
