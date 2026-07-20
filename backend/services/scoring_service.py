from __future__ import annotations

from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session

from schemas.decision_schemas import FraudDecision, ReasonCode
from schemas.fraud_rule_schemas import FraudRuleOperator
from schemas.transaction_schemas import TransactionCreate
from services import (
    device_fingerprint_service,
    fraud_rule_service,
    transaction_service,
    velocity_service,
)


def _is_missing(value) -> bool:
    return value in {None, ""} or value == [] or value == {}


def _freeze_value(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze_value(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze_value(item) for item in value))
    return value


def _matches_rule_values(
    operator: FraudRuleOperator,
    candidate: Any,
    comparison_value: Any,
    secondary_value: Any = None,
) -> bool:
    if operator == FraudRuleOperator.is_missing:
        return _is_missing(candidate)

    if operator == FraudRuleOperator.field_mismatch:
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


@lru_cache(maxsize=10000)
def _evaluate_rule_cached(
    operator_value: str,
    candidate: Any,
    comparison_value: Any,
    secondary_value: Any,
) -> bool:
    return _matches_rule_values(
        FraudRuleOperator(operator_value),
        candidate,
        comparison_value,
        secondary_value,
    )


def _matches_rule(rule, transaction_data: dict) -> bool:
    candidate = _freeze_value(transaction_data.get(rule.field_name))
    secondary_value = _freeze_value(
        transaction_data.get(rule.secondary_field_name)
        if rule.secondary_field_name
        else None
    )
    comparison_value = _freeze_value(rule.comparison_value)
    return _evaluate_rule_cached(
        str(rule.operator),
        candidate,
        comparison_value,
        secondary_value,
    )


def _build_rule_index(rules) -> dict[str, list]:
    rule_index: dict[str, list] = {}
    for rule in rules:
        rule_index.setdefault(rule.field_name, []).append(rule)
        if rule.secondary_field_name:
            rule_index.setdefault(rule.secondary_field_name, []).append(rule)
    return rule_index


def _get_relevant_rules(effective_rules, transaction_data: dict) -> list:
    rule_index = _build_rule_index(effective_rules)
    relevant_rules: dict[int, object] = {}

    for field_name in transaction_data.keys():
        for rule in rule_index.get(field_name, []):
            relevant_rules[rule.id] = rule

    return sorted(
        relevant_rules.values(),
        key=lambda rule: (rule.priority, rule.id),
    )


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
    velocity_signals = velocity_service.get_velocity_signals(db, payload)
    transaction_data.update(velocity_signals)
    device_signals = device_fingerprint_service.get_device_signals(db, payload)
    transaction_data.update(device_signals)

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

    for rule in _get_relevant_rules(effective_rules, transaction_data):
        if _matches_rule(rule, transaction_data):
            matched_rules.append(rule)
            total_score += float(rule.weight)
            reason_code = ReasonCode(rule.reason_code)
            if reason_code not in reason_codes:
                reason_codes.append(reason_code)
            if total_score >= decline_threshold:
                break

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
        "evaluated_data": transaction_data,
    }
