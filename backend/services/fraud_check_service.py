from __future__ import annotations

from sqlalchemy.orm import Session

from schemas.decision_schemas import DecisionCreate
from schemas.fraud_check_schemas import FraudCheckRequest, FraudCheckResponse
from schemas.risk_signal_schemas import RiskSignalCreate
from services import decision_service, review_case_service, risk_signal_service, scoring_service, transaction_service


def check_fraud_service(db: Session, payload: FraudCheckRequest) -> FraudCheckResponse:
    score_result = scoring_service.score_transaction(db, payload)
    transaction_data = transaction_service.normalize_transaction_data(payload)

    try:
        transaction = transaction_service.create_transaction_record(db, payload, commit=False)
        db.flush()

        decision = decision_service.create_decision_record(
            db,
            DecisionCreate(
                transaction_id=transaction.id,
                user_id=transaction.user_id,
                organisation_id=transaction.organisation_id,
                risk_score=score_result["risk_score"],
                decision=score_result["decision"],
                reason_codes=score_result["reason_codes"],
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
                        "secondary_value": transaction_data.get(rule.secondary_field_name) if rule.secondary_field_name else None,
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
