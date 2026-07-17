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
) -> list[UsageLimit]:
    query = db.query(UsageLimit)
    if user_id is not None:
        query = query.filter(UsageLimit.user_id == user_id)
    if organisation_id is not None:
        query = query.filter(UsageLimit.organisation_id == organisation_id)
    if limit_type is not None:
        query = query.filter(UsageLimit.limit_type == limit_type)
    return query.order_by(UsageLimit.created_at.desc()).all()


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
) -> list[LimitUsageRecord]:
    query = db.query(LimitUsageRecord)
    if usage_limit_id is not None:
        query = query.filter(LimitUsageRecord.usage_limit_id == usage_limit_id)
    return query.order_by(LimitUsageRecord.period_start.desc()).all()
