from unittest.mock import MagicMock, patch
import uuid

from cruds import fraud_rule_crud, organisation_crud, settings_crud, user_crud
from schemas.decision_schemas import FraudDecision, ReasonCode
from schemas.fraud_rule_schemas import (
    FraudRuleCreate,
    FraudRuleField,
    FraudRuleOperator,
)
from schemas.transaction_schemas import TransactionCreate
from services import enrichment_service, fraud_rule_service, scoring_service


def _make_org_and_user(db):
    suffix = uuid.uuid4().hex[:8]
    org = organisation_crud.create_organisation(db, name=f"Optimized Org {suffix}")
    user = user_crud.create_user(
        db,
        email=f"optimized_{suffix}@example.com",
        organisation_id=org.id,
        password_hash="x",
    )
    return org, user


def test_effective_rule_cache_reuses_results_and_invalidates_on_change(db):
    org, _ = _make_org_and_user(db)
    fraud_rule_service.seed_default_fraud_rules(db)

    with patch(
        "services.fraud_rule_service.fraud_rule_crud.list_effective_fraud_rules",
        wraps=fraud_rule_crud.list_effective_fraud_rules,
    ) as mocked_list:
        first = fraud_rule_service.list_effective_fraud_rules_service(
            db,
            organisation_id=org.id,
        )
        second = fraud_rule_service.list_effective_fraud_rules_service(
            db,
            organisation_id=org.id,
        )

        assert first
        assert len(first) == len(second)
        assert mocked_list.call_count == 1

        fraud_rule_service.create_fraud_rule_service(
            db,
            payload=FraudRuleCreate(
                name="Org fast rule",
                rule_code="org_fast_rule",
                description="Invalidate cache after create",
                organisation_id=org.id,
                reason_code=ReasonCode.velocity_spike,
                weight=12,
                field_name=FraudRuleField.transactions_last_24h,
                operator=FraudRuleOperator.gte,
                comparison_value=1,
                secondary_field_name=None,
                enabled=True,
                priority=5,
            ),
        )

        refreshed = fraud_rule_service.list_effective_fraud_rules_service(
            db,
            organisation_id=org.id,
        )

        assert any(rule.rule_code == "org_fast_rule" for rule in refreshed)
        assert mocked_list.call_count == 2


def test_score_transaction_uses_early_exit_once_decline_threshold_is_hit(db):
    org, user = _make_org_and_user(db)
    settings_crud.create_settings(
        db,
        organisation_id=org.id,
        currency="USD",
        timezone="UTC",
        review_threshold=40,
        decline_threshold=50,
        enable_billing=True,
        enable_usage_tracking=True,
        notification_email=None,
        notes=None,
    )

    fraud_rule_crud.create_fraud_rule(
        db,
        name="Decline rule one",
        rule_code="decline_rule_one",
        description="First declining rule",
        organisation_id=org.id,
        reason_code=ReasonCode.high_amount,
        weight=30,
        field_name=FraudRuleField.amount,
        operator=FraudRuleOperator.gte,
        comparison_value=10,
        secondary_field_name=None,
        enabled=True,
        priority=1,
    )
    fraud_rule_crud.create_fraud_rule(
        db,
        name="Decline rule two",
        rule_code="decline_rule_two",
        description="Second declining rule",
        organisation_id=org.id,
        reason_code=ReasonCode.velocity_spike,
        weight=25,
        field_name=FraudRuleField.amount,
        operator=FraudRuleOperator.gte,
        comparison_value=20,
        secondary_field_name=None,
        enabled=True,
        priority=2,
    )
    fraud_rule_crud.create_fraud_rule(
        db,
        name="Should not run",
        rule_code="decline_rule_three",
        description="Would only match without early exit",
        organisation_id=org.id,
        reason_code=ReasonCode.new_account,
        weight=10,
        field_name=FraudRuleField.amount,
        operator=FraudRuleOperator.gte,
        comparison_value=1,
        secondary_field_name=None,
        enabled=True,
        priority=999,
    )
    fraud_rule_service.invalidate_effective_rule_cache(org.id)

    payload = TransactionCreate(
        user_id=user.id,
        organisation_id=org.id,
        amount=100.0,
        currency="USD",
        payment_method="cc",
        channel="web",
        device_id="device-1",
        metadata={},
    )

    result = scoring_service.score_transaction(db, payload)

    assert result["risk_score"] == 55.0
    assert result["decision"] == FraudDecision.decline
    assert {rule.rule_code for rule in result["matched_rules"]} == {
        "decline_rule_one",
        "decline_rule_two",
    }


def test_ip_enrichment_lookup_uses_cache(db):
    mock_geo = MagicMock()
    mock_geo.country_code = "US"
    mock_geo.region = "CA"
    mock_geo.city = "Mountain View"
    mock_geo.latitude = "37.386"
    mock_geo.longitude = "-122.0838"
    mock_geo.isp = "Google"

    with patch(
        "services.enrichment_service.ip_geolocation_crud.get_geolocation_by_ip",
        return_value=mock_geo,
    ) as mocked_lookup:
        first = enrichment_service.get_enriched_transaction_data(
            db,
            ip_address="8.8.8.8",
            card_number=None,
            billing_country="US",
        )
        second = enrichment_service.get_enriched_transaction_data(
            db,
            ip_address="8.8.8.8",
            card_number=None,
            billing_country="US",
        )

    assert first["ip_country_code"] == "US"
    assert second["ip_country_code"] == "US"
    assert mocked_lookup.call_count == 1


def test_bin_enrichment_lookup_uses_cache_and_exposes_card_category(db):
    mock_bin = MagicMock()
    mock_bin.bin_number = "424242"
    mock_bin.card_brand = "Visa"
    mock_bin.card_type = "Credit"
    mock_bin.card_category = "Gold"
    mock_bin.issuing_bank = "Chase"
    mock_bin.issuing_country_code = "US"
    mock_bin.is_prepaid = False
    mock_bin.is_commercial = False
    mock_bin.risk_score = 12

    with patch(
        "services.enrichment_service.bin_lookup_crud.get_bin_by_card_number",
        return_value=mock_bin,
    ) as mocked_lookup:
        first = enrichment_service.get_enriched_transaction_data(
            db,
            ip_address=None,
            card_number="4242424242424242",
            billing_country="US",
        )
        second = enrichment_service.get_enriched_transaction_data(
            db,
            ip_address=None,
            card_number="4242424242424242",
            billing_country="US",
        )

    assert first["card_brand"] == "Visa"
    assert first["card_category"] == "Gold"
    assert second["card_category"] == "Gold"
    assert mocked_lookup.call_count == 1
