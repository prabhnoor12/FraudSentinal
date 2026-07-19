from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from auth import oauth2_scheme
from database import get_db
from services import auth_service, mfa_service
from pydantic import BaseModel

router = APIRouter(prefix="/mfa", tags=["mfa"])


class MFASetupOut(BaseModel):
    secret: str
    qr_code: str


class MFAVerifyIn(BaseModel):
    secret: str
    code: str


class MFAVerifyOut(BaseModel):
    backup_codes: List[str]


@router.post("/setup", response_model=MFASetupOut)
def setup_mfa(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Start MFA setup for the current user."""
    user_claims = auth_service.decode_access_token(token)
    user = auth_service.get_authenticated_user_from_token(db, token)

    if user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA is already enabled")

    secret, qr_code = mfa_service.MFAService.generate_setup_data(user)
    return {"secret": secret, "qr_code": qr_code}


@router.post("/verify", response_model=MFAVerifyOut)
def verify_mfa(
    payload: MFAVerifyIn,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """Verify the first MFA code and enable it."""
    user = auth_service.get_authenticated_user_from_token(db, token)

    if user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA is already enabled")

    backup_codes = mfa_service.MFAService.verify_and_enable(
        db, user, payload.secret, payload.code
    )
    return {"backup_codes": backup_codes}


@router.post("/disable")
def disable_mfa(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Disable MFA (requires secondary auth in real world, but for now just disable)."""
    user = auth_service.get_authenticated_user_from_token(db, token)
    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_backup_codes_hash = None
    db.add(user)
    db.commit()
    return {"message": "MFA disabled successfully"}
