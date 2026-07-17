from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.orm import Session

from auth import oauth2_scheme
from database import get_db
from schemas.auth_schemas import (
    AuthUserOut,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from services import auth_service


router = APIRouter(prefix="/auth", tags=["auth"])


def get_authenticated_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return auth_service.get_authenticated_user_from_token(db, token)


@router.post("/register", response_model=AuthUserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    return auth_service.register_user(db, payload)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.authenticate_user(db, payload)


@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    return auth_service.refresh_user_tokens(db, payload.refresh_token)


@router.post("/logout")
def logout(
    refresh_token: str | None = Body(default=None, embed=True),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    auth_service.logout_user(db, access_token=token, refresh_token_value=refresh_token)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=AuthUserOut)
def me(current_user=Depends(get_authenticated_user)):
    return current_user


@router.post("/password-reset/request")
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    return auth_service.request_password_reset(db, payload)


@router.post("/password-reset/confirm")
def confirm_password_reset(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    return auth_service.confirm_password_reset(db, payload)
