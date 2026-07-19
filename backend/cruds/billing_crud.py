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
    db: Session, *, organisation_id: int | None = None
) -> list[BillingPlan]:
    query = db.query(BillingPlan)
    if organisation_id is not None:
        query = query.filter(BillingPlan.organisation_id == organisation_id)
    return query.order_by(BillingPlan.created_at.desc()).all()


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
) -> list[BillingRecord]:
    query = db.query(BillingRecord)
    if user_id is not None:
        query = query.filter(BillingRecord.user_id == user_id)
    if organisation_id is not None:
        query = query.filter(BillingRecord.organisation_id == organisation_id)
    return query.order_by(BillingRecord.created_at.desc()).all()
