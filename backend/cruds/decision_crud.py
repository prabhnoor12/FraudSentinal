from sqlalchemy.orm import Session

from models.decision_models import Decision


def create_decision(db: Session, *, commit: bool = True, **data) -> Decision:
    decision = Decision(**data)
    db.add(decision)
    if commit:
        db.commit()
        db.refresh(decision)
    return decision


def get_decision_by_id(db: Session, decision_id: int) -> Decision | None:
    return db.query(Decision).filter(Decision.id == decision_id).first()


def list_decisions(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
    transaction_id: int | None = None,
    limit: int = 100,
) -> list[Decision]:
    query = db.query(Decision)
    if user_id is not None:
        query = query.filter(Decision.user_id == user_id)
    if organisation_id is not None:
        query = query.filter(Decision.organisation_id == organisation_id)
    if transaction_id is not None:
        query = query.filter(Decision.transaction_id == transaction_id)
    return query.order_by(Decision.created_at.desc()).limit(limit).all()
