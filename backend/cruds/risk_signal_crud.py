from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from models.risk_signal_models import RiskSignal


def create_risk_signal(db: Session, *, commit: bool = True, **data) -> RiskSignal:
    risk_signal = RiskSignal(**data)
    db.add(risk_signal)
    if commit:
        db.commit()
        db.refresh(risk_signal)
    return risk_signal


def get_risk_signal_by_id(db: Session, risk_signal_id: int) -> RiskSignal | None:
    return db.query(RiskSignal).filter(RiskSignal.id == risk_signal_id).first()


def list_risk_signals(
    db: Session,
    *,
    organisation_id: int | None = None,
    transaction_id: int | None = None,
    decision_id: int | None = None,
    offset: int = 0,
    limit: int = 200,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> list[RiskSignal]:
    query = db.query(RiskSignal)
    if organisation_id is not None:
        query = query.filter(RiskSignal.organisation_id == organisation_id)
    if transaction_id is not None:
        query = query.filter(RiskSignal.transaction_id == transaction_id)
    if decision_id is not None:
        query = query.filter(RiskSignal.decision_id == decision_id)
    order_column = {
        "created_at": RiskSignal.created_at,
        "weight": RiskSignal.weight,
        "id": RiskSignal.id,
    }.get(sort_by, RiskSignal.created_at)
    order_func = asc if sort_dir == "asc" else desc
    return (
        query.order_by(order_func(order_column), desc(RiskSignal.id))
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_risk_signals(
    db: Session,
    *,
    organisation_id: int | None = None,
    transaction_id: int | None = None,
    decision_id: int | None = None,
) -> int:
    query = db.query(func.count(RiskSignal.id))
    if organisation_id is not None:
        query = query.filter(RiskSignal.organisation_id == organisation_id)
    if transaction_id is not None:
        query = query.filter(RiskSignal.transaction_id == transaction_id)
    if decision_id is not None:
        query = query.filter(RiskSignal.decision_id == decision_id)
    return query.scalar() or 0
