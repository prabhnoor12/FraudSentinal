from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from auth_dependencies import get_current_org_id, require_scopes
from database import get_db
from schemas.billing_schemas import (
    BillingPlanCreate,
    BillingPlanOut,
    BillingRecordCreate,
    BillingRecordOut,
)
from services import billing_service


router = APIRouter(prefix="/billing", tags=["billing"])


@router.get(
    "/plans",
    response_model=list[BillingPlanOut],
    dependencies=[Depends(require_scopes("billing:read"))],
)
def list_billing_plans(
    org_id: int = Depends(get_current_org_id), db: Session = Depends(get_db)
):
    return billing_service.list_billing_plans_service(db, organisation_id=org_id)


@router.post(
    "/plans",
    response_model=BillingPlanOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scopes("billing:write"))],
)
def create_billing_plan(
    payload: BillingPlanCreate,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    payload.organisation_id = org_id
    return billing_service.create_billing_plan_service(db, payload)


@router.get(
    "/records",
    response_model=list[BillingRecordOut],
    dependencies=[Depends(require_scopes("billing:read"))],
)
def list_billing_records(
    org_id: int = Depends(get_current_org_id), db: Session = Depends(get_db)
):
    return billing_service.list_billing_records_service(db, organisation_id=org_id)


@router.post(
    "/records",
    response_model=BillingRecordOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scopes("billing:write"))],
)
def create_billing_record(
    payload: BillingRecordCreate,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    payload.organisation_id = org_id
    return billing_service.create_billing_record_service(db, payload)
