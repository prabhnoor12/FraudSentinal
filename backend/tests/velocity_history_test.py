from datetime import UTC, datetime, timedelta
import uuid

from cruds import risk_signal_crud, transaction_crud
from schemas.decision_schemas import FraudDecision, ReasonCode
from schemas.transaction_schemas import TransactionCreate
from services import fraud_rule_service, scoring_service


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


def _seed_transaction_history(
    db,
    *,
    user_id: int,
    organisation_id: int,
    customer_id: str,
    amount: float,
    ip_address: str,
    created_at: datetime,
):
    transaction_crud.create_transaction(
        db,
        user_id=user_id,
        organisation_id=organisation_id,
        external_transaction_id=None,
        amount=amount,
        currency="USD",
        payment_method="cc",
        channel="web",
        customer_id=customer_id,
        customer_email=None,
        billing_country=None,
        shipping_country=None,
        ip_address=ip_address,
        device_id="history-device",
        account_age_days=None,
        transactions_last_24h=0,
        failed_attempts_last_24h=0,
        metadata={},
        created_at=created_at,
    )


def test_score_transaction_uses_persisted_velocity_history(db, client):
    fraud_rule_service.seed_default_fraud_rules(db)

    suffix = uuid.uuid4().hex[:8]
    token, me = _register_and_login(
        client,
        email=f"history_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"HistoryOrg_{suffix}",
    )
    assert token

    now = datetime.now(UTC)
    customer_id = "cust-history-1"
    _seed_transaction_history(
        db,
        user_id=me["id"],
        organisation_id=me["organisation_id"],
        customer_id=customer_id,
        amount=120.0,
        ip_address="10.0.0.1",
        created_at=now - timedelta(minutes=30),
    )
    _seed_transaction_history(
        db,
        user_id=me["id"],
        organisation_id=me["organisation_id"],
        customer_id=customer_id,
        amount=130.0,
        ip_address="10.0.0.1",
        created_at=now - timedelta(minutes=10),
    )

    payload = TransactionCreate(
        user_id=me["id"],
        organisation_id=me["organisation_id"],
        amount=140.0,
        currency="USD",
        payment_method="cc",
        channel="web",
        customer_id=customer_id,
        ip_address="10.0.0.1",
        device_id="device-1",
        metadata={},    
    )

    result = scoring_service.score_transaction(db, payload)

    assert result["decision"] == FraudDecision.approve
    assert result["risk_score"] == 20.0
    assert result["reason_codes"] == [ReasonCode.velocity_spike]
    assert result["evaluated_data"]["tx_count_1hour"] == 3
    assert result["evaluated_data"]["transactions_last_24h"] == 3
    assert {rule.rule_code for rule in result["matched_rules"]} == {
        "velocity_spike_3",
        "velocity_spike_1hour_3",
    }


def test_check_fraud_creates_velocity_history_risk_signals(client, db):
    fraud_rule_service.seed_default_fraud_rules(db)

    suffix = uuid.uuid4().hex[:8]
    token, me = _register_and_login(
        client,
        email=f"velocityhistory_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"VelocityHistoryOrg_{suffix}",
    )

    now = datetime.now(UTC)
    customer_id = "cust-history-2"
    _seed_transaction_history(
        db,
        user_id=me["id"],
        organisation_id=me["organisation_id"],
        customer_id=customer_id,
        amount=400.0,
        ip_address="10.0.0.1",
        created_at=now - timedelta(minutes=45),
    )
    _seed_transaction_history(
        db,
        user_id=me["id"],
        organisation_id=me["organisation_id"],
        customer_id=customer_id,
        amount=400.0,
        ip_address="10.0.0.2",
        created_at=now - timedelta(minutes=20),
    )

    response = client.post(
        "/check-fraud",
        json={
            "user_id": me["id"],
            "organisation_id": me["organisation_id"],
            "amount": 300,
            "currency": "USD",
            "payment_method": "cc",
            "channel": "web",
            "customer_id": customer_id,
            "ip_address": "10.0.0.3",
            "device_id": "velocity-device",
            "transactions_last_24h": 0,
            "failed_attempts_last_24h": 0,
            "metadata": {},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == FraudDecision.review.value
    assert body["risk_score"] == 47.0
    assert set(body["reason_codes"]) == {
        ReasonCode.velocity_spike.value,
        ReasonCode.high_amount.value,
    }

    signals = risk_signal_crud.list_risk_signals(
        db,
        transaction_id=body["transaction_id"],
        limit=20,
    )
    assert {signal.rule_code for signal in signals} == {
        "velocity_spike_3",
        "velocity_spike_1hour_3",
        "velocity_ip_diversity_24hour_3",
        "velocity_amount_24hour_1000",
    }
