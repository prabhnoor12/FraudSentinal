from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from auth import oauth2_scheme
from database import get_db
from schemas.fraud_rule_schemas import FraudRuleCreate, FraudRuleOut, FraudRuleUpdate
from services import auth_service, fraud_rule_service


router = APIRouter(prefix="/fraud-rules", tags=["fraud-rules"])


def require_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return auth_service.get_authenticated_user_from_token(db, token)


@router.get("", response_model=list[FraudRuleOut], dependencies=[Depends(require_auth)])
def list_fraud_rules(
    organisation_id: int | None = None,
    enabled: bool | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return fraud_rule_service.list_fraud_rules_service(
        db,
        organisation_id=organisation_id,
        enabled=enabled,
        limit=limit,
    )


@router.post("", response_model=FraudRuleOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_auth)])
def create_fraud_rule(payload: FraudRuleCreate, db: Session = Depends(get_db)):
    return fraud_rule_service.create_fraud_rule_service(db, payload)


@router.get("/{rule_id}", response_model=FraudRuleOut, dependencies=[Depends(require_auth)])
def get_fraud_rule(rule_id: int, db: Session = Depends(get_db)):
    return fraud_rule_service.get_fraud_rule_service(db, rule_id)


@router.put("/{rule_id}", response_model=FraudRuleOut, dependencies=[Depends(require_auth)])
def update_fraud_rule(rule_id: int, payload: FraudRuleUpdate, db: Session = Depends(get_db)):
    return fraud_rule_service.update_fraud_rule_service(db, rule_id, payload)


@router.post("/{rule_id}/enable", response_model=FraudRuleOut, dependencies=[Depends(require_auth)])
def enable_fraud_rule(rule_id: int, db: Session = Depends(get_db)):
    return fraud_rule_service.enable_fraud_rule_service(db, rule_id)


@router.post("/{rule_id}/disable", response_model=FraudRuleOut, dependencies=[Depends(require_auth)])
def disable_fraud_rule(rule_id: int, db: Session = Depends(get_db)):
    return fraud_rule_service.disable_fraud_rule_service(db, rule_id)
