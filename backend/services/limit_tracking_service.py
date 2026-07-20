from sqlalchemy.orm import Session

from cruds import limit_tracking_crud, organisation_crud, user_crud
from schemas.limit_tracking_schemas import LimitUsageRecordCreate, UsageLimitCreate
from utils.exception_handling_utils import NotFoundError, ValidationError


def create_usage_limit_service(db: Session, payload: UsageLimitCreate):
    if payload.user_id is None and payload.organisation_id is None:
        raise ValidationError("A usage limit must target a user or organisation")
    if payload.user_id is not None and not user_crud.get_user_by_id(
        db, payload.user_id
    ):
        raise NotFoundError("User not found")
    if (
        payload.organisation_id is not None
        and not organisation_crud.get_organisation_by_id(db, payload.organisation_id)
    ):
        raise NotFoundError("Organisation not found")
    return limit_tracking_crud.create_usage_limit(db, **payload.model_dump())


def list_usage_limits_service(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
    limit_type: str | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
):
    items = limit_tracking_crud.list_usage_limits(
        db,
        user_id=user_id,
        organisation_id=organisation_id,
        limit_type=limit_type,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    total = limit_tracking_crud.count_usage_limits(
        db,
        user_id=user_id,
        organisation_id=organisation_id,
        limit_type=limit_type,
    )
    return items, total


def create_limit_usage_record_service(db: Session, payload: LimitUsageRecordCreate):
    usage_limit = limit_tracking_crud.get_usage_limit_by_id(db, payload.usage_limit_id)
    if not usage_limit:
        raise NotFoundError("Usage limit not found")
    return limit_tracking_crud.create_limit_usage_record(db, **payload.model_dump())


def list_limit_usage_records_service(
    db: Session,
    *,
    usage_limit_id: int | None = None,
    organisation_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "period_start",
    sort_dir: str = "desc",
):
    items = limit_tracking_crud.list_limit_usage_records(
        db,
        usage_limit_id=usage_limit_id,
        organisation_id=organisation_id,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    total = limit_tracking_crud.count_limit_usage_records(
        db,
        usage_limit_id=usage_limit_id,
        organisation_id=organisation_id,
    )
    return items, total
