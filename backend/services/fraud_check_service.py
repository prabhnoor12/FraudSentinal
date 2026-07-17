from __future__ import annotations

from sqlalchemy.orm import Session

from schemas.decision_schemas import DecisionCreate
from schemas.fraud_check_schemas import FraudCheckRequest, FraudCheckResponse
from services import decision_service, scoring_service, transaction_service


def check_fraud_service(db: Session, payload: FraudCheckRequest) -> FraudCheckResponse:
    score_result = scoring_service.score_transaction(db, payload)

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
