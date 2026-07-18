from __future__ import annotations

from sqlalchemy.orm import Session

from cruds import decision_crud, risk_signal_crud, transaction_crud
from schemas.risk_signal_schemas import RiskSignalCreate
from utils.exception_handling_utils import NotFoundError


def _ensure_signal_owners_exist(db: Session, *, transaction_id: int, decision_id: int) -> None:
    if not transaction_crud.get_transaction_by_id(db, transaction_id):
        raise NotFoundError("Transaction not found")
    if not decision_crud.get_decision_by_id(db, decision_id):
        raise NotFoundError("Decision not found")


def create_risk_signal_service(db: Session, payload: RiskSignalCreate, *, commit: bool = True):
    _ensure_signal_owners_exist(db, transaction_id=payload.transaction_id, decision_id=payload.decision_id)
    return risk_signal_crud.create_risk_signal(db, commit=commit, **payload.model_dump())


def get_risk_signal_service(db: Session, risk_signal_id: int, organisation_id: int | None = None):
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
    limit: int = 200,
):
    return risk_signal_crud.list_risk_signals(
        db,
        organisation_id=organisation_id,
        transaction_id=transaction_id,
        decision_id=decision_id,
        limit=limit,
    )
