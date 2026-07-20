from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from models.billing_models import BillingPlan, BillingRecord


def create_billing_plan(db: Session, **data) -> BillingPlan:
    billing_plan = BillingPlan(**data)
    db.add(billing_plan)
    db.commit()
    db.refresh(billing_plan)
    return billing_plan


def get_billing_plan_by_id(db: Session, billing_plan_id: int) -> BillingPlan | None:
    return db.query(BillingPlan).filter(BillingPlan.id == billing_plan_id).first()


def list_billing_plans(
    db: Session,
    *,
    organisation_id: int | None = None,
    is_active: bool | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> list[BillingPlan]:
    query = db.query(BillingPlan)
    if organisation_id is not None:
        query = query.filter(BillingPlan.organisation_id == organisation_id)
    if is_active is not None:
        query = query.filter(BillingPlan.is_active == is_active)
    order_column = {
        "created_at": BillingPlan.created_at,
        "name": BillingPlan.name,
        "price_per_unit": BillingPlan.price_per_unit,
        "id": BillingPlan.id,
    }.get(sort_by, BillingPlan.created_at)
    order_func = asc if sort_dir == "asc" else desc
    return (
        query.order_by(order_func(order_column), desc(BillingPlan.id))
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_billing_plans(
    db: Session,
    *,
    organisation_id: int | None = None,
    is_active: bool | None = None,
) -> int:
    query = db.query(func.count(BillingPlan.id))
    if organisation_id is not None:
        query = query.filter(BillingPlan.organisation_id == organisation_id)
    if is_active is not None:
        query = query.filter(BillingPlan.is_active == is_active)
    return query.scalar() or 0


def update_billing_plan(
    db: Session, billing_plan: BillingPlan, **updates
) -> BillingPlan:
    for field, value in updates.items():
        if value is not None:
            setattr(billing_plan, field, value)
    db.commit()
    db.refresh(billing_plan)
    return billing_plan


def create_billing_record(db: Session, **data) -> BillingRecord:
    billing_record = BillingRecord(**data)
    db.add(billing_record)
    db.commit()
    db.refresh(billing_record)
    return billing_record


def list_billing_records(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> list[BillingRecord]:
    query = db.query(BillingRecord)
    if user_id is not None:
        query = query.filter(BillingRecord.user_id == user_id)
    if organisation_id is not None:
        query = query.filter(BillingRecord.organisation_id == organisation_id)
    if status is not None:
        query = query.filter(BillingRecord.status == status)
    order_column = {
        "created_at": BillingRecord.created_at,
        "amount": BillingRecord.amount,
        "billing_period_start": BillingRecord.billing_period_start,
        "id": BillingRecord.id,
    }.get(sort_by, BillingRecord.created_at)
    order_func = asc if sort_dir == "asc" else desc
    return (
        query.order_by(order_func(order_column), desc(BillingRecord.id))
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_billing_records(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
    status: str | None = None,
) -> int:
    query = db.query(func.count(BillingRecord.id))
    if user_id is not None:
        query = query.filter(BillingRecord.user_id == user_id)
    if organisation_id is not None:
        query = query.filter(BillingRecord.organisation_id == organisation_id)
    if status is not None:
        query = query.filter(BillingRecord.status == status)
    return query.scalar() or 0
