from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import string
from ipaddress import ip_address, ip_network
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


def fingerprint_token(token: str, *, secret: Optional[str] = None) -> str:
    """Create a keyed fingerprint for stored tokens without persisting raw values."""
    if not isinstance(token, str) or not token.strip():
        raise ValueError("Token must be a non-empty string")

    fingerprint_secret = (
        secret
        or os.getenv("TOKEN_HASH_SECRET")
        or os.getenv("SECRET_KEY")
        or "fraudsentinel-dev-token-secret"
    )
    return hmac.new(
        fingerprint_secret.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


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


def derive_fernet_key(secret: str) -> str:
    """Derive a valid Fernet key from an application secret."""
    if not isinstance(secret, str) or not secret.strip():
        raise ValueError("Secret must be a non-empty string")
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii")


def validate_email(email: str) -> bool:
    """Return True when an email address matches a safe, common format."""
    if not isinstance(email, str):
        return False
    normalized = email.strip().lower()
    if not normalized or len(normalized) > 254:
        return False
    return bool(EMAIL_REGEX.fullmatch(normalized))


def validate_ip_address(value: str) -> bool:
    """Return True when the value is a valid IPv4 or IPv6 address."""
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        ip_address(value.strip())
        return True
    except ValueError:
        return False


def normalize_ip_address(value: str) -> str:
    """Normalize an IP address to canonical string form."""
    if not validate_ip_address(value):
        raise ValueError("Invalid IP address")
    return str(ip_address(value.strip()))


def normalize_country_code(value: Optional[str]) -> Optional[str]:
    """Normalize ISO-style country codes to uppercase two-letter values."""
    if value is None:
        return None
    normalized = sanitize_input(value, max_length=2).upper()
    if len(normalized) != 2 or not normalized.isalpha():
        raise ValueError("Country code must be a 2-letter ISO code")
    return normalized


def normalize_card_number(value: Optional[str]) -> Optional[str]:
    """Strip formatting from card numbers and validate basic length."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Card number must be a string")
    digits = "".join(char for char in value if char.isdigit())
    if not digits:
        raise ValueError("Card number must contain digits")
    if len(digits) < 6 or len(digits) > 19:
        raise ValueError("Card number must be between 6 and 19 digits")
    return digits


def passes_luhn_check(card_number: str) -> bool:
    """Return True when the card number passes the Luhn checksum."""
    normalized = normalize_card_number(card_number)
    if normalized is None or len(normalized) < 12:
        return False

    total = 0
    reverse_digits = normalized[::-1]
    for index, digit_char in enumerate(reverse_digits):
        digit = int(digit_char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


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


def get_trusted_proxy_networks() -> list[str]:
    """Return configured trusted proxy networks from the environment."""
    configured = os.getenv("TRUSTED_PROXY_NETWORKS", "")
    values = [item.strip() for item in configured.split(",") if item.strip()]
    return values


def is_production_environment() -> bool:
    """Return True when the app is configured to run in production mode."""
    environment = (
        os.getenv("APP_ENV")
        or os.getenv("ENVIRONMENT")
        or os.getenv("FASTAPI_ENV")
        or "development"
    )
    return environment.strip().lower() in {"prod", "production"}


def validate_production_hardening() -> None:
    """Validate required production-only security configuration."""
    if not is_production_environment():
        return

    from redis import get_redis_url

    if not get_redis_url():
        raise ValueError("REDIS_URL must be configured in production")

    if not get_trusted_proxy_networks():
        raise ValueError("TRUSTED_PROXY_NETWORKS must be configured in production")


def is_trusted_proxy_host(host: Optional[str]) -> bool:
    """Return True when the immediate client is a configured trusted proxy."""
    if not host:
        return False

    trusted_networks = get_trusted_proxy_networks()
    if not trusted_networks:
        return False

    try:
        host_ip = ip_address(host)
    except ValueError:
        return False

    for network in trusted_networks:
        try:
            if host_ip in ip_network(network, strict=False):
                return True
        except ValueError:
            continue
    return False


def get_request_client_ip(request: Any) -> str:
    """Resolve the client IP, trusting forwarded headers only from known proxies."""
    client_host = getattr(getattr(request, "client", None), "host", None)
    if is_trusted_proxy_host(client_host):
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            forwarded_ip = forwarded_for.split(",")[0].strip()
            if forwarded_ip:
                return forwarded_ip

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

    if client_host:
        return client_host

    return "unknown"


__all__ = [
    "generate_api_key",
    "constant_time_compare",
    "hash_value",
    "fingerprint_token",
    "is_strong_password",
    "derive_fernet_key",
    "validate_email",
    "validate_ip_address",
    "normalize_ip_address",
    "normalize_country_code",
    "normalize_card_number",
    "passes_luhn_check",
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
    "get_trusted_proxy_networks",
    "is_production_environment",
    "validate_production_hardening",
    "is_trusted_proxy_host",
    "get_request_client_ip",
]
