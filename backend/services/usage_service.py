from sqlalchemy.orm import Session

from cruds import organisation_crud, usage_crud, user_crud
from schemas.usage_schemas import UsageEventCreate, UsageSummaryCreate
from utils.exception_handling_utils import NotFoundError


def _ensure_usage_owners_exist(
    db: Session, *, user_id: int, organisation_id: int
) -> None:
    if not user_crud.get_user_by_id(db, user_id):
        raise NotFoundError("User not found")
    if not organisation_crud.get_organisation_by_id(db, organisation_id):
        raise NotFoundError("Organisation not found")


def create_usage_event_service(db: Session, payload: UsageEventCreate):
    _ensure_usage_owners_exist(
        db, user_id=payload.user_id, organisation_id=payload.organisation_id
    )
    return usage_crud.create_usage_event(db, **payload.model_dump())


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
    return usage_crud.create_usage_summary(db, **payload.model_dump())


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
