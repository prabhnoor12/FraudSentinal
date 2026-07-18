from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
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
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
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
        
    return query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset).all()

def get_audit_log_by_id(db: Session, log_id: int) -> Optional[AuditLog]:
    return db.query(AuditLog).filter(AuditLog.id == log_id).first()

def get_audit_stats(db: Session, organisation_id: int) -> dict:
    """Get aggregate statistics for audit logs."""
    event_counts = db.query(
        AuditLog.event_type, func.count(AuditLog.id)
    ).filter(AuditLog.organisation_id == organisation_id).group_by(AuditLog.event_type).all()
    
    user_activity = db.query(
        AuditLog.user_id, func.count(AuditLog.id)
    ).filter(AuditLog.organisation_id == organisation_id).group_by(AuditLog.user_id).all()
    
    return {
        "event_type_distribution": dict(event_counts),
        "user_activity_counts": dict(user_activity)
    }
