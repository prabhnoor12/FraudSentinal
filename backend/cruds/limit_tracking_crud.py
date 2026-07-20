from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from models.limit_tracking_models import LimitUsageRecord, UsageLimit


def create_usage_limit(db: Session, **data) -> UsageLimit:
    usage_limit = UsageLimit(**data)
    db.add(usage_limit)
    db.commit()
    db.refresh(usage_limit)
    return usage_limit


def get_usage_limit_by_id(db: Session, usage_limit_id: int) -> UsageLimit | None:
    return db.query(UsageLimit).filter(UsageLimit.id == usage_limit_id).first()


def list_usage_limits(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
    limit_type: str | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> list[UsageLimit]:
    query = db.query(UsageLimit)
    if user_id is not None:
        query = query.filter(UsageLimit.user_id == user_id)
    if organisation_id is not None:
        query = query.filter(UsageLimit.organisation_id == organisation_id)
    if limit_type is not None:
        query = query.filter(UsageLimit.limit_type == limit_type)
    order_column = {
        "created_at": UsageLimit.created_at,
        "updated_at": UsageLimit.updated_at,
        "limit_value": UsageLimit.limit_value,
        "id": UsageLimit.id,
    }.get(sort_by, UsageLimit.created_at)
    order_func = asc if sort_dir == "asc" else desc
    return (
        query.order_by(order_func(order_column), desc(UsageLimit.id))
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_usage_limits(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
    limit_type: str | None = None,
) -> int:
    query = db.query(func.count(UsageLimit.id))
    if user_id is not None:
        query = query.filter(UsageLimit.user_id == user_id)
    if organisation_id is not None:
        query = query.filter(UsageLimit.organisation_id == organisation_id)
    if limit_type is not None:
        query = query.filter(UsageLimit.limit_type == limit_type)
    return query.scalar() or 0


def update_usage_limit(db: Session, usage_limit: UsageLimit, **updates) -> UsageLimit:
    for field, value in updates.items():
        if value is not None:
            setattr(usage_limit, field, value)
    db.commit()
    db.refresh(usage_limit)
    return usage_limit


def create_limit_usage_record(db: Session, **data) -> LimitUsageRecord:
    record = LimitUsageRecord(**data)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_limit_usage_records(
    db: Session,
    *,
    usage_limit_id: int | None = None,
    organisation_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "period_start",
    sort_dir: str = "desc",
) -> list[LimitUsageRecord]:
    query = db.query(LimitUsageRecord)
    if organisation_id is not None:
        query = query.join(
            UsageLimit, UsageLimit.id == LimitUsageRecord.usage_limit_id
        ).filter(UsageLimit.organisation_id == organisation_id)
    if usage_limit_id is not None:
        query = query.filter(LimitUsageRecord.usage_limit_id == usage_limit_id)
    order_column = {
        "period_start": LimitUsageRecord.period_start,
        "period_end": LimitUsageRecord.period_end,
        "current_usage": LimitUsageRecord.current_usage,
        "updated_at": LimitUsageRecord.updated_at,
        "id": LimitUsageRecord.id,
    }.get(sort_by, LimitUsageRecord.period_start)
    order_func = asc if sort_dir == "asc" else desc
    return (
        query.order_by(order_func(order_column), desc(LimitUsageRecord.id))
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_limit_usage_records(
    db: Session,
    *,
    usage_limit_id: int | None = None,
    organisation_id: int | None = None,
) -> int:
    query = db.query(func.count(LimitUsageRecord.id))
    if organisation_id is not None:
        query = query.join(
            UsageLimit, UsageLimit.id == LimitUsageRecord.usage_limit_id
        ).filter(UsageLimit.organisation_id == organisation_id)
    if usage_limit_id is not None:
        query = query.filter(LimitUsageRecord.usage_limit_id == usage_limit_id)
    return query.scalar() or 0
