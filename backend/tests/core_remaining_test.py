from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import uuid

from fastapi import status

from models.user_models import User
from services import fraud_rule_service


def _email(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}@example.com"


def _register(client, *, email: str, password: str, organisation_name: str | None):
    payload: dict = {"email": email, "password": password}
    if organisation_name is not None:
        payload["organisation_name"] = organisation_name
    resp = client.post("/auth/register", json=payload)
    assert resp.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
    return resp.json()


def _login(client, *, email: str, password: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == status.HTTP_200_OK
    token = resp.json()["access_token"]
    assert token
    return token


def _me(client, *, token: str) -> dict:
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == status.HTTP_200_OK
    return resp.json()


def _auth_ctx(client, *, with_org: bool = True) -> tuple[str, dict]:
    email = _email("core")
    password = "StrongPass123!"
    org_name = f"Org_{uuid.uuid4().hex[:8]}" if with_org else None
    _register(client, email=email, password=password, organisation_name=org_name)
    token = _login(client, email=email, password=password)
    return token, _me(client, token=token)


def _make_admin(db, *, user_id: int) -> None:
    user = db.query(User).filter(User.id == user_id).first()
    assert user is not None
    user.role = "admin"
    db.add(user)
    db.commit()


def test_organisations_list_get_update_summary_and_isolation(client):
    token_a, me_a = _auth_ctx(client, with_org=True)
    org_a = me_a["organisation_id"]
    assert org_a is not None

    list_resp = client.get("/organisations", headers={"Authorization": f"Bearer {token_a}"})
    assert list_resp.status_code == status.HTTP_200_OK
    orgs = list_resp.json()
    assert isinstance(orgs, list)
    assert len(orgs) == 1
    assert orgs[0]["id"] == org_a

    get_resp = client.get(
        f"/organisations/{org_a}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert get_resp.status_code == status.HTTP_200_OK
    assert get_resp.json()["id"] == org_a

    update_resp = client.put(
        f"/organisations/{org_a}",
        json={"name": f"Renamed_{uuid.uuid4().hex[:8]}"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert update_resp.status_code == status.HTTP_200_OK
    assert update_resp.json()["id"] == org_a

    summary_resp = client.get(
        "/organisations/dashboard/summary",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert summary_resp.status_code == status.HTTP_200_OK
    summary = summary_resp.json()
    assert "total_transactions" in summary
    assert "decision_distribution" in summary
    assert "pending_cases_count" in summary

    token_b, me_b = _auth_ctx(client, with_org=True)
    org_b = me_b["organisation_id"]
    assert org_b != org_a

    forbidden_get = client.get(
        f"/organisations/{org_a}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert forbidden_get.status_code == status.HTTP_404_NOT_FOUND


def test_settings_create_get_update(client):
    token, me = _auth_ctx(client, with_org=True)
    org_id = me["organisation_id"]

    create_resp = client.post(
        "/settings",
        json={
            "organisation_id": org_id,
            "currency": "USD",
            "timezone": "UTC",
            "review_threshold": 41,
            "decline_threshold": 72,
            "enable_billing": True,
            "enable_usage_tracking": True,
            "notification_email": "alerts@example.com",
            "notes": "test",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    created = create_resp.json()
    assert created["organisation_id"] == org_id
    assert created["review_threshold"] == 41

    get_resp = client.get(
        f"/settings/{org_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == status.HTTP_200_OK
    assert get_resp.json()["organisation_id"] == org_id

    update_resp = client.put(
        f"/settings/{org_id}",
        json={"review_threshold": 35, "decline_threshold": 80},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_resp.status_code == status.HTTP_200_OK
    updated = update_resp.json()
    assert updated["review_threshold"] == 35
    assert updated["decline_threshold"] == 80


def test_users_crud_and_role_admin_only(client, db):
    token, me = _auth_ctx(client, with_org=True)
    create_resp = client.post(
        "/users",
        json={
            "email": _email("member"),
            "password": "StrongPass123!",
            "full_name": "Member User",
            "is_active": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    created = create_resp.json()
    user_id = created["id"]
    assert created["email"]
    assert created["role"] == "investigator"

    list_resp = client.get("/users", headers={"Authorization": f"Bearer {token}"})
    assert list_resp.status_code == status.HTTP_200_OK
    users = list_resp.json()
    assert any(u["id"] == user_id for u in users)

    get_resp = client.get(f"/users/{user_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_resp.status_code == status.HTTP_200_OK
    assert get_resp.json()["id"] == user_id

    update_resp = client.put(
        f"/users/{user_id}",
        json={"full_name": "Updated Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_resp.status_code == status.HTTP_200_OK
    assert update_resp.json()["full_name"] == "Updated Name"

    role_fail = client.patch(
        f"/users/{user_id}/role",
        params={"role": "admin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert role_fail.status_code == status.HTTP_403_FORBIDDEN

    _make_admin(db, user_id=me["id"])

    role_bad = client.patch(
        f"/users/{user_id}/role",
        params={"role": "superuser"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert role_bad.status_code == status.HTTP_400_BAD_REQUEST

    role_ok = client.patch(
        f"/users/{user_id}/role",
        params={"role": "admin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert role_ok.status_code == status.HTTP_200_OK
    assert role_ok.json()["role"] == "admin"

    delete_resp = client.delete(f"/users/{user_id}", headers={"Authorization": f"Bearer {token}"})
    assert delete_resp.status_code == status.HTTP_204_NO_CONTENT


def test_sessions_create_list_get_end(client):
    token, me = _auth_ctx(client, with_org=True)
    user_id = me["id"]

    session_token = f"sess_{uuid.uuid4().hex}"
    create_resp = client.post(
        "/sessions",
        json={
            "user_id": user_id,
            "session_token": session_token,
            "ip_address": "127.0.0.1",
            "user_agent": "pytest",
            "status": "active",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    created = create_resp.json()
    session_id = created["id"]
    assert created["session_token"] == session_token

    list_resp = client.get(
        "/sessions",
        params={"user_id": user_id, "status_filter": "active"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == status.HTTP_200_OK
    assert any(s["id"] == session_id for s in list_resp.json())

    get_resp = client.get(f"/sessions/{session_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_resp.status_code == status.HTTP_200_OK
    assert get_resp.json()["id"] == session_id

    end_resp = client.post(f"/sessions/{session_id}/end", headers={"Authorization": f"Bearer {token}"})
    assert end_resp.status_code == status.HTTP_200_OK
    ended = end_resp.json()
    assert ended["id"] == session_id
    assert ended["status"] != "active"


def test_usage_and_user_tracking_endpoints(client):
    token, me = _auth_ctx(client, with_org=True)
    user_id = me["id"]
    org_id = me["organisation_id"]

    event_resp = client.post(
        "/usage/events",
        json={
            "user_id": user_id,
            "organisation_id": org_id,
            "event_type": "check_fraud",
            "units": 1.0,
            "unit_type": "request",
            "description": "test",
            "status": "recorded",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert event_resp.status_code == status.HTTP_201_CREATED
    event = event_resp.json()
    assert event["user_id"] == user_id
    assert event["organisation_id"] == org_id

    list_events = client.get(
        "/usage/events",
        params={"organisation_id": org_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_events.status_code == status.HTTP_200_OK
    assert any(e["id"] == event["id"] for e in list_events.json())

    now = datetime.now(timezone.utc)
    summary_resp = client.post(
        "/usage/summaries",
        json={
            "user_id": user_id,
            "organisation_id": org_id,
            "period_start": (now - timedelta(days=30)).isoformat(),
            "period_end": now.isoformat(),
            "total_units": 10.0,
            "currency": "USD",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert summary_resp.status_code == status.HTTP_201_CREATED
    summary = summary_resp.json()
    assert summary["organisation_id"] == org_id

    list_summaries = client.get(
        "/usage/summaries",
        params={"user_id": user_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_summaries.status_code == status.HTTP_200_OK
    assert any(s["id"] == summary["id"] for s in list_summaries.json())

    ut_event = client.post(
        "/user-tracking/events",
        json={
            "user_id": user_id,
            "organisation_id": org_id,
            "event_type": "login",
            "units": 1.0,
            "unit_type": "event",
            "description": "test",
            "status": "recorded",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ut_event.status_code == status.HTTP_201_CREATED

    ut_events = client.get(
        "/user-tracking/events",
        params={"user_id": user_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ut_events.status_code == status.HTTP_200_OK
    assert len(ut_events.json()) >= 1


def test_limit_tracking_limits_and_records(client):
    token, me = _auth_ctx(client, with_org=True)
    user_id = me["id"]
    org_id = me["organisation_id"]

    limit_resp = client.post(
        "/limit-tracking/limits",
        json={
            "organisation_id": org_id,
            "limit_type": "check_fraud",
            "limit_value": 1000,
            "period": "monthly",
            "is_active": "true",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert limit_resp.status_code == status.HTTP_201_CREATED
    usage_limit = limit_resp.json()
    usage_limit_id = usage_limit["id"]

    list_limits = client.get(
        "/limit-tracking/limits",
        params={"organisation_id": org_id, "limit_type": "check_fraud"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_limits.status_code == status.HTTP_200_OK
    assert any(l["id"] == usage_limit_id for l in list_limits.json())

    now = datetime.now(timezone.utc)
    record_resp = client.post(
        "/limit-tracking/records",
        json={
            "usage_limit_id": usage_limit_id,
            "current_usage": 5.0,
            "period_start": (now - timedelta(days=30)).isoformat(),
            "period_end": now.isoformat(),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert record_resp.status_code == status.HTTP_201_CREATED
    record = record_resp.json()

    list_records = client.get(
        "/limit-tracking/records",
        params={"usage_limit_id": usage_limit_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_records.status_code == status.HTTP_200_OK
    assert any(r["id"] == record["id"] for r in list_records.json())

    user_limit = client.post(
        "/limit-tracking/limits",
        json={
            "user_id": user_id,
            "limit_type": "transactions",
            "limit_value": 100,
            "period": "monthly",
            "is_active": "true",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert user_limit.status_code == status.HTTP_201_CREATED


def test_transactions_create_list_get_and_isolation(client):
    token_a, me_a = _auth_ctx(client, with_org=True)
    token_b, me_b = _auth_ctx(client, with_org=True)

    user_a = me_a["id"]
    org_a = me_a["organisation_id"]
    org_b = me_b["organisation_id"]

    create_resp = client.post(
        "/transactions",
        json={
            "user_id": user_a,
            "organisation_id": org_b,
            "amount": 50,
            "currency": "USD",
            "payment_method": "cc",
            "channel": "web",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    tx = create_resp.json()
    tx_id = tx["id"]
    assert tx["organisation_id"] == org_a

    get_a = client.get(f"/transactions/{tx_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert get_a.status_code == status.HTTP_200_OK

    get_b = client.get(f"/transactions/{tx_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert get_b.status_code == status.HTTP_404_NOT_FOUND

    list_a = client.get("/transactions", headers={"Authorization": f"Bearer {token_a}"})
    assert list_a.status_code == status.HTTP_200_OK
    assert any(t["id"] == tx_id for t in list_a.json())


def test_check_fraud_creates_decision_and_risk_signals_and_routes(client, db):
    fraud_rule_service.seed_default_fraud_rules(db)

    token, me = _auth_ctx(client, with_org=True)
    user_id = me["id"]
    org_id = me["organisation_id"]

    resp = client.post(
        "/check-fraud",
        json={
            "user_id": user_id,
            "organisation_id": 999999,
            "amount": 50,
            "currency": "USD",
            "payment_method": "cc",
            "channel": "web",
            "device_id": "dev_1",
            "transactions_last_24h": 10,
            "failed_attempts_last_24h": 0,
            "metadata": {},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["transaction_id"]
    assert body["decision_id"]
    assert body["decision"] in ("approve", "review", "decline")
    assert body["reason_codes"]

    decisions = client.get("/decisions", headers={"Authorization": f"Bearer {token}"})
    assert decisions.status_code == status.HTTP_200_OK
    assert any(d["id"] == body["decision_id"] for d in decisions.json())

    decision = client.get(
        f"/decisions/{body['decision_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert decision.status_code == status.HTTP_200_OK
    assert decision.json()["id"] == body["decision_id"]

    signals = client.get(
        "/risk-signals",
        params={"transaction_id": body["transaction_id"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert signals.status_code == status.HTTP_200_OK
    sigs = signals.json()
    assert len(sigs) >= 1

    sig_id = sigs[0]["id"]
    sig = client.get(
        f"/risk-signals/{sig_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert sig.status_code == status.HTTP_200_OK
    assert sig.json()["id"] == sig_id


def test_audit_requires_admin_and_exports_csv(client, db):
    fraud_rule_service.seed_default_fraud_rules(db)

    token, me = _auth_ctx(client, with_org=True)

    forbidden = client.get("/audit", headers={"Authorization": f"Bearer {token}"})
    assert forbidden.status_code == status.HTTP_403_FORBIDDEN

    _make_admin(db, user_id=me["id"])

    rule_resp = client.post(
        "/fraud-rules",
        json={
            "name": "Audit Rule",
            "rule_code": f"audit_rule_{uuid.uuid4().hex[:8]}",
            "description": "x",
            "weight": 10,
            "field_name": "transactions_last_24h",
            "operator": "gte",
            "comparison_value": 3,
            "priority": 1,
            "reason_code": "velocity_spike",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rule_resp.status_code == status.HTTP_201_CREATED

    logs = client.get("/audit", headers={"Authorization": f"Bearer {token}"})
    assert logs.status_code == status.HTTP_200_OK
    assert isinstance(logs.json(), list)

    stats_resp = client.get("/audit/stats", headers={"Authorization": f"Bearer {token}"})
    assert stats_resp.status_code == status.HTTP_200_OK
    stats = stats_resp.json()
    assert "event_type_distribution" in stats
    assert "user_activity_counts" in stats

    export_resp = client.get("/audit/export", headers={"Authorization": f"Bearer {token}"})
    assert export_resp.status_code == status.HTTP_200_OK
    assert export_resp.headers["content-type"].startswith("text/csv")
    assert "Content-Disposition" in export_resp.headers
    assert "ID" in export_resp.text


def test_password_reset_request_and_confirm_flow(client):
    email = _email("reset")
    password = "StrongPass123!"
    _register(client, email=email, password=password, organisation_name=f"Org_{uuid.uuid4().hex[:8]}")

    req = client.post("/auth/password-reset/request", json={"email": email})
    assert req.status_code == status.HTTP_200_OK
    body = req.json()
    assert "reset_token" in body

    new_password = "NewStrongPass123!"
    confirm = client.post(
        "/auth/password-reset/confirm",
        json={"token": body["reset_token"], "new_password": new_password},
    )
    assert confirm.status_code == status.HTTP_200_OK

    token = _login(client, email=email, password=new_password)
    assert token


def test_mfa_setup_verify_disable(client):
    token, _ = _auth_ctx(client, with_org=True)

    with patch("services.mfa_service.MFAService.generate_setup_data", return_value=("S3CR3T", "QRDATA")):
        setup = client.post("/mfa/setup", headers={"Authorization": f"Bearer {token}"})
        assert setup.status_code == status.HTTP_200_OK
        assert setup.json()["secret"] == "S3CR3T"
        assert setup.json()["qr_code"] == "QRDATA"

    with patch("services.mfa_service.MFAService.verify_and_enable", return_value=["code1", "code2"]):
        verify = client.post(
            "/mfa/verify",
            json={"secret": "S3CR3T", "code": "123456"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert verify.status_code == status.HTTP_200_OK
        assert verify.json()["backup_codes"] == ["code1", "code2"]

    disable = client.post("/mfa/disable", headers={"Authorization": f"Bearer {token}"})
    assert disable.status_code == status.HTTP_200_OK
    assert "message" in disable.json()
