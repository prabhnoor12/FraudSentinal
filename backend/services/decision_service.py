from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from cruds import decision_crud, transaction_crud
from schemas.decision_schemas import DecisionCreate, DecisionOut, DecisionReplayOut
from services import scoring_service
from utils.exception_handling_utils import NotFoundError, ValidationError


def serialize_decision(decision) -> DecisionOut:
    return DecisionOut(
        id=decision.id,
        transaction_id=decision.transaction_id,
        user_id=decision.user_id,
        organisation_id=decision.organisation_id,
        risk_score=decision.risk_score,
        decision=decision.decision,
        reason_codes=decision.reason_codes or [],
        scoring_snapshot=decision.scoring_snapshot or {},
        created_at=decision.created_at,
    )


def _ensure_transaction_matches_decision_payload(
    db: Session, payload: DecisionCreate
) -> None:
    transaction = transaction_crud.get_transaction_by_id(db, payload.transaction_id)
    if not transaction:
        raise NotFoundError("Transaction not found")

    if transaction.organisation_id != payload.organisation_id:
        raise ValidationError("Transaction does not belong to the target organisation")

    if transaction.user_id != payload.user_id:
        raise ValidationError("Transaction does not belong to the target user")


def create_decision_record(
    db: Session,
    payload: DecisionCreate,
    *,
    commit: bool = True,
):
    _ensure_transaction_matches_decision_payload(db, payload)
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
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> tuple[list[DecisionOut], int]:
    decisions = decision_crud.list_decisions(
        db,
        user_id=user_id,
        organisation_id=organisation_id,
        transaction_id=transaction_id,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    total = decision_crud.count_decisions(
        db,
        user_id=user_id,
        organisation_id=organisation_id,
        transaction_id=transaction_id,
    )
    return [serialize_decision(decision) for decision in decisions], total


def replay_decision_service(
    db: Session,
    decision_id: int,
    *,
    organisation_id: int | None = None,
) -> DecisionReplayOut:
    decision = decision_crud.get_decision_by_id(db, decision_id)
    if not decision:
        raise NotFoundError("Decision not found")
    if organisation_id is not None and decision.organisation_id != organisation_id:
        raise NotFoundError("Decision not found")

    snapshot = dict(decision.scoring_snapshot or {})
    if not snapshot:
        raise ValidationError("Decision does not contain a replayable scoring snapshot")

    replay_result = scoring_service.replay_scoring_snapshot(snapshot)
    original_summary = snapshot.get("decision_summary") or {}
    original_decision = original_summary.get("decision") or decision.decision

    return DecisionReplayOut(
        decision_id=decision.id,
        transaction_id=decision.transaction_id,
        organisation_id=decision.organisation_id,
        original_decision=original_decision,
        replayed_decision=replay_result["decision"],
        original_risk_score=float(original_summary.get("risk_score", decision.risk_score)),
        replayed_risk_score=float(replay_result["risk_score"]),
        original_rule_score=float(original_summary.get("rule_score", replay_result["rule_score"])),
        replayed_rule_score=float(replay_result["rule_score"]),
        matches_original_decision=bool(
            replay_result["replay"].get("matches_original_decision", False)
            and replay_result["decision"].value == original_decision
        ),
        replay=replay_result["replay"],
        scoring_snapshot=snapshot,
        replayed_at=datetime.now(UTC),
    )
