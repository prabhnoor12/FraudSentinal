from datetime import datetime

from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from models.usage_models import UsageEvent, UsageSummary


def create_usage_event(db: Session, *, commit: bool = True, **data) -> UsageEvent:
    usage_event = UsageEvent(**data)
    db.add(usage_event)
    if commit:
        db.commit()
        db.refresh(usage_event)
    else:
        db.flush()
    return usage_event


def list_usage_events(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "recorded_at",
    sort_dir: str = "desc",
) -> list[UsageEvent]:
    query = db.query(UsageEvent)
    if user_id is not None:
        query = query.filter(UsageEvent.user_id == user_id)
    if organisation_id is not None:
        query = query.filter(UsageEvent.organisation_id == organisation_id)
    order_column = {
        "recorded_at": UsageEvent.recorded_at,
        "units": UsageEvent.units,
        "id": UsageEvent.id,
    }.get(sort_by, UsageEvent.recorded_at)
    order_func = asc if sort_dir == "asc" else desc
    return (
        query.order_by(order_func(order_column), desc(UsageEvent.id))
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_usage_events(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
) -> int:
    query = db.query(func.count(UsageEvent.id))
    if user_id is not None:
        query = query.filter(UsageEvent.user_id == user_id)
    if organisation_id is not None:
        query = query.filter(UsageEvent.organisation_id == organisation_id)
    return query.scalar() or 0


def create_usage_summary(db: Session, *, commit: bool = True, **data) -> UsageSummary:
    usage_summary = UsageSummary(**data)
    db.add(usage_summary)
    if commit:
        db.commit()
        db.refresh(usage_summary)
    else:
        db.flush()
    return usage_summary


def get_usage_summary_for_period(
    db: Session,
    *,
    user_id: int,
    organisation_id: int,
    period_start: datetime,
    period_end: datetime,
    currency: str,
) -> UsageSummary | None:
    return (
        db.query(UsageSummary)
        .filter(
            UsageSummary.user_id == user_id,
            UsageSummary.organisation_id == organisation_id,
            UsageSummary.period_start == period_start,
            UsageSummary.period_end == period_end,
            UsageSummary.currency == currency,
        )
        .first()
    )


def update_usage_summary(
    db: Session, usage_summary: UsageSummary, *, commit: bool = True, **updates
) -> UsageSummary:
    for field, value in updates.items():
        if value is not None:
            setattr(usage_summary, field, value)
    if commit:
        db.commit()
        db.refresh(usage_summary)
    else:
        db.flush()
    return usage_summary


def list_usage_summaries(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "period_start",
    sort_dir: str = "desc",
) -> list[UsageSummary]:
    query = db.query(UsageSummary)
    if user_id is not None:
        query = query.filter(UsageSummary.user_id == user_id)
    if organisation_id is not None:
        query = query.filter(UsageSummary.organisation_id == organisation_id)
    order_column = {
        "period_start": UsageSummary.period_start,
        "period_end": UsageSummary.period_end,
        "total_units": UsageSummary.total_units,
        "id": UsageSummary.id,
    }.get(sort_by, UsageSummary.period_start)
    order_func = asc if sort_dir == "asc" else desc
    return (
        query.order_by(order_func(order_column), desc(UsageSummary.id))
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_usage_summaries(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
) -> int:
    query = db.query(func.count(UsageSummary.id))
    if user_id is not None:
        query = query.filter(UsageSummary.user_id == user_id)
    if organisation_id is not None:
        query = query.filter(UsageSummary.organisation_id == organisation_id)
    return query.scalar() or 0
