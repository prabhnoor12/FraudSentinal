from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from auth_dependencies import get_current_principal, require_scopes
from database import get_db
from schemas.usage_schemas import (
    UsageEventCreate,
    UsageEventOut,
    UsageSummaryCreate,
    UsageSummaryOut,
)
from services import usage_service


router = APIRouter(prefix="/user-tracking", tags=["user-tracking"])


def require_auth(
    principal=Depends(get_current_principal),
):
    return principal


@router.get(
    "/events",
    response_model=list[UsageEventOut],
    dependencies=[Depends(require_scopes("usage:read"))],
)
def list_usage_events(
    user_id: int | None = None,
    organisation_id: int | None = None,
    db: Session = Depends(get_db),
):
    return usage_service.list_usage_events_service(
        db,
        user_id=user_id,
        organisation_id=organisation_id,
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
    response_model=list[UsageSummaryOut],
    dependencies=[Depends(require_scopes("usage:read"))],
)
def list_usage_summaries(
    user_id: int | None = None,
    organisation_id: int | None = None,
    db: Session = Depends(get_db),
):
    return usage_service.list_usage_summaries_service(
        db,
        user_id=user_id,
        organisation_id=organisation_id,
    )


@router.post(
    "/summaries",
    response_model=UsageSummaryOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scopes("usage:write"))],
)
def create_usage_summary(payload: UsageSummaryCreate, db: Session = Depends(get_db)):
    return usage_service.create_usage_summary_service(db, payload)
