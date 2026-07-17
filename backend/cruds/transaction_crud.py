from sqlalchemy.orm import Session

from models.transaction_models import Transaction


def create_transaction(db: Session, *, commit: bool = True, **data) -> Transaction:
    payload = dict(data)
    payload["transaction_metadata"] = payload.pop("metadata", {})
    transaction = Transaction(**payload)
    db.add(transaction)
    if commit:
        db.commit()
        db.refresh(transaction)
    return transaction


def get_transaction_by_id(db: Session, transaction_id: int) -> Transaction | None:
    return db.query(Transaction).filter(Transaction.id == transaction_id).first()


def list_transactions(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
    limit: int = 100,
) -> list[Transaction]:
    query = db.query(Transaction)
    if user_id is not None:
        query = query.filter(Transaction.user_id == user_id)
    if organisation_id is not None:
        query = query.filter(Transaction.organisation_id == organisation_id)
    return query.order_by(Transaction.created_at.desc()).limit(limit).all()
