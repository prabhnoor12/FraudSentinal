from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_, asc, desc, func
from sqlalchemy.orm import Session

from models.audit_models import AuditLog


def create_audit_log(db: Session, **kwargs) -> AuditLog:
    """Create a new audit log entry. Logs are intended to be immutable."""
    db_obj = AuditLog(**kwargs)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def list_audit_logs(
    db: Session,
    organisation_id: Optional[int] = None,
    user_id: Optional[int] = None,
    event_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> List[AuditLog]:
    query = db.query(AuditLog)

    filters = []
    if organisation_id is not None:
        filters.append(AuditLog.organisation_id == organisation_id)
    if user_id is not None:
        filters.append(AuditLog.user_id == user_id)
    if event_type:
        filters.append(AuditLog.event_type == event_type)
    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)

    if start_date:
        filters.append(AuditLog.created_at >= start_date)
    if end_date:
        filters.append(AuditLog.created_at <= end_date)

    if filters:
        query = query.filter(and_(*filters))

    order_column = {
        "created_at": AuditLog.created_at,
        "event_type": AuditLog.event_type,
        "action": AuditLog.action,
        "id": AuditLog.id,
    }.get(sort_by, AuditLog.created_at)
    order_func = asc if sort_dir == "asc" else desc

    return (
        query.order_by(order_func(order_column), desc(AuditLog.id))
        .limit(limit)
        .offset(offset)
        .all()
    )


def count_audit_logs(
    db: Session,
    organisation_id: Optional[int] = None,
    user_id: Optional[int] = None,
    event_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> int:
    query = db.query(func.count(AuditLog.id))

    filters = []
    if organisation_id is not None:
        filters.append(AuditLog.organisation_id == organisation_id)
    if user_id is not None:
        filters.append(AuditLog.user_id == user_id)
    if event_type:
        filters.append(AuditLog.event_type == event_type)
    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)
    if start_date:
        filters.append(AuditLog.created_at >= start_date)
    if end_date:
        filters.append(AuditLog.created_at <= end_date)

    if filters:
        query = query.filter(and_(*filters))
    return query.scalar() or 0


def get_audit_log_by_id(db: Session, log_id: int) -> Optional[AuditLog]:
    return db.query(AuditLog).filter(AuditLog.id == log_id).first()


def get_audit_stats(db: Session, organisation_id: int) -> dict:
    """Get aggregate statistics for audit logs."""
    event_counts = (
        db.query(AuditLog.event_type, func.count(AuditLog.id))
        .filter(AuditLog.organisation_id == organisation_id)
        .group_by(AuditLog.event_type)
        .all()
    )

    user_activity = (
        db.query(AuditLog.user_id, func.count(AuditLog.id))
        .filter(AuditLog.organisation_id == organisation_id)
        .group_by(AuditLog.user_id)
        .all()
    )

    return {
        "event_type_distribution": dict(event_counts),
        "user_activity_counts": dict(user_activity),
    }
