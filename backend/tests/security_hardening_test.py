from __future__ import annotations

from types import SimpleNamespace
import uuid

import pyotp
from fastapi import status

from auth import hash_password
from models.audit_models import AuditLog
from models.auth_models import PasswordResetToken, RefreshToken, TokenBlacklist
from models.user_models import User
from services.mfa_service import MFAService, get_mfa_cipher
from utils.security_utils import (
    fingerprint_token,
    get_request_client_ip,
    validate_production_hardening,
)


def _email(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}@example.com"


def _register(client, *, email: str, password: str) -> None:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "organisation_name": f"Org_{uuid.uuid4().hex[:8]}",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED


def test_password_reset_request_hides_token_outside_testing(client, monkeypatch):
    email = _email("reset_hide")
    _register(client, email=email, password="StrongPass123!")

    monkeypatch.setenv("TESTING", "0")
    response = client.post("/auth/password-reset/request", json={"email": email})

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "message": "If the account exists, a reset token has been created"
    }


def test_auth_tokens_are_persisted_as_fingerprints(client, db):
    email = _email("token_store")
    password = "StrongPass123!"
    _register(client, email=email, password=password)

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == status.HTTP_200_OK
    token_payload = login.json()
    access_token = token_payload["access_token"]
    refresh_token = token_payload["refresh_token"]

    stored_refresh = db.query(RefreshToken).first()
    assert stored_refresh is not None
    assert stored_refresh.token == fingerprint_token(refresh_token)
    assert stored_refresh.token != refresh_token

    reset = client.post("/auth/password-reset/request", json={"email": email})
    assert reset.status_code == status.HTTP_200_OK
    reset_token = reset.json()["reset_token"]

    stored_reset = db.query(PasswordResetToken).first()
    assert stored_reset is not None
    assert stored_reset.token == fingerprint_token(reset_token)
    assert stored_reset.token != reset_token

    logout = client.post(
        "/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout.status_code == status.HTTP_200_OK

    stored_blacklist = db.query(TokenBlacklist).first()
    assert stored_blacklist is not None
    assert stored_blacklist.token == fingerprint_token(access_token)
    assert stored_blacklist.token != access_token


def test_mfa_secret_is_encrypted_before_storage(db):
    user = User(
        email=_email("mfa_encrypt"),
        password_hash=hash_password("StrongPass123!"),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    secret = pyotp.random_base32()
    code = pyotp.TOTP(secret).now()

    backup_codes = MFAService.verify_and_enable(db, user, secret, code)

    assert backup_codes
    assert user.mfa_secret
    assert user.mfa_secret != secret
    assert get_mfa_cipher().decrypt(user.mfa_secret.encode()).decode() == secret


def test_request_client_ip_only_trusts_forwarded_headers_from_known_proxies(
    monkeypatch,
):
    request = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.10", "x-real-ip": "198.51.100.11"},
        client=SimpleNamespace(host="10.0.0.20"),
    )

    monkeypatch.delenv("TRUSTED_PROXY_NETWORKS", raising=False)
    assert get_request_client_ip(request) == "10.0.0.20"

    monkeypatch.setenv("TRUSTED_PROXY_NETWORKS", "10.0.0.0/24")
    assert get_request_client_ip(request) == "203.0.113.10"


def test_security_headers_are_applied(client):
    response = client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    assert "Content-Security-Policy" in response.headers
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "Strict-Transport-Security" in response.headers


def test_validate_production_hardening_requires_runtime_config(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("TRUSTED_PROXY_NETWORKS", raising=False)

    try:
        validate_production_hardening()
        assert False, "Expected missing REDIS_URL to fail validation"
    except ValueError as exc:
        assert "REDIS_URL" in str(exc)

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        validate_production_hardening()
        assert False, "Expected missing TRUSTED_PROXY_NETWORKS to fail validation"
    except ValueError as exc:
        assert "TRUSTED_PROXY_NETWORKS" in str(exc)

    monkeypatch.setenv("TRUSTED_PROXY_NETWORKS", "10.0.0.0/24")
    validate_production_hardening()


def test_auth_security_events_are_audited(client, db):
    email = _email("audit_auth")
    password = "StrongPass123!"
    _register(client, email=email, password=password)

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == status.HTTP_200_OK
    access_token = login.json()["access_token"]
    refresh_token = login.json()["refresh_token"]

    reset_request = client.post("/auth/password-reset/request", json={"email": email})
    assert reset_request.status_code == status.HTTP_200_OK
    reset_token = reset_request.json()["reset_token"]

    reset_confirm = client.post(
        "/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "NewStrongPass123!"},
    )
    assert reset_confirm.status_code == status.HTTP_200_OK

    refresh = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh.status_code == status.HTTP_200_OK

    logout = client.post(
        "/auth/logout",
        json={"refresh_token": refresh.json()["refresh_token"]},
        headers={"Authorization": f"Bearer {refresh.json()['access_token']}"},
    )
    assert logout.status_code == status.HTTP_200_OK

    actions = {log.action for log in db.query(AuditLog).all()}
    assert "password_reset_requested" in actions
    assert "password_reset_confirmed" in actions
    assert "refresh_token_rotated" in actions
    assert "logout" in actions


def test_mfa_lifecycle_events_are_audited(client, db):
    email = _email("audit_mfa")
    password = "StrongPass123!"
    _register(client, email=email, password=password)

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == status.HTTP_200_OK
    token = login.json()["access_token"]

    setup = client.post("/mfa/setup", headers={"Authorization": f"Bearer {token}"})
    assert setup.status_code == status.HTTP_200_OK
    secret = setup.json()["secret"]

    verify = client.post(
        "/mfa/verify",
        json={"secret": secret, "code": pyotp.TOTP(secret).now()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert verify.status_code == status.HTTP_200_OK

    disable = client.post("/mfa/disable", headers={"Authorization": f"Bearer {token}"})
    assert disable.status_code == status.HTTP_200_OK

    actions = [log.action for log in db.query(AuditLog).all()]
    assert "mfa_setup_started" in actions
    assert "mfa_enabled" in actions
    assert "mfa_disabled" in actions
