import uuid

from cruds import risk_signal_crud
from schemas.decision_schemas import ReasonCode
from services import fraud_check_service, fraud_rule_service


def _register_and_login(
    client, *, email: str, password: str, organisation_name: str | None
):
    payload = {"email": email, "password": password}
    if organisation_name is not None:
        payload["organisation_name"] = organisation_name

    r = client.post("/auth/register", json=payload)
    assert r.status_code in (200, 201)

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    body = login.json()
    assert "access_token" in body
    token = body["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    return token, me.json()


def test_check_fraud_requires_auth(client):
    resp = client.post(
        "/check-fraud",
        json={
            "user_id": 1,
            "organisation_id": 1,
            "amount": 50,
            "currency": "USD",
            "payment_method": "cc",
            "channel": "web",
        },
    )
    assert resp.status_code == 401


def test_check_fraud_requires_user_assigned_to_org(client):
    suffix = uuid.uuid4().hex[:10]
    email = f"noorg_{suffix}@example.com"
    password = "StrongPass123!"

    token, me = _register_and_login(
        client, email=email, password=password, organisation_name=None
    )
    assert me["organisation_id"] is None

    resp = client.post(
        "/check-fraud",
        json={
            "user_id": me["id"],
            "organisation_id": 9999,
            "amount": 50,
            "currency": "USD",
            "payment_method": "cc",
            "channel": "web",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_check_fraud_velocity_spike_enforces_org_and_creates_risk_signals(client, db):
    fraud_rule_service.seed_default_fraud_rules(db)

    suffix_a = uuid.uuid4().hex[:10]
    email_a = f"velocity_a_{suffix_a}@example.com"
    password = "StrongPass123!"
    token_a, me_a = _register_and_login(
        client, email=email_a, password=password, organisation_name=f"OrgA_{suffix_a}"
    )

    suffix_b = uuid.uuid4().hex[:10]
    email_b = f"velocity_b_{suffix_b}@example.com"
    token_b, me_b = _register_and_login(
        client, email=email_b, password=password, organisation_name=f"OrgB_{suffix_b}"
    )

    resp = client.post(
        "/check-fraud",
        json={
            "user_id": me_a["id"],
            "organisation_id": me_b["organisation_id"],
            "amount": 50,
            "currency": "USD",
            "payment_method": "cc",
            "channel": "web",
            "device_id": "dev_1",
            "transactions_last_24h": 10,
            "failed_attempts_last_24h": 0,
            "metadata": {},
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["decision"] == "review"
    assert body["risk_score"] == 48.0
    assert body["reason_codes"] == [ReasonCode.velocity_spike.value]

    tx_id = body["transaction_id"]

    tx_a = client.get(
        f"/transactions/{tx_id}", headers={"Authorization": f"Bearer {token_a}"}
    )
    assert tx_a.status_code == 200

    tx_b = client.get(
        f"/transactions/{tx_id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert tx_b.status_code == 404

    signals = risk_signal_crud.list_risk_signals(db, transaction_id=tx_id, limit=50)
    assert len(signals) == 3
    assert {s.rule_code for s in signals} == {
        "velocity_spike_3",
        "velocity_spike_5",
        "velocity_spike_10",
    }
    assert {s.reason_code for s in signals} == {ReasonCode.velocity_spike.value}


def test_check_fraud_low_signal_profile_when_no_rules_match(client, db):
    fraud_rule_service.seed_default_fraud_rules(db)

    suffix = uuid.uuid4().hex[:10]
    email = f"low_signal_{suffix}@example.com"
    password = "StrongPass123!"
    token, me = _register_and_login(
        client, email=email, password=password, organisation_name=f"Org_{suffix}"
    )

    resp = client.post(
        "/check-fraud",
        json={
            "user_id": me["id"],
            "organisation_id": me["organisation_id"],
            "amount": 50,
            "currency": "USD",
            "payment_method": "cc",
            "channel": "web",
            "device_id": "dev_1",
            "transactions_last_24h": 0,
            "failed_attempts_last_24h": 0,
            "metadata": {},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["decision"] == "approve"
    assert body["risk_score"] == 0.0
    assert body["reason_codes"] == [ReasonCode.low_signal_profile.value]


def test_build_scoring_snapshot_includes_effective_rules(db):
    fraud_rule_service.seed_default_fraud_rules(db)

    snapshot = fraud_check_service._build_scoring_snapshot(db, organisation_id=None)

    assert snapshot["rules_version"] == "v1.0"
    assert snapshot["rules_count"] == len(snapshot["rules"])
    codes = {r["rule_code"] for r in snapshot["rules"]}
    assert {"velocity_spike_3", "velocity_spike_5", "velocity_spike_10"}.issubset(codes)
