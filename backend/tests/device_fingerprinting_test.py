import uuid

from cruds import device_fingerprint_crud
from schemas.decision_schemas import FraudDecision, ReasonCode
from schemas.transaction_schemas import TransactionCreate
from services import device_fingerprint_service, fraud_rule_service, scoring_service


def _register_and_login(
    client, *, email: str, password: str, organisation_name: str | None
):
    payload = {"email": email, "password": password}
    if organisation_name is not None:
        payload["organisation_name"] = organisation_name

    register_response = client.post("/auth/register", json=payload)
    assert register_response.status_code in (200, 201)

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    return token, me_response.json()


def _device_payload(*, user_id: int, organisation_id: int, device_id: str, user_agent: str):
    return TransactionCreate(
        user_id=user_id,
        organisation_id=organisation_id,
        amount=75.0,
        currency="USD",
        payment_method="cc",
        channel="web",
        customer_id="cust-device-1",
        device_id=device_id,
        metadata={
            "user_agent": user_agent,
            "accept_language": "en-US",
            "accept_encoding": "gzip",
            "screen_resolution": "1920x1080",
            "timezone": "UTC",
        },
    )


def test_device_fingerprint_signals_detect_new_device_after_baseline(db, client):
    fraud_rule_service.seed_default_fraud_rules(db)
    suffix = uuid.uuid4().hex[:8]
    _, me = _register_and_login(
        client,
        email=f"device_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"DeviceOrg_{suffix}",
    )

    baseline = _device_payload(
        user_id=me["id"],
        organisation_id=me["organisation_id"],
        device_id="device-known",
        user_agent="Mozilla/5.0 Chrome/126 Windows",
    )
    device_fingerprint_service.remember_device_fingerprint(db, baseline)

    same_device_signals = device_fingerprint_service.get_device_signals(db, baseline)
    assert same_device_signals["new_device"] is False
    assert same_device_signals["known_devices_count"] == 1

    new_device_payload = _device_payload(
        user_id=me["id"],
        organisation_id=me["organisation_id"],
        device_id="device-new",
        user_agent="Mozilla/5.0 Firefox/127 Windows",
    )
    new_device_signals = device_fingerprint_service.get_device_signals(db, new_device_payload)

    assert new_device_signals["new_device"] is True
    assert new_device_signals["known_devices_count"] == 1
    assert float(new_device_signals["device_fingerprint_confidence"]) > 0


def test_score_transaction_flags_new_device_rule(db, client):
    fraud_rule_service.seed_default_fraud_rules(db)
    suffix = uuid.uuid4().hex[:8]
    _, me = _register_and_login(
        client,
        email=f"score_device_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"ScoreDeviceOrg_{suffix}",
    )

    device_fingerprint_service.remember_device_fingerprint(
        db,
        _device_payload(
            user_id=me["id"],
            organisation_id=me["organisation_id"],
            device_id="device-known",
            user_agent="Mozilla/5.0 Chrome/126 Windows",
        ),
    )

    result = scoring_service.score_transaction(
        db,
        _device_payload(
            user_id=me["id"],
            organisation_id=me["organisation_id"],
            device_id="device-suspicious",
            user_agent="Mozilla/5.0 Firefox/127 Windows",
        ),
    )

    assert result["decision"] == FraudDecision.approve
    assert result["risk_score"] == 25.0
    assert result["reason_codes"] == [ReasonCode.new_device]
    assert {rule.rule_code for rule in result["matched_rules"]} == {"new_device_detected"}


def test_check_fraud_persists_device_fingerprint_and_scores_new_device(client, db):
    fraud_rule_service.seed_default_fraud_rules(db)
    suffix = uuid.uuid4().hex[:8]
    token, me = _register_and_login(
        client,
        email=f"persist_device_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"PersistDeviceOrg_{suffix}",
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 Chrome/126 Windows",
        "Accept-Language": "en-US",
        "Accept-Encoding": "gzip",
    }
    first_response = client.post(
        "/check-fraud",
        json={
            "user_id": me["id"],
            "organisation_id": me["organisation_id"],
            "amount": 50,
            "currency": "USD",
            "payment_method": "cc",
            "channel": "web",
            "customer_id": "cust-device-2",
            "device_id": "browser-a",
            "metadata": {"screen_resolution": "1920x1080", "timezone": "UTC"},
        },
        headers=headers,
    )
    assert first_response.status_code == 200
    assert first_response.json()["decision"] == FraudDecision.approve.value

    second_response = client.post(
        "/check-fraud",
        json={
            "user_id": me["id"],
            "organisation_id": me["organisation_id"],
            "amount": 50,
            "currency": "USD",
            "payment_method": "cc",
            "channel": "web",
            "customer_id": "cust-device-2",
            "device_id": "browser-b",
            "metadata": {"screen_resolution": "1366x768", "timezone": "UTC"},
        },
        headers={
            **headers,
            "User-Agent": "Mozilla/5.0 Firefox/127 Windows",
        },
    )
    assert second_response.status_code == 200
    body = second_response.json()
    assert body["risk_score"] == 25.0
    assert body["reason_codes"] == [ReasonCode.new_device.value]

    known_devices = device_fingerprint_crud.list_known_device_fingerprints(
        db,
        organisation_id=me["organisation_id"],
        user_id=me["id"],
        customer_id="cust-device-2",
    )
    assert len(known_devices) == 2
