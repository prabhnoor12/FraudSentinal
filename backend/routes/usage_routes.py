from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from auth_dependencies import get_current_org_id, get_current_principal, require_scopes
from database import get_db
from schemas.usage_schemas import (
    UsageEventCreate,
    UsageEventListResponse,
    UsageEventOut,
    UsageSummaryCreate,
    UsageSummaryListResponse,
    UsageSummaryOut,
)
from services import usage_service
from utils.pagination_utils import (
    build_paginated_payload,
    normalize_limit,
    normalize_offset,
    normalize_sort_dir,
)


router = APIRouter(prefix="/usage", tags=["usage"])


def require_auth(
    principal=Depends(get_current_principal),
):
    return principal


@router.get(
    "/events",
    response_model=UsageEventListResponse,
    dependencies=[Depends(require_scopes("usage:read"))],
)
def list_usage_events(
    request: Request,
    user_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "recorded_at",
    sort_dir: str = "desc",
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    normalized_offset = normalize_offset(offset)
    normalized_limit = normalize_limit(limit, default=100, maximum=200)
    items, total = usage_service.list_usage_events_service(
        db,
        user_id=user_id,
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
    "/events",
    response_model=UsageEventOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scopes("usage:write"))],
)
def create_usage_event(payload: UsageEventCreate, db: Session = Depends(get_db)):
    return usage_service.create_usage_event_service(db, payload)


@router.get(
    "/summaries",
    response_model=UsageSummaryListResponse,
    dependencies=[Depends(require_scopes("usage:read"))],
)
def list_usage_summaries(
    request: Request,
    user_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "period_start",
    sort_dir: str = "desc",
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    normalized_offset = normalize_offset(offset)
    normalized_limit = normalize_limit(limit, default=100, maximum=200)
    items, total = usage_service.list_usage_summaries_service(
        db,
        user_id=user_id,
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
    "/summaries",
    response_model=UsageSummaryOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scopes("usage:write"))],
)
def create_usage_summary(payload: UsageSummaryCreate, db: Session = Depends(get_db)):
    return usage_service.create_usage_summary_service(db, payload)
