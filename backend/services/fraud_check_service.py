from __future__ import annotations

from datetime import datetime, UTC

from sqlalchemy.orm import Session

from schemas.decision_schemas import DecisionCreate
from schemas.fraud_check_schemas import FraudCheckRequest, FraudCheckResponse
from schemas.risk_signal_schemas import RiskSignalCreate
from services import (
    device_fingerprint_service,
    decision_service,
    entitlement_service,
    fraud_rule_service,
    review_case_service,
    risk_signal_service,
    scoring_service,
    transaction_service,
)


def _build_scoring_snapshot(db: Session, organisation_id: int | None) -> dict:
    """Capture the exact rule configuration at decision time."""
    from schemas.fraud_rule_schemas import FraudRuleOperator

    effective_rules = fraud_rule_service.list_effective_fraud_rules_service(
        db, organisation_id=organisation_id
    )

    snapshot = {
        "captured_at": datetime.now(UTC).isoformat(),
        "organisation_id": organisation_id,
        "rules_version": "v1.0",
        "rules_count": len(effective_rules),
        "rules": [],
    }

    for rule in effective_rules:
        rule_data = {
            "id": rule.id,
            "name": rule.name,
            "rule_code": rule.rule_code,
            "reason_code": rule.reason_code,
            "weight": rule.weight,
            "field_name": rule.field_name,
            "operator": str(rule.operator)
            if isinstance(rule.operator, FraudRuleOperator)
            else rule.operator,
            "comparison_value": rule.comparison_value,
            "secondary_field_name": rule.secondary_field_name,
            "priority": rule.priority,
            "enabled": rule.enabled,
            "organisation_id": rule.organisation_id,
        }
        snapshot["rules"].append(rule_data)

    return snapshot


def check_fraud_service(db: Session, payload: FraudCheckRequest) -> FraudCheckResponse:
    score_result = scoring_service.score_transaction(db, payload)
    transaction_data = score_result.get("evaluated_data") or transaction_service.normalize_transaction_data(payload)

    try:
        transaction = transaction_service.create_transaction_record(
            db, payload, commit=False
        )
        db.flush()

        scoring_snapshot = _build_scoring_snapshot(db, transaction.organisation_id)

        decision = decision_service.create_decision_record(
            db,
            DecisionCreate(
                transaction_id=transaction.id,
                user_id=transaction.user_id,
                organisation_id=transaction.organisation_id,
                risk_score=score_result["risk_score"],
                decision=score_result["decision"],
                reason_codes=score_result["reason_codes"],
                scoring_snapshot=scoring_snapshot,
            ),
            commit=False,
        )
        db.flush()

        for rule in score_result.get("matched_rules", []):
            risk_signal_service.create_risk_signal_service(
                db,
                RiskSignalCreate(
                    transaction_id=transaction.id,
                    decision_id=decision.id,
                    organisation_id=transaction.organisation_id,
                    user_id=transaction.user_id,
                    rule_id=rule.id,
                    rule_code=rule.rule_code,
                    reason_code=rule.reason_code,
                    weight=rule.weight,
                    details={
                        "field_name": rule.field_name,
                        "operator": rule.operator,
                        "comparison_value": rule.comparison_value,
                        "secondary_field_name": rule.secondary_field_name,
                        "matched_value": transaction_data.get(rule.field_name),
                        "secondary_value": transaction_data.get(
                            rule.secondary_field_name
                        )
                        if rule.secondary_field_name
                        else None,
                    },
                ),
                commit=False,
            )

        review_case_service.create_review_case_if_needed(
            db,
            transaction_id=transaction.id,
            decision_id=decision.id,
            organisation_id=transaction.organisation_id,
            user_id=transaction.user_id,
            decision_value=decision.decision,
            commit=False,
        )
        device_fingerprint_service.remember_device_fingerprint(
            db,
            payload,
            commit=False,
        )
        entitlement_service.record_consumption(
            db,
            organisation_id=transaction.organisation_id,
            user_id=transaction.user_id,
            meter_key="fraud_checks",
            units=1.0,
            currency=transaction.currency,
            description=f"Fraud check for transaction {transaction.id}",
            commit=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(transaction)
    db.refresh(decision)

    return FraudCheckResponse(
        transaction_id=transaction.id,
        decision_id=decision.id,
        risk_score=decision.risk_score,
        decision=decision.decision,
        reason_codes=decision.reason_codes or [],
        checked_at=decision.created_at,
    )
