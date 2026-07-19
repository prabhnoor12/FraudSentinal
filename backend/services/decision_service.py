from __future__ import annotations

from sqlalchemy.orm import Session

from cruds import decision_crud, transaction_crud
from schemas.decision_schemas import DecisionCreate, DecisionOut
from utils.exception_handling_utils import NotFoundError


def serialize_decision(decision) -> DecisionOut:
    return DecisionOut(
        id=decision.id,
        transaction_id=decision.transaction_id,
        user_id=decision.user_id,
        organisation_id=decision.organisation_id,
        risk_score=decision.risk_score,
        decision=decision.decision,
        reason_codes=decision.reason_codes or [],
        created_at=decision.created_at,
    )


def create_decision_record(
    db: Session,
    payload: DecisionCreate,
    *,
    commit: bool = True,
):
    if not transaction_crud.get_transaction_by_id(db, payload.transaction_id):
        raise NotFoundError("Transaction not found")
    return decision_crud.create_decision(db, commit=commit, **payload.model_dump())


def get_decision_service(
    db: Session, decision_id: int, organisation_id: int | None = None
) -> DecisionOut:
    decision = decision_crud.get_decision_by_id(db, decision_id)
    if not decision:
        raise NotFoundError("Decision not found")

    if organisation_id is not None and decision.organisation_id != organisation_id:
        raise NotFoundError("Decision not found")

    return serialize_decision(decision)


def list_decisions_service(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
    transaction_id: int | None = None,
    limit: int = 100,
) -> list[DecisionOut]:
    decisions = decision_crud.list_decisions(
        db,
        user_id=user_id,
        organisation_id=organisation_id,
        transaction_id=transaction_id,
        limit=limit,
    )
    return [serialize_decision(decision) for decision in decisions]
