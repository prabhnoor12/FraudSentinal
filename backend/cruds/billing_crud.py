from datetime import UTC, datetime

from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from models.billing_models import BillingPlan, BillingRecord, BillingWebhookEvent


def create_billing_plan(db: Session, **data) -> BillingPlan:
    billing_plan = BillingPlan(**data)
    db.add(billing_plan)
    db.commit()
    db.refresh(billing_plan)
    return billing_plan


def get_billing_plan_by_id(db: Session, billing_plan_id: int) -> BillingPlan | None:
    return db.query(BillingPlan).filter(BillingPlan.id == billing_plan_id).first()


def get_active_billing_plan(
    db: Session, *, organisation_id: int, plan_code: str | None = None
) -> BillingPlan | None:
    query = db.query(BillingPlan).filter(
        BillingPlan.organisation_id == organisation_id, BillingPlan.is_active.is_(True)
    )
    if plan_code is not None:
        query = query.filter(BillingPlan.plan_code == plan_code)
    return query.order_by(desc(BillingPlan.updated_at), desc(BillingPlan.id)).first()


def get_billing_plan_by_provider_plan_id(
    db: Session, *, billing_provider: str, provider_plan_id: str
) -> BillingPlan | None:
    return (
        db.query(BillingPlan)
        .filter(
            BillingPlan.billing_provider == billing_provider,
            BillingPlan.provider_plan_id == provider_plan_id,
        )
        .order_by(desc(BillingPlan.updated_at), desc(BillingPlan.id))
        .first()
    )


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


def create_billing_record(db: Session, *, commit: bool = True, **data) -> BillingRecord:
    billing_record = BillingRecord(**data)
    db.add(billing_record)
    if commit:
        db.commit()
        db.refresh(billing_record)
    else:
        db.flush()
    return billing_record


def get_billing_record_by_id(db: Session, billing_record_id: int) -> BillingRecord | None:
    return db.query(BillingRecord).filter(BillingRecord.id == billing_record_id).first()


def get_billing_record_by_provider_references(
    db: Session,
    *,
    billing_provider: str,
    organisation_id: int,
    provider_invoice_id: str | None = None,
    provider_payment_id: str | None = None,
    provider_subscription_id: str | None = None,
) -> BillingRecord | None:
    query = db.query(BillingRecord).filter(
        BillingRecord.billing_provider == billing_provider,
        BillingRecord.organisation_id == organisation_id,
    )
    if provider_invoice_id:
        record = query.filter(BillingRecord.provider_invoice_id == provider_invoice_id).first()
        if record is not None:
            return record
    if provider_payment_id:
        record = query.filter(BillingRecord.provider_payment_id == provider_payment_id).first()
        if record is not None:
            return record
    if provider_subscription_id:
        record = query.filter(
            BillingRecord.provider_subscription_id == provider_subscription_id
        ).order_by(desc(BillingRecord.created_at), desc(BillingRecord.id)).first()
        if record is not None:
            return record
    return None


def update_billing_record(
    db: Session, billing_record: BillingRecord, *, commit: bool = True, **updates
) -> BillingRecord:
    for field, value in updates.items():
        if value is not None:
            setattr(billing_record, field, value)
    if commit:
        db.commit()
        db.refresh(billing_record)
    else:
        db.flush()
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


def get_billing_webhook_event(
    db: Session, *, provider: str, event_id: str
) -> BillingWebhookEvent | None:
    return (
        db.query(BillingWebhookEvent)
        .filter(
            BillingWebhookEvent.provider == provider,
            BillingWebhookEvent.event_id == event_id,
        )
        .first()
    )


def create_billing_webhook_event(
    db: Session, *, commit: bool = True, **data
) -> BillingWebhookEvent:
    webhook_event = BillingWebhookEvent(**data)
    db.add(webhook_event)
    if commit:
        db.commit()
        db.refresh(webhook_event)
    else:
        db.flush()
    return webhook_event


def update_billing_webhook_event(
    db: Session,
    webhook_event: BillingWebhookEvent,
    *,
    commit: bool = True,
    **updates,
) -> BillingWebhookEvent:
    for field, value in updates.items():
        if value is not None:
            setattr(webhook_event, field, value)
    if "processed_at" not in updates and updates.get("processing_status") == "processed":
        webhook_event.processed_at = datetime.now(UTC)
    if commit:
        db.commit()
        db.refresh(webhook_event)
    else:
        db.flush()
    return webhook_event
