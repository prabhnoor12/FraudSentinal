from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from auth import get_current_org_id, oauth2_scheme
from database import get_db
from schemas.audit_schemas import AuditContext
from schemas.fraud_rule_schemas import FraudRuleCreate, FraudRuleOut, FraudRuleUpdate
from services import auth_service, fraud_rule_service


router = APIRouter(prefix="/fraud-rules", tags=["fraud-rules"])


def get_audit_ctx(
    request: Request,
    org_id: int = Depends(get_current_org_id),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> AuditContext:
    user = auth_service.get_authenticated_user_from_token(db, token)
    return AuditContext(
        user_id=user.id,
        organisation_id=org_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.get("", response_model=list[FraudRuleOut])
def list_fraud_rules(
    enabled: bool | None = None,
    limit: int = 100,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    return fraud_rule_service.list_fraud_rules_service(
        db,
        organisation_id=org_id,
        enabled=enabled,
        limit=limit,
    )


@router.post("", response_model=FraudRuleOut, status_code=status.HTTP_201_CREATED)
def create_fraud_rule(
    payload: FraudRuleCreate,
    org_id: int = Depends(get_current_org_id),
    audit_ctx: AuditContext = Depends(get_audit_ctx),
    db: Session = Depends(get_db),
):
    # Enforce org_id from token
    payload.organisation_id = org_id
    return fraud_rule_service.create_fraud_rule_service(
        db, payload, audit_ctx=audit_ctx
    )


@router.get("/{rule_id}", response_model=FraudRuleOut)
def get_fraud_rule(
    rule_id: int,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    return fraud_rule_service.get_fraud_rule_service(
        db, rule_id, organisation_id=org_id
    )


@router.put("/{rule_id}", response_model=FraudRuleOut)
def update_fraud_rule(
    rule_id: int,
    payload: FraudRuleUpdate,
    org_id: int = Depends(get_current_org_id),
    audit_ctx: AuditContext = Depends(get_audit_ctx),
    db: Session = Depends(get_db),
):
    # Enforce org_id from token if provided in payload, or just use org_id for scoping
    if payload.organisation_id is not None:
        payload.organisation_id = org_id
    return fraud_rule_service.update_fraud_rule_service(
        db, rule_id, payload, organisation_id=org_id, audit_ctx=audit_ctx
    )


@router.post("/{rule_id}/enable", response_model=FraudRuleOut)
def enable_fraud_rule(
    rule_id: int,
    org_id: int = Depends(get_current_org_id),
    audit_ctx: AuditContext = Depends(get_audit_ctx),
    db: Session = Depends(get_db),
):
    return fraud_rule_service.enable_fraud_rule_service(
        db, rule_id, organisation_id=org_id, audit_ctx=audit_ctx
    )


@router.post("/{rule_id}/disable", response_model=FraudRuleOut)
def disable_fraud_rule(
    rule_id: int,
    org_id: int = Depends(get_current_org_id),
    audit_ctx: AuditContext = Depends(get_audit_ctx),
    db: Session = Depends(get_db),
):
    return fraud_rule_service.disable_fraud_rule_service(
        db, rule_id, organisation_id=org_id, audit_ctx=audit_ctx
    )
