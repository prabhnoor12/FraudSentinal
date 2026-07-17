from sqlalchemy.orm import Session

from cruds import billing_crud, organisation_crud, usage_crud, user_crud
from schemas.billing_schemas import BillingPlanCreate, BillingRecordCreate
from utils.exception_handling_utils import NotFoundError


def create_billing_plan_service(db: Session, payload: BillingPlanCreate):
    if not organisation_crud.get_organisation_by_id(db, payload.organisation_id):
        raise NotFoundError("Organisation not found")
    return billing_crud.create_billing_plan(db, **payload.model_dump())


def list_billing_plans_service(db: Session, *, organisation_id: int | None = None):
    return billing_crud.list_billing_plans(db, organisation_id=organisation_id)


def create_billing_record_service(db: Session, payload: BillingRecordCreate):
    if not user_crud.get_user_by_id(db, payload.user_id):
        raise NotFoundError("User not found")
    if not organisation_crud.get_organisation_by_id(db, payload.organisation_id):
        raise NotFoundError("Organisation not found")
    if payload.usage_event_id is not None:
        usage_events = usage_crud.list_usage_events(
            db,
            user_id=payload.user_id,
            organisation_id=payload.organisation_id,
        )
        if not any(event.id == payload.usage_event_id for event in usage_events):
            raise NotFoundError("Usage event not found")
    return billing_crud.create_billing_record(db, **payload.model_dump())


def list_billing_records_service(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
):
    return billing_crud.list_billing_records(db, user_id=user_id, organisation_id=organisation_id)
