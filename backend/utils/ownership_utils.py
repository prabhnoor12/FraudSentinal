from __future__ import annotations

from sqlalchemy.orm import Session

from cruds import decision_crud, organisation_crud, session_crud, transaction_crud, user_crud
from models.decision_models import Decision
from models.organisation_models import Organisation
from models.session_models import UserSession
from models.transaction_models import Transaction
from models.user_models import User
from utils.exception_handling_utils import NotFoundError


def require_organisation(db: Session, organisation_id: int) -> Organisation:
    organisation = organisation_crud.get_organisation_by_id(db, organisation_id)
    if not organisation:
        raise NotFoundError("Organisation not found")
    return organisation


def require_user_in_organisation(db: Session, *, user_id: int, organisation_id: int) -> User:
    user = user_crud.get_user_by_id(db, user_id)
    if not user or user.organisation_id != organisation_id:
        raise NotFoundError("User not found")
    return user


def require_user_in_organisation_if_provided(
    db: Session,
    *,
    user_id: int,
    organisation_id: int | None,
) -> User:
    user = user_crud.get_user_by_id(db, user_id)
    if not user:
        raise NotFoundError("User not found")
    if organisation_id is not None and user.organisation_id != organisation_id:
        raise NotFoundError("User not found")
    return user


def require_transaction_in_organisation(
    db: Session, *, transaction_id: int, organisation_id: int
) -> Transaction:
    transaction = transaction_crud.get_transaction_by_id(db, transaction_id)
    if not transaction or transaction.organisation_id != organisation_id:
        raise NotFoundError("Transaction not found")
    return transaction


def require_decision_in_organisation(
    db: Session, *, decision_id: int, organisation_id: int
) -> Decision:
    decision = decision_crud.get_decision_by_id(db, decision_id)
    if not decision or decision.organisation_id != organisation_id:
        raise NotFoundError("Decision not found")
    return decision


def require_transaction_and_decision_in_organisation(
    db: Session,
    *,
    transaction_id: int,
    decision_id: int,
    organisation_id: int,
) -> tuple[Transaction, Decision]:
    transaction = require_transaction_in_organisation(
        db, transaction_id=transaction_id, organisation_id=organisation_id
    )
    decision = require_decision_in_organisation(
        db, decision_id=decision_id, organisation_id=organisation_id
    )
    if decision.transaction_id != transaction.id:
        raise NotFoundError("Decision not found")
    return transaction, decision


def require_transaction_ownership_match(
    db: Session,
    *,
    transaction_id: int,
    user_id: int,
    organisation_id: int,
) -> Transaction:
    transaction = require_transaction_in_organisation(
        db, transaction_id=transaction_id, organisation_id=organisation_id
    )
    if transaction.user_id != user_id:
        raise NotFoundError("Transaction not found")
    return transaction


def require_session_in_organisation(
    db: Session,
    *,
    session_id: int,
    organisation_id: int,
) -> UserSession:
    session = session_crud.get_session_by_id(db, session_id)
    if not session:
        raise NotFoundError("Session not found")
    if session.organisation_id != organisation_id:
        raise NotFoundError("Session not found")
    return session
