from datetime import datetime

from sqlalchemy import asc, desc, distinct, func
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
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> list[Transaction]:
    query = db.query(Transaction)
    if user_id is not None:
        query = query.filter(Transaction.user_id == user_id)
    if organisation_id is not None:
        query = query.filter(Transaction.organisation_id == organisation_id)
    order_column = {
        "created_at": Transaction.created_at,
        "amount": Transaction.amount,
        "id": Transaction.id,
    }.get(sort_by, Transaction.created_at)
    order_func = asc if sort_dir == "asc" else desc
    return (
        query.order_by(order_func(order_column), desc(Transaction.id))
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_transactions(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
) -> int:
    query = db.query(func.count(Transaction.id))
    if user_id is not None:
        query = query.filter(Transaction.user_id == user_id)
    if organisation_id is not None:
        query = query.filter(Transaction.organisation_id == organisation_id)
    return query.scalar() or 0


def count_transactions_since(
    db: Session,
    *,
    organisation_id: int,
    customer_id: str,
    since: datetime,
) -> int:
    return (
        db.query(func.count(Transaction.id))
        .filter(
            Transaction.organisation_id == organisation_id,
            Transaction.customer_id == customer_id,
            Transaction.created_at >= since,
        )
        .scalar()
        or 0
    )


def sum_transaction_amount_since(
    db: Session,
    *,
    organisation_id: int,
    customer_id: str,
    since: datetime,
) -> float:
    return float(
        db.query(func.sum(Transaction.amount))
        .filter(
            Transaction.organisation_id == organisation_id,
            Transaction.customer_id == customer_id,
            Transaction.created_at >= since,
        )
        .scalar()
        or 0.0
    )


def count_unique_ip_addresses_since(
    db: Session,
    *,
    organisation_id: int,
    customer_id: str,
    since: datetime,
) -> int:
    return (
        db.query(func.count(distinct(Transaction.ip_address)))
        .filter(
            Transaction.organisation_id == organisation_id,
            Transaction.customer_id == customer_id,
            Transaction.created_at >= since,
            Transaction.ip_address.isnot(None),
        )
        .scalar()
        or 0
    )


def has_ip_address_since(
    db: Session,
    *,
    organisation_id: int,
    customer_id: str,
    ip_address: str,
    since: datetime,
) -> bool:
    return (
        db.query(Transaction.id)
        .filter(
            Transaction.organisation_id == organisation_id,
            Transaction.customer_id == customer_id,
            Transaction.ip_address == ip_address,
            Transaction.created_at >= since,
        )
        .first()
        is not None
    )
