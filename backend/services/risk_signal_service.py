from __future__ import annotations

from sqlalchemy.orm import Session

from cruds import decision_crud, risk_signal_crud, transaction_crud
from schemas.risk_signal_schemas import RiskSignalCreate
from utils.exception_handling_utils import NotFoundError, ValidationError
from utils.ownership_utils import require_decision_in_organisation, require_transaction_in_organisation


def _ensure_signal_owners_exist(
    db: Session, *, transaction_id: int, decision_id: int
) -> None:
    transaction = transaction_crud.get_transaction_by_id(db, transaction_id)
    if not transaction:
        raise NotFoundError("Transaction not found")

    decision = decision_crud.get_decision_by_id(db, decision_id)
    if not decision:
        raise NotFoundError("Decision not found")

    if decision.transaction_id != transaction.id:
        raise ValidationError("Decision does not belong to the transaction")


def create_risk_signal_service(
    db: Session, payload: RiskSignalCreate, *, commit: bool = True
):
    _ensure_signal_owners_exist(
        db, transaction_id=payload.transaction_id, decision_id=payload.decision_id
    )
    transaction = require_transaction_in_organisation(
        db,
        transaction_id=payload.transaction_id,
        organisation_id=payload.organisation_id,
    )
    require_decision_in_organisation(
        db,
        decision_id=payload.decision_id,
        organisation_id=payload.organisation_id,
    )
    if transaction.user_id != payload.user_id:
        raise ValidationError("Transaction does not belong to the target user")
    return risk_signal_crud.create_risk_signal(
        db, commit=commit, **payload.model_dump()
    )


def get_risk_signal_service(
    db: Session, risk_signal_id: int, organisation_id: int | None = None
):
    risk_signal = risk_signal_crud.get_risk_signal_by_id(db, risk_signal_id)
    if not risk_signal:
        raise NotFoundError("Risk signal not found")

    if organisation_id is not None and risk_signal.organisation_id != organisation_id:
        raise NotFoundError("Risk signal not found")

    return risk_signal


def list_risk_signals_service(
    db: Session,
    *,
    organisation_id: int | None = None,
    transaction_id: int | None = None,
    decision_id: int | None = None,
    offset: int = 0,
    limit: int = 200,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> tuple[list, int]:
    signals = risk_signal_crud.list_risk_signals(
        db,
        organisation_id=organisation_id,
        transaction_id=transaction_id,
        decision_id=decision_id,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    total = risk_signal_crud.count_risk_signals(
        db,
        organisation_id=organisation_id,
        transaction_id=transaction_id,
        decision_id=decision_id,
    )
    return signals, total
