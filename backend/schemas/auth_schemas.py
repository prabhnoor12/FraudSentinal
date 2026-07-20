from datetime import datetime
from typing import Optional

from pydantic import ConfigDict, EmailStr

from schemas.api_schemas import ORMStrictSchema, StrictSchema


class RegisterRequest(StrictSchema):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    organisation_name: Optional[str] = None


class LoginRequest(StrictSchema):
    email: EmailStr
    password: str


class TokenResponse(StrictSchema):
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    mfa_required: bool = False
    pre_auth_token: Optional[str] = None
    message: Optional[str] = None


class MFALoginRequest(StrictSchema):
    pre_auth_token: str
    code: str


class RefreshTokenRequest(StrictSchema):
    refresh_token: str


class PasswordResetRequest(StrictSchema):
    email: EmailStr


class PasswordResetConfirm(StrictSchema):
    token: str
    new_password: str


class AuthUserOut(ORMStrictSchema):
    id: int
    organisation_id: Optional[int] = None
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ServiceAccountCreate(StrictSchema):
    organisation_id: int
    name: str
    description: Optional[str] = None
    scopes: list[str]
    expires_at: Optional[datetime] = None


class ServiceAccountOut(ORMStrictSchema):
    id: int
    organisation_id: int
    created_by_user_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    scopes: list[str]
    is_active: bool
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class APIKeyCreateRequest(StrictSchema):
    name: str
    scopes: Optional[list[str]] = None
    expires_at: Optional[datetime] = None


class APIKeyRotateRequest(StrictSchema):
    name: Optional[str] = None
    scopes: Optional[list[str]] = None
    expires_at: Optional[datetime] = None


class APIKeyOut(StrictSchema):
    id: int
    name: str
    key_prefix: str
    masked_key: str
    raw_key: Optional[str] = None
    scopes: list[str]
    is_active: bool
    expires_at: Optional[datetime] = None
    rotation_due_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime
    last_used_at: Optional[datetime] = None


class APIKeyAlertOut(StrictSchema):
    service_account_id: int
    service_account_name: str
    api_key_id: int
    api_key_name: str
    rotation_due_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
