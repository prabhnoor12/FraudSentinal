from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import string
from typing import Any, Mapping, Optional
from urllib.parse import urlparse


EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
SUSPICIOUS_CONTENT_PATTERN = re.compile(
    r"<script|javascript:|on\w+=|drop\s+table|union\s+select|--",
    re.IGNORECASE,
)


def generate_api_key(prefix: str = "fs_", length: int = 24) -> str:
    """Generate a secure API key with a readable prefix."""
    if not prefix or not isinstance(prefix, str):
        raise ValueError("Prefix must be a non-empty string")
    if length <= 0:
        raise ValueError("Length must be positive")
    return f"{prefix}{secrets.token_urlsafe(length)}"


def constant_time_compare(left: str, right: str) -> bool:
    """Compare two strings without leaking timing information."""
    if not isinstance(left, str) or not isinstance(right, str):
        return False
    return hmac.compare_digest(left, right)


def hash_value(value: str) -> str:
    """Create a deterministic hash of a value for non-sensitive fingerprinting."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Value must be a non-empty string")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


COMMON_WEAK_PASSWORDS = {
    "password",
    "password123",
    "123456",
    "qwerty",
    "admin",
    "welcome",
    "fraudsentinel",
    "investigator",
    "secret",
    "security",
}


def is_strong_password(
    password: str, user_info: Optional[Mapping[str, str]] = None
) -> bool:
    """Validate password strength requirements.

    Requirements:
    - Min length 12
    - At least 3 of: upper, lower, digit, symbol
    - Not a common weak password
    - Not containing user personal info (email, full name)
    """
    if not isinstance(password, str) or len(password) < 12:
        return False

    # Check for character types
    has_upper = any(char.isupper() for char in password)
    has_lower = any(char.islower() for char in password)
    has_digit = any(char.isdigit() for char in password)
    has_symbol = any(char in string.punctuation for char in password)

    types_count = sum([has_upper, has_lower, has_digit, has_symbol])
    if types_count < 3:
        return False

    # Check for common weak passwords
    if password.lower() in COMMON_WEAK_PASSWORDS:
        return False

    # Check for personal info
    if user_info:
        for key in ["email", "full_name", "phone"]:
            info = user_info.get(key)
            if info and info.lower() in password.lower():
                return False

    return True


def validate_secret_key(key: Optional[str]) -> None:
    """Validate that the SECRET_KEY meets security standards.

    Requirements:
    - Non-empty
    - At least 32 characters
    - Contains mix of upper, lower, digits, and symbols
    """
    if not key:
        raise ValueError(
            "SECRET_KEY must be provided via environment variables or vault"
        )

    if len(key) < 32:
        raise ValueError("SECRET_KEY must be at least 32 characters long")

    has_upper = any(char.isupper() for char in key)
    has_lower = any(char.islower() for char in key)
    has_digit = any(char.isdigit() for char in key)
    has_symbol = any(
        char in string.punctuation or char in "!@#$%^&*()_+-=[]{}|;:,.<>?"
        for char in key
    )

    if not (has_upper and has_lower and has_digit and has_symbol):
        raise ValueError(
            "SECRET_KEY must contain uppercase, lowercase, numbers, and special symbols"
        )


def validate_email(email: str) -> bool:
    """Return True when an email address matches a safe, common format."""
    if not isinstance(email, str):
        return False
    normalized = email.strip().lower()
    if not normalized or len(normalized) > 254:
        return False
    return bool(EMAIL_REGEX.fullmatch(normalized))


def normalize_email(email: str) -> str:
    """Normalize an email address to lowercase and validate it."""
    if not validate_email(email):
        raise ValueError("Invalid email address")
    return email.strip().lower()


def sanitize_input(value: Any, *, max_length: int = 1000, strip: bool = True) -> str:
    """Convert input to a safe string and reject oversized content."""
    if value is None:
        return ""

    if isinstance(value, (int, float, bool)):
        value = str(value)
    elif not isinstance(value, str):
        value = str(value)

    if len(value) > max_length:
        raise ValueError(f"Input exceeds maximum length of {max_length}")

    if strip:
        value = value.strip()
    return value


def mask_sensitive_data(value: Optional[str], *, keep: int = 4) -> Optional[str]:
    """Mask sensitive strings such as emails, tokens, or API keys."""
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return ""

    if len(value) <= keep * 2:
        return "*" * len(value)

    return f"{value[:keep]}{'*' * (len(value) - keep * 2)}{value[-keep:]}"


def redact_sensitive_fields(
    data: Mapping[str, Any], *, keys: Optional[set[str]] = None
) -> dict[str, Any]:
    """Return a copy of a mapping with sensitive values redacted."""
    sensitive_keys = keys or {"password", "token", "secret", "api_key", "authorization"}
    redacted: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(key, str) and any(k in key.lower() for k in sensitive_keys):
            redacted[key] = "[REDACTED]"
        elif isinstance(value, dict):
            redacted[key] = redact_sensitive_fields(value, keys=sensitive_keys)
        elif isinstance(value, list):
            redacted[key] = [
                redact_sensitive_fields(item, keys=sensitive_keys)
                if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            redacted[key] = value
    return redacted


def is_safe_filename(filename: str) -> bool:
    """Check whether a filename is safe for filesystem use."""
    if not isinstance(filename, str) or not filename.strip():
        return False

    if len(filename) > 255:
        return False

    pattern = re.compile(r"[^A-Za-z0-9._-]")
    return not bool(pattern.search(filename))


def is_safe_url(url: str) -> bool:
    """Validate that a URL uses a safe scheme and is syntactically valid."""
    if not isinstance(url, str) or not url.strip():
        return False

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.netloc:
        return False
    return True


def contains_suspicious_content(value: str) -> bool:
    """Detect common input patterns associated with injection or XSS attempts."""
    if not isinstance(value, str):
        return False
    return bool(SUSPICIOUS_CONTENT_PATTERN.search(value))


def generate_secret_key(length: int = 32) -> str:
    """Generate a secret key using the OS entropy source."""
    if length <= 0:
        raise ValueError("Secret length must be positive")
    return secrets.token_urlsafe(length)


def generate_hmac_signature(payload: str | bytes, secret: str) -> str:
    """Create a deterministic HMAC signature for request payloads."""
    if not isinstance(secret, str) or not secret.strip():
        raise ValueError("Secret must be a non-empty string")
    if isinstance(payload, bytes):
        payload_bytes = payload
    else:
        payload_bytes = payload.encode("utf-8")
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


def verify_hmac_signature(payload: str | bytes, signature: str, secret: str) -> bool:
    """Verify an HMAC signature using a constant-time comparison."""
    if not isinstance(signature, str) or not signature.strip():
        return False
    expected_signature = generate_hmac_signature(payload, secret)
    return constant_time_compare(signature, expected_signature)


__all__ = [
    "generate_api_key",
    "constant_time_compare",
    "hash_value",
    "is_strong_password",
    "validate_email",
    "normalize_email",
    "sanitize_input",
    "mask_sensitive_data",
    "redact_sensitive_fields",
    "is_safe_filename",
    "is_safe_url",
    "contains_suspicious_content",
    "generate_secret_key",
    "generate_hmac_signature",
    "verify_hmac_signature",
]
