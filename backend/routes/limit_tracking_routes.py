from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from auth_dependencies import get_current_org_id, get_current_principal, require_scopes
from database import get_db
from schemas.limit_tracking_schemas import (
    LimitUsageRecordCreate,
    LimitUsageRecordListResponse,
    LimitUsageRecordOut,
    UsageLimitCreate,
    UsageLimitListResponse,
    UsageLimitOut,
)
from services import limit_tracking_service
from utils.pagination_utils import (
    build_paginated_payload,
    normalize_limit,
    normalize_offset,
    normalize_sort_dir,
)


router = APIRouter(prefix="/limit-tracking", tags=["limit-tracking"])


def require_auth(
    principal=Depends(get_current_principal),
):
    return principal


@router.get(
    "/limits",
    response_model=UsageLimitListResponse,
    dependencies=[Depends(require_scopes("limits:read"))],
)
def list_usage_limits(
    request: Request,
    user_id: int | None = None,
    limit_type: str | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    normalized_offset = normalize_offset(offset)
    normalized_limit = normalize_limit(limit, default=100, maximum=200)
    items, total = limit_tracking_service.list_usage_limits_service(
        db,
        user_id=user_id,
        organisation_id=org_id,
        limit_type=limit_type,
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
    "/limits",
    response_model=UsageLimitOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scopes("limits:write"))],
)
def create_usage_limit(payload: UsageLimitCreate, db: Session = Depends(get_db)):
    return limit_tracking_service.create_usage_limit_service(db, payload)


@router.get(
    "/records",
    response_model=LimitUsageRecordListResponse,
    dependencies=[Depends(require_scopes("limits:read"))],
)
def list_limit_usage_records(
    request: Request,
    usage_limit_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "period_start",
    sort_dir: str = "desc",
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    normalized_offset = normalize_offset(offset)
    normalized_limit = normalize_limit(limit, default=100, maximum=200)
    items, total = limit_tracking_service.list_limit_usage_records_service(
        db,
        usage_limit_id=usage_limit_id,
        organisation_id=org_id,
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
    response_model=LimitUsageRecordOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scopes("limits:write"))],
)
def create_limit_usage_record(
    payload: LimitUsageRecordCreate, db: Session = Depends(get_db)
):
    return limit_tracking_service.create_limit_usage_record_service(db, payload)
