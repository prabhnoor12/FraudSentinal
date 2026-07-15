
"""Authentication helpers.

Uses `passlib` for password hashing and `authlib` to issue/verify
OAuth2-style bearer tokens (JWTs). Exposes a FastAPI dependency
`get_current_user` that returns decoded token claims.
"""
from datetime import datetime, timedelta
import os
from typing import Any, Dict, Optional

from passlib.context import CryptContext
from secrets import token_urlsafe
from authlib.jose import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT / token configuration (override via env vars)
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


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
    valid = verify_password(password, hashed_password)
    new_hash = None
    if valid and needs_rehash(hashed_password):
        new_hash = hash_password(password)
    return valid, new_hash


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token string."""
    return token_urlsafe(length)


def create_access_token(subject: str, data: Optional[Dict[str, Any]] = None, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token containing `sub` and optional data.

    `subject` is typically a user identifier (e.g. user id or email).
    """
    now = datetime.utcnow()
    to_encode: Dict[str, Any] = {"sub": subject, "iat": int(now.timestamp())}
    if data:
        to_encode.update(data)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = int(expire.timestamp())

    header = {"alg": ALGORITHM}
    token = jwt.encode(header, to_encode, SECRET_KEY)
    if isinstance(token, bytes):
        token = token.decode()
    return token


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and verify a JWT access token.

    Raises `HTTPException(status_code=401)` on failure so it can be used
    directly in FastAPI dependencies.
    """
    try:
        claims = jwt.decode(token, SECRET_KEY)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate exp manually (authlib's decode may not validate timestamps automatically)
    exp = claims.get("exp")
    if exp is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing expiration",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if datetime.utcfromtimestamp(int(exp)) < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return dict(claims)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """FastAPI dependency that returns decoded token claims for the current user.

    Callers should map claims to application user objects as needed.
    """
    return decode_access_token(token)
