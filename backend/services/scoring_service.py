from __future__ import annotations

from sqlalchemy.orm import Session

from schemas.decision_schemas import FraudDecision, ReasonCode
from schemas.fraud_rule_schemas import FraudRuleOperator
from schemas.transaction_schemas import TransactionCreate
from services import fraud_rule_service, transaction_service


def _is_missing(value) -> bool:
    return value in {None, ""} or value == [] or value == {}


def _matches_rule(rule, transaction_data: dict) -> bool:
    operator = FraudRuleOperator(rule.operator)
    candidate = transaction_data.get(rule.field_name)
    comparison_value = rule.comparison_value

    if operator == FraudRuleOperator.is_missing:
        return _is_missing(candidate)

    if operator == FraudRuleOperator.field_mismatch:
        secondary_value = transaction_data.get(rule.secondary_field_name)
        if _is_missing(candidate) or _is_missing(secondary_value):
            return False
        return candidate != secondary_value

    if _is_missing(candidate):
        return False

    if operator == FraudRuleOperator.gte:
        return candidate >= comparison_value
    if operator == FraudRuleOperator.gt:
        return candidate > comparison_value
    if operator == FraudRuleOperator.lte:
        return candidate <= comparison_value
    if operator == FraudRuleOperator.lt:
        return candidate < comparison_value
    if operator == FraudRuleOperator.eq:
        return candidate == comparison_value
    if operator == FraudRuleOperator.neq:
        return candidate != comparison_value
    if operator == FraudRuleOperator.in_list:
        return candidate in comparison_value
    if operator == FraudRuleOperator.not_in:
        return candidate not in comparison_value

    return False


def score_transaction(db: Session, payload: TransactionCreate) -> dict:
    # Get enrichment data if IP or card number present
    from services.enrichment_service import get_enriched_transaction_data

    enrichment_data = get_enriched_transaction_data(
        db,
        ip_address=payload.ip_address if hasattr(payload, "ip_address") else None,
        card_number=payload.card_number if hasattr(payload, "card_number") else None,
        billing_country=payload.billing_country
        if hasattr(payload, "billing_country")
        else None,
    )

    # Merge enrichment data with transaction data for rule evaluation
    transaction_data = transaction_service.normalize_transaction_data_with_enrichment(
        payload, enrichment_data
    )

    effective_rules = fraud_rule_service.list_effective_fraud_rules_service(
        db,
        organisation_id=payload.organisation_id,
    )

    # Load organisation settings for custom thresholds
    from services.settings_service import get_settings_service

    try:
        settings = get_settings_service(db, payload.organisation_id)
        review_threshold = settings.review_threshold
        decline_threshold = settings.decline_threshold
    except Exception:
        review_threshold = 40
        decline_threshold = 70

    matched_rules = []
    reason_codes: list[ReasonCode] = []
    total_score = 0.0

    for rule in effective_rules:
        if _matches_rule(rule, transaction_data):
            matched_rules.append(rule)
            total_score += float(rule.weight)
            reason_code = ReasonCode(rule.reason_code)
            if reason_code not in reason_codes:
                reason_codes.append(reason_code)

    risk_score = min(round(total_score, 2), 100.0)
    if risk_score >= decline_threshold:
        decision = FraudDecision.decline
    elif risk_score >= review_threshold:
        decision = FraudDecision.review
    else:
        decision = FraudDecision.approve

    if not reason_codes:
        reason_codes.append(ReasonCode.low_signal_profile)

    return {
        "risk_score": risk_score,
        "decision": decision,
        "reason_codes": reason_codes,
        "matched_rules": matched_rules,
    }
