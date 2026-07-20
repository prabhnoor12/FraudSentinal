from fastapi import APIRouter, BackgroundTasks, Depends, Request
import time
from sqlalchemy.orm import Session

from auth_dependencies import (
    get_current_org_id,
    get_current_principal,
    require_scopes,
)
from database import get_db
from schemas.audit_schemas import AuditContext
from schemas.fraud_check_schemas import FraudCheckRequest, FraudCheckResponse
from services import (
    auth_service,
    background_task_service,
    fraud_check_service,
    fraud_metrics_service,
)


router = APIRouter(prefix="/check-fraud", tags=["check-fraud"])


def require_auth(
    principal=Depends(require_scopes("fraud:check")),
):
    return principal


def get_audit_ctx(
    request: Request,
    org_id: int = Depends(get_current_org_id),
    principal=Depends(get_current_principal),
) -> AuditContext:
    return AuditContext(
        user_id=getattr(principal.user, "id", None),
        organisation_id=org_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("", response_model=FraudCheckResponse)
def check_fraud(
    background_tasks: BackgroundTasks,
    request: Request,
    payload: FraudCheckRequest,
    org_id: int = Depends(get_current_org_id),
    principal=Depends(require_scopes("fraud:check")),
    audit_ctx: AuditContext = Depends(get_audit_ctx),
    db: Session = Depends(get_db),
):
    started_at = time.perf_counter()
    # Enforce org_id from token
    payload.organisation_id = org_id
    payload.metadata = {
        **(payload.metadata or {}),
        "user_agent": (payload.metadata or {}).get("user_agent")
        or request.headers.get("user-agent"),
        "accept_language": (payload.metadata or {}).get("accept_language")
        or request.headers.get("accept-language"),
        "accept_encoding": (payload.metadata or {}).get("accept_encoding")
        or request.headers.get("accept-encoding"),
    }
    response = fraud_check_service.check_fraud_service(db, payload)
    fraud_metrics_service.fraud_metrics.record_check(
        decision=response.decision.value,
        risk_score=response.risk_score,
        duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
    )
    background_tasks.add_task(
        background_task_service.log_fraud_check_completed,
        bind=db.get_bind(),
        user_id=audit_ctx.user_id,
        organisation_id=audit_ctx.organisation_id,
        transaction_id=response.transaction_id,
        decision_id=response.decision_id,
        risk_score=response.risk_score,
        decision=response.decision.value,
        reason_codes=[reason.value for reason in response.reason_codes],
        ip_address=audit_ctx.ip_address,
        user_agent=audit_ctx.user_agent,
    )
    return response
