from sqlalchemy.orm import Session

from cruds import usage_crud
from schemas.usage_schemas import UsageEventCreate, UsageSummaryCreate
from services import entitlement_service
from utils.ownership_utils import require_user_in_organisation


def _ensure_usage_owners_exist(
    db: Session, *, user_id: int, organisation_id: int
) -> None:
    require_user_in_organisation(db, user_id=user_id, organisation_id=organisation_id)


def create_usage_event_service(db: Session, payload: UsageEventCreate):
    _ensure_usage_owners_exist(
        db, user_id=payload.user_id, organisation_id=payload.organisation_id
    )
    event = usage_crud.create_usage_event(db, **payload.model_dump())
    entitlement_service.invalidate_entitlement_cache(payload.organisation_id)
    return event


def list_usage_events_service(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "recorded_at",
    sort_dir: str = "desc",
):
    items = usage_crud.list_usage_events(
        db,
        user_id=user_id,
        organisation_id=organisation_id,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    total = usage_crud.count_usage_events(
        db, user_id=user_id, organisation_id=organisation_id
    )
    return items, total


def create_usage_summary_service(db: Session, payload: UsageSummaryCreate):
    _ensure_usage_owners_exist(
        db, user_id=payload.user_id, organisation_id=payload.organisation_id
    )
    summary = usage_crud.create_usage_summary(db, **payload.model_dump())
    entitlement_service.invalidate_entitlement_cache(payload.organisation_id)
    return summary


def list_usage_summaries_service(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "period_start",
    sort_dir: str = "desc",
):
    items = usage_crud.list_usage_summaries(
        db,
        user_id=user_id,
        organisation_id=organisation_id,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    total = usage_crud.count_usage_summaries(
        db, user_id=user_id, organisation_id=organisation_id
    )
    return items, total
