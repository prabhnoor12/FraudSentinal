from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from cruds import audit_crud
from models.audit_models import AuditLog


class AuditService:
    @staticmethod
    def log_security_event(
        db: Session,
        *,
        action: str,
        user_id: Optional[int] = None,
        organisation_id: Optional[int] = None,
        resource_type: str = "auth",
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        return audit_crud.create_audit_log(
            db,
            user_id=user_id,
            organisation_id=organisation_id,
            event_type="security_event",
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    def log_rule_change(
        db: Session,
        *,
        user_id: int,
        organisation_id: int,
        action: str,
        rule_id: int,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        return audit_crud.create_audit_log(
            db,
            user_id=user_id,
            organisation_id=organisation_id,
            event_type="rule_change",
            action=action,
            resource_type="fraud_rule",
            resource_id=str(rule_id),
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    def log_case_action(
        db: Session,
        *,
        user_id: int,
        organisation_id: int,
        action: str,
        case_id: int,
        notes: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        return audit_crud.create_audit_log(
            db,
            user_id=user_id,
            organisation_id=organisation_id,
            event_type="case_action",
            action=action,
            resource_type="review_case",
            resource_id=str(case_id),
            details={"notes": notes},
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    def log_resource_access(
        db: Session,
        *,
        user_id: int,
        organisation_id: int,
        resource_type: str,
        resource_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        return audit_crud.create_audit_log(
            db,
            user_id=user_id,
            organisation_id=organisation_id,
            event_type="resource_access",
            action="view",
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    def list_logs(db: Session, organisation_id: int, **kwargs):
        # Tenant isolation is enforced here
        logs = audit_crud.list_audit_logs(db, organisation_id=organisation_id, **kwargs)
        count_kwargs = {
            key: value
            for key, value in kwargs.items()
            if key in {"user_id", "event_type", "resource_type", "start_date", "end_date"}
        }
        total = audit_crud.count_audit_logs(
            db, organisation_id=organisation_id, **count_kwargs
        )
        return logs, total

    @staticmethod
    def get_stats(db: Session, organisation_id: int):
        return audit_crud.get_audit_stats(db, organisation_id=organisation_id)

    @staticmethod
    def export_logs_csv(db: Session, organisation_id: int, **kwargs) -> str:
        import csv
        import io

        logs = audit_crud.list_audit_logs(
            db, organisation_id=organisation_id, limit=1000, **kwargs
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "ID",
                "Timestamp",
                "User ID",
                "Event Type",
                "Action",
                "Resource Type",
                "Resource ID",
                "IP Address",
            ]
        )

        for log in logs:
            writer.writerow(
                [
                    log.id,
                    log.created_at.isoformat(),
                    log.user_id,
                    log.event_type,
                    log.action,
                    log.resource_type,
                    log.resource_id,
                    log.ip_address,
                ]
            )

        return output.getvalue()
