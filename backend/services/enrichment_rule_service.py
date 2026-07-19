"""Fraud rules based on signal enrichment (IP geolocation + BIN lookup).

This module provides pre-built fraud rules that use enriched transaction data
to detect high-risk patterns like geolocation mismatches and risky BINs.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from schemas.fraud_rule_schemas import FraudRuleField, FraudRuleOperator, ReasonCode
from services import fraud_rule_service


# Rule weight constants
WEIGHT_GEOLOCATION_MISMATCH = 30
WEIGHT_BIN_COUNTRY_MISMATCH = 25
WEIGHT_HIGH_RISK_BIN = 40
WEIGHT_PREPAID_CARD = 20
WEIGHT_COMMERCIAL_CARD = 15
WEIGHT_IP_HIGH_RISK_COUNTRY = 35


def create_geolocation_mismatch_rule(
    db: Session, organisation_id: int | None = None
) -> Any:
    """Create rule for IP geolocation vs billing country mismatch.

    This detects when a transaction comes from an IP in one country
    but the billing address is in another - a common fraud pattern.
    """
    rule_code = "geolocation_billing_mismatch"

    # Check if rule already exists
    existing = fraud_rule_service.get_fraud_rule_by_code_service(
        db, rule_code, organisation_id
    )
    if existing:
        return existing

    from schemas.fraud_rule_schemas import FraudRuleCreate

    rule_data = FraudRuleCreate(
        name="Geolocation-Billing Country Mismatch",
        rule_code=rule_code,
        description="Flags transactions where IP geolocation country differs from billing country. High fraud risk indicator.",
        organisation_id=organisation_id,
        reason_code=ReasonCode.cross_border_mismatch,
        weight=WEIGHT_GEOLOCATION_MISMATCH,
        field_name=FraudRuleField.ip_country_code,  # Would need to add this field
        operator=FraudRuleOperator.field_mismatch,
        secondary_field_name=FraudRuleField.billing_country,
        priority=50,
    )

    return fraud_rule_service.create_fraud_rule_service(db, rule_data)


def create_bin_country_mismatch_rule(
    db: Session, organisation_id: int | None = None
) -> Any:
    """Create rule for BIN issuing country vs billing country mismatch.

    Detects when a card was issued in one country but billing address
    is in another - potential stolen card or fraud.
    """
    rule_code = "bin_billing_country_mismatch"

    existing = fraud_rule_service.get_fraud_rule_by_code_service(
        db, rule_code, organisation_id
    )
    if existing:
        return existing

    from schemas.fraud_rule_schemas import FraudRuleCreate

    rule_data = FraudRuleCreate(
        name="BIN-Billing Country Mismatch",
        rule_code=rule_code,
        description="Flags transactions where card issuing country differs from billing country. Indicates potential stolen card usage.",
        organisation_id=organisation_id,
        reason_code=ReasonCode.cross_border_mismatch,
        weight=WEIGHT_BIN_COUNTRY_MISMATCH,
        field_name=FraudRuleField.issuing_country_code,  # Would need to add this field
        operator=FraudRuleOperator.field_mismatch,
        secondary_field_name=FraudRuleField.billing_country,
        priority=60,
    )

    return fraud_rule_service.create_fraud_rule_service(db, rule_data)


def create_high_risk_bin_rule(db: Session, organisation_id: int | None = None) -> Any:
    """Create rule for high-risk BIN detection.

    Flags transactions using cards with elevated risk scores,
    typically prepaid cards or cards from high-fraud regions.
    """
    rule_code = "high_risk_bin"

    existing = fraud_rule_service.get_fraud_rule_by_code_service(
        db, rule_code, organisation_id
    )
    if existing:
        return existing

    from schemas.fraud_rule_schemas import FraudRuleCreate

    rule_data = FraudRuleCreate(
        name="High Risk BIN",
        rule_code=rule_code,
        description="Flags transactions using cards with elevated risk scores. Prepaid cards and cards from high-fraud regions are typically flagged.",
        organisation_id=organisation_id,
        reason_code=ReasonCode.risky_payment_method,
        weight=WEIGHT_HIGH_RISK_BIN,
        field_name=FraudRuleField.bin_risk_score,  # Would need to add this field
        operator=FraudRuleOperator.gte,
        comparison_value=50,  # Risk score >= 50 is high risk
        priority=70,
    )

    return fraud_rule_service.create_fraud_rule_service(db, rule_data)


def create_prepaid_card_rule(db: Session, organisation_id: int | None = None) -> Any:
    """Create rule for prepaid card detection.

    Prepaid cards are often used in fraud because they're anonymous
    and can be purchased with cash.
    """
    rule_code = "prepaid_card"

    existing = fraud_rule_service.get_fraud_rule_by_code_service(
        db, rule_code, organisation_id
    )
    if existing:
        return existing

    from schemas.fraud_rule_schemas import FraudRuleCreate

    rule_data = FraudRuleCreate(
        name="Prepaid Card",
        rule_code=rule_code,
        description="Flags transactions using prepaid cards. Prepaid cards are often used in fraud due to their anonymity and cash purchase capability.",
        organisation_id=organisation_id,
        reason_code=ReasonCode.risky_payment_method,
        weight=WEIGHT_PREPAID_CARD,
        field_name=FraudRuleField.is_prepaid,  # Would need to add this field
        operator=FraudRuleOperator.eq,
        comparison_value=True,
        priority=65,
    )

    return fraud_rule_service.create_fraud_rule_service(db, rule_data)


def seed_all_enrichment_rules(db: Session, organisation_id: int | None = None) -> dict:
    """Seed all enrichment-based fraud rules.

    Returns:
        Dict with created rules and any errors.
    """
    rules = {}
    errors = []

    rule_functions = [
        ("geolocation_mismatch", create_geolocation_mismatch_rule),
        ("bin_country_mismatch", create_bin_country_mismatch_rule),
        ("high_risk_bin", create_high_risk_bin_rule),
        ("prepaid_card", create_prepaid_card_rule),
    ]

    for rule_name, rule_func in rule_functions:
        try:
            rule = rule_func(db, organisation_id)
            rules[rule_name] = rule
        except Exception as e:
            errors.append(f"{rule_name}: {str(e)}")

    return {
        "created": len(rules),
        "rules": rules,
        "errors": errors,
    }
