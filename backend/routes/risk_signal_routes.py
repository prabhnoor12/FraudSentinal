from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import get_current_org_id, oauth2_scheme
from database import get_db
from schemas.risk_signal_schemas import RiskSignalOut
from services import auth_service, risk_signal_service


router = APIRouter(prefix="/risk-signals", tags=["risk-signals"])


def require_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return auth_service.get_authenticated_user_from_token(db, token)


@router.get("", response_model=list[RiskSignalOut])
def list_risk_signals(
    transaction_id: int | None = None,
    decision_id: int | None = None,
    limit: int = 200,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    return risk_signal_service.list_risk_signals_service(
        db,
        organisation_id=org_id,
        transaction_id=transaction_id,
        decision_id=decision_id,
        limit=limit,
    )


@router.get("/{risk_signal_id}", response_model=RiskSignalOut)
def get_risk_signal(
    risk_signal_id: int,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    return risk_signal_service.get_risk_signal_service(db, risk_signal_id, organisation_id=org_id)
