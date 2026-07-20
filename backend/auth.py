"""Authentication helpers.

Uses `pwdlib` for password hashing and `joserfc` to issue/verify
OAuth2-style bearer tokens (JWTs). Exposes a FastAPI dependency
`get_current_user` that returns decoded token claims.
"""

from datetime import datetime, timedelta, UTC
import os
from typing import Any, Dict, Optional


from pwdlib import PasswordHash
from secrets import token_urlsafe
import uuid

from joserfc import jwt
from joserfc.jwk import OctKey
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from dotenv import load_dotenv

load_dotenv()

from utils.security_utils import validate_secret_key

# Password hashing
pwd_context = PasswordHash.recommended()

# JWT / token configuration (override via env vars)
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
JWT_ISSUER = os.getenv("JWT_ISSUER", "FraudSentinal")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "fraudsentinel-api")
JWT_CLOCK_SKEW_SECONDS = int(os.getenv("JWT_CLOCK_SKEW_SECONDS", "30"))

# Validate SECRET_KEY on import (will be caught on startup)
try:
    validate_secret_key(SECRET_KEY)
except ValueError:
    # We don't exit here because some tools might just import auth.py
    # app.py will do the final check on startup
    pass

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_jwt_key() -> OctKey:
    return OctKey.import_key(SECRET_KEY)


def hash_password(password: str) -> str:
    """Hash a plain text password using the configured algorithm."""
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(password, hashed_password)


def needs_rehash(hashed_password: str) -> bool:
    """Return True if a stored hash should be upgraded."""
    return pwd_context.needs_update(hashed_password)


def verify_and_update(password: str, hashed_password: str):
    """Verify a password and return (is_valid, new_hash_or_None).

    If the hash needs to be upgraded, `new_hash_or_None` will contain
    the updated hash for the caller to persist; otherwise it will be None.
    """
    valid, new_hash = pwd_context.verify_and_update(password, hashed_password)
    return valid, new_hash


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token string."""
    return token_urlsafe(length)


def create_access_token(
    subject: str,
    data: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token containing `sub` and optional data.

    `subject` is typically a user identifier (e.g. user id or email).
    """
    now = datetime.now(UTC)
    to_encode: Dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "jti": str(uuid.uuid4()),
    }
    if data:
        to_encode.update(data)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = int(expire.timestamp())

    header = {"alg": ALGORITHM}
    token = jwt.encode(header, to_encode, get_jwt_key(), algorithms=[ALGORITHM])
    return token


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and verify a JWT access token.

    Raises `HTTPException(status_code=401)` on failure so it can be used
    directly in FastAPI dependencies.
    """
    try:
        decoded_token = jwt.decode(token, get_jwt_key(), algorithms=[ALGORITHM])
        claims = decoded_token.claims
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate required claims manually because joserfc separates decode from claim validation
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    iss = claims.get("iss")
    if iss != JWT_ISSUER:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token issuer",
            headers={"WWW-Authenticate": "Bearer"},
        )

    aud = claims.get("aud")
    valid_audience = aud == JWT_AUDIENCE or (
        isinstance(aud, list) and JWT_AUDIENCE in aud
    )
    if not valid_audience:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token audience",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jti = claims.get("jti")
    if not isinstance(jti, str) or not jti.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    current_time = datetime.now(UTC)
    exp = claims.get("exp")
    if exp is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing expiration",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if datetime.fromtimestamp(int(exp), UTC) < current_time - timedelta(
        seconds=JWT_CLOCK_SKEW_SECONDS
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    nbf = claims.get("nbf")
    if nbf is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing not-before claim",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if datetime.fromtimestamp(int(nbf), UTC) > current_time + timedelta(
        seconds=JWT_CLOCK_SKEW_SECONDS
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is not active yet",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return dict(claims)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """FastAPI dependency that returns decoded token claims for the current user.

    Callers should map claims to application user objects as needed.
    """
    return decode_access_token(token)


async def get_current_org_id(claims: Dict[str, Any] = Depends(get_current_user)) -> int:
    """FastAPI dependency that returns the organisation_id from the current user's token.

    Raises 403 if the user is not assigned to an organisation.
    """
    org_id = claims.get("org_id")
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not assigned to an organisation",
        )
    return int(org_id)
