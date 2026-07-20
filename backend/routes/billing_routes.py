from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from auth_dependencies import get_current_org_id, require_scopes
from database import get_db
from schemas.billing_schemas import (
    BillingPlanCreate,
    BillingPlanListResponse,
    BillingPlanOut,
    BillingRecordListResponse,
    BillingRecordCreate,
    BillingRecordOut,
)
from services import billing_service
from utils.pagination_utils import (
    build_paginated_payload,
    normalize_limit,
    normalize_offset,
    normalize_sort_dir,
)


router = APIRouter(prefix="/billing", tags=["billing"])


@router.get(
    "/plans",
    response_model=BillingPlanListResponse,
    dependencies=[Depends(require_scopes("billing:read"))],
)
def list_billing_plans(
    request: Request,
    is_active: bool | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    org_id: int = Depends(get_current_org_id), db: Session = Depends(get_db)
):
    normalized_offset = normalize_offset(offset)
    normalized_limit = normalize_limit(limit, default=100, maximum=200)
    items, total = billing_service.list_billing_plans_service(
        db,
        organisation_id=org_id,
        is_active=is_active,
        offset=normalized_offset,
        limit=normalized_limit,
        sort_by=sort_by,
        sort_dir=normalize_sort_dir(sort_dir),
    )
    return build_paginated_payload(
        request=request,
        items=items,
        total=total,
        limit=normalized_limit,
        offset=normalized_offset,
    )


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
    response_model=BillingRecordListResponse,
    dependencies=[Depends(require_scopes("billing:read"))],
)
def list_billing_records(
    request: Request,
    user_id: int | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    org_id: int = Depends(get_current_org_id), db: Session = Depends(get_db)
):
    normalized_offset = normalize_offset(offset)
    normalized_limit = normalize_limit(limit, default=100, maximum=200)
    items, total = billing_service.list_billing_records_service(
        db,
        user_id=user_id,
        organisation_id=org_id,
        status=status,
        offset=normalized_offset,
        limit=normalized_limit,
        sort_by=sort_by,
        sort_dir=normalize_sort_dir(sort_dir),
    )
    return build_paginated_payload(
        request=request,
        items=items,
        total=total,
        limit=normalized_limit,
        offset=normalized_offset,
    )


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
