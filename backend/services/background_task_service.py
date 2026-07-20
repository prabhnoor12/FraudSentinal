from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from services.audit_service import AuditService


def log_fraud_check_completed(
    *,
    bind,
    user_id: int | None,
    organisation_id: int,
    transaction_id: int,
    decision_id: int,
    risk_score: float,
    decision: str,
    reason_codes: list[str],
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=bind)
    db = session_factory()
    try:
        AuditService.log_security_event(
            db,
            action="fraud_check_completed",
            user_id=user_id,
            organisation_id=organisation_id,
            resource_type="fraud_check",
            resource_id=str(transaction_id),
            details={
                "decision_id": decision_id,
                "risk_score": risk_score,
                "decision": decision,
                "reason_codes": reason_codes,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
    finally:
        db.close()
