from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from backend.utils.exception_handling_utils import AppException
from backend.utils.security_utils import mask_sensitive_data, redact_sensitive_fields


logger = logging.getLogger("fraudsentinel.audit")


class AuditLogger:
    """Centralized audit logger for security-relevant application events."""

    def __init__(self, logger_instance: Optional[logging.Logger] = None) -> None:
        self.logger = logger_instance or logger

    def log_event(
        self,
        *,
        event_type: str,
        user_id: Optional[str] = None,
        organisation_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        severity: str = "INFO",
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Record a structured audit event."""
        safe_details = redact_sensitive_fields(details or {})
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "organisation_id": organisation_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action,
            "details": safe_details,
            "severity": severity.upper(),
            "request_id": request_id,
            "ip_address": mask_sensitive_data(ip_address) if ip_address else None,
            "user_agent": user_agent,
        }
        self.logger.info("audit_event", extra=payload)

    def log_security_event(
        self,
        *,
        event_type: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Record a security-related event with elevated severity."""
        self.log_event(
            event_type=event_type,
            user_id=user_id,
            action="security_event",
            details={"message": message, **(details or {})},
            severity="WARNING",
            request_id=request_id,
            ip_address=ip_address,
        )

    def log_exception(self, exc: Exception, *, context: Optional[dict[str, Any]] = None) -> None:
        """Record exception details without exposing sensitive values."""
        if isinstance(exc, AppException):
            details = {"message": exc.message, "status_code": exc.status_code, **(exc.details or {})}
            severity = "WARNING"
        else:
            details = {"message": str(exc)}
            severity = "ERROR"

        merged_context = redact_sensitive_fields(context or {})
        self.log_event(
            event_type="exception",
            action="error",
            details={**merged_context, **details},
            severity=severity,
        )

    def log_user_action(self, *, user_id: str, action: str, details: Optional[dict[str, Any]] = None, **kwargs: Any) -> None:
        """Convenience wrapper for user-driven actions."""
        self.log_event(event_type="user_action", user_id=user_id, action=action, details=details, **kwargs)

    def log_admin_action(self, *, user_id: str, action: str, details: Optional[dict[str, Any]] = None, **kwargs: Any) -> None:
        """Convenience wrapper for admin-driven actions."""
        self.log_event(event_type="admin_action", user_id=user_id, action=action, details=details, **kwargs)

    def log_system_action(self, *, action: str, details: Optional[dict[str, Any]] = None, **kwargs: Any) -> None:
        """Convenience wrapper for system-driven actions."""
        self.log_event(event_type="system_action", action=action, details=details, **kwargs)


audit_logger = AuditLogger()


__all__ = ["AuditLogger", "audit_logger"]
