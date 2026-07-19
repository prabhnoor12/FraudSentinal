import uuid

from cruds import organisation_crud, user_crud
from schemas.decision_schemas import FraudDecision, ReasonCode
from schemas.transaction_schemas import TransactionCreate
from services import fraud_rule_service, scoring_service


def _make_org_and_user(db):
    suffix = uuid.uuid4().hex[:10]
    org = organisation_crud.create_organisation(db, name=f"Velocity Org {suffix}")
    user = user_crud.create_user(db, email=f"velocity_{suffix}@example.com", organisation_id=org.id, password_hash="x")
    return org, user


def _base_payload(*, user_id: int, organisation_id: int, transactions_last_24h: int) -> TransactionCreate:
    return TransactionCreate(
        user_id=user_id,
        organisation_id=organisation_id,
        amount=50.0,
        currency="USD",
        payment_method="cc",
        channel="web",
        device_id="dev_1",
        transactions_last_24h=transactions_last_24h,
        failed_attempts_last_24h=0,
        metadata={},
    )


def test_velocity_no_match_returns_low_signal_profile(db):
    fraud_rule_service.seed_default_fraud_rules(db)
    org, user = _make_org_and_user(db)

    payload = _base_payload(user_id=user.id, organisation_id=org.id, transactions_last_24h=0)
    result = scoring_service.score_transaction(db, payload)

    assert result["risk_score"] == 0.0
    assert result["decision"] == FraudDecision.approve
    assert result["reason_codes"] == [ReasonCode.low_signal_profile]
    assert result["matched_rules"] == []


def test_velocity_spike_level_1_at_3(db):
    fraud_rule_service.seed_default_fraud_rules(db)
    org, user = _make_org_and_user(db)

    payload = _base_payload(user_id=user.id, organisation_id=org.id, transactions_last_24h=3)
    result = scoring_service.score_transaction(db, payload)

    assert result["risk_score"] == 8.0
    assert result["decision"] == FraudDecision.approve
    assert ReasonCode.velocity_spike in result["reason_codes"]
    assert len(result["reason_codes"]) == 1
    assert {r.rule_code for r in result["matched_rules"]} == {"velocity_spike_3"}


def test_velocity_spike_level_2_at_5(db):
    fraud_rule_service.seed_default_fraud_rules(db)
    org, user = _make_org_and_user(db)

    payload = _base_payload(user_id=user.id, organisation_id=org.id, transactions_last_24h=5)
    result = scoring_service.score_transaction(db, payload)

    assert result["risk_score"] == 23.0
    assert result["decision"] == FraudDecision.approve
    assert result["reason_codes"] == [ReasonCode.velocity_spike]
    assert {r.rule_code for r in result["matched_rules"]} == {"velocity_spike_3", "velocity_spike_5"}


def test_velocity_spike_level_3_at_10_triggers_review(db):
    fraud_rule_service.seed_default_fraud_rules(db)
    org, user = _make_org_and_user(db)

    payload = _base_payload(user_id=user.id, organisation_id=org.id, transactions_last_24h=10)
    result = scoring_service.score_transaction(db, payload)

    assert result["risk_score"] == 48.0
    assert result["decision"] == FraudDecision.review
    assert result["reason_codes"] == [ReasonCode.velocity_spike]
    assert {r.rule_code for r in result["matched_rules"]} == {"velocity_spike_3", "velocity_spike_5", "velocity_spike_10"}