from sqlalchemy.orm import Session

from models.usage_models import UsageEvent, UsageSummary


def create_usage_event(db: Session, **data) -> UsageEvent:
    usage_event = UsageEvent(**data)
    db.add(usage_event)
    db.commit()
    db.refresh(usage_event)
    return usage_event


def list_usage_events(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
) -> list[UsageEvent]:
    query = db.query(UsageEvent)
    if user_id is not None:
        query = query.filter(UsageEvent.user_id == user_id)
    if organisation_id is not None:
        query = query.filter(UsageEvent.organisation_id == organisation_id)
    return query.order_by(UsageEvent.recorded_at.desc()).all()


def create_usage_summary(db: Session, **data) -> UsageSummary:
    usage_summary = UsageSummary(**data)
    db.add(usage_summary)
    db.commit()
    db.refresh(usage_summary)
    return usage_summary


def list_usage_summaries(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
) -> list[UsageSummary]:
    query = db.query(UsageSummary)
    if user_id is not None:
        query = query.filter(UsageSummary.user_id == user_id)
    if organisation_id is not None:
        query = query.filter(UsageSummary.organisation_id == organisation_id)
    return query.order_by(UsageSummary.period_start.desc()).all()
