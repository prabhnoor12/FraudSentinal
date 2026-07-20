from unittest.mock import patch
import uuid

from cruds import organisation_crud, user_crud
from schemas.decision_schemas import FraudDecision, ReasonCode
from schemas.transaction_schemas import TransactionCreate
from services import fraud_rule_service, ml_fraud_service, scoring_service


def _make_org_and_user(db):
    suffix = uuid.uuid4().hex[:8]
    org = organisation_crud.create_organisation(db, name=f"ML Org {suffix}")
    user = user_crud.create_user(
        db,
        email=f"ml_{suffix}@example.com",
        organisation_id=org.id,
        password_hash="x",
    )
    return org, user


def test_ml_feature_extraction_uses_expected_signals():
    features = ml_fraud_service.extract_features(
        {
            "amount": 1000,
            "transactions_last_24h": 4,
            "failed_attempts_last_24h": 2,
            "account_age_days": 3,
            "ip_billing_country_mismatch": True,
            "is_prepaid": True,
            "bin_risk_score": 60,
            "tx_count_1hour": 3,
            "unique_ips_24hour": 2,
            "new_device": True,
        }
    )

    assert features["amount"] == 1000.0
    assert features["failed_attempts_last_24h"] == 2.0
    assert features["new_device"] == 1.0


def test_ml_predict_returns_bounded_scores():
    result = ml_fraud_service.predict(
        {
            "amount": 2000,
            "transactions_last_24h": 10,
            "failed_attempts_last_24h": 5,
            "account_age_days": 1,
            "ip_billing_country_mismatch": True,
            "is_prepaid": True,
            "bin_risk_score": 90,
            "tx_count_1hour": 6,
            "unique_ips_24hour": 4,
            "new_device": True,
        }
    )

    assert 0 <= result["fraud_probability"] <= 1
    assert 0 <= result["risk_score"] <= 100
    assert result["model_version"] == "heuristic-v1"


def test_score_transaction_combines_rule_and_ml_scores_when_enabled(db):
    fraud_rule_service.seed_default_fraud_rules(db)
    org, user = _make_org_and_user(db)

    payload = TransactionCreate(
        user_id=user.id,
        organisation_id=org.id,
        amount=2000.0,
        currency="USD",
        payment_method="prepaid_card",
        channel="web",
        customer_id="cust-ml",
        device_id="device-ml",
        transactions_last_24h=10,
        failed_attempts_last_24h=2,
        billing_country="US",
        metadata={
            "user_agent": "Mozilla/5.0 Chrome/126 Windows",
            "accept_language": "en-US",
            "accept_encoding": "gzip",
            "screen_resolution": "1920x1080",
            "timezone": "UTC",
        },
    )

    with patch("services.ml_fraud_service.is_ml_scoring_enabled", return_value=True):
        result = scoring_service.score_transaction(db, payload)

    assert result["rule_score"] >= 68.0
    assert result["ml_result"] is not None
    assert result["risk_score"] >= result["rule_score"] * 0.4
    assert result["decision"] in {
        FraudDecision.review,
        FraudDecision.decline,
    }
    assert ReasonCode.high_amount in result["reason_codes"]
