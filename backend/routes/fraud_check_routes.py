from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from auth import get_current_org_id, oauth2_scheme
from database import get_db
from schemas.fraud_check_schemas import FraudCheckRequest, FraudCheckResponse
from services import auth_service, fraud_check_service


router = APIRouter(prefix="/check-fraud", tags=["check-fraud"])


def require_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return auth_service.get_authenticated_user_from_token(db, token)


@router.post("", response_model=FraudCheckResponse)
def check_fraud(
    request: Request,
    payload: FraudCheckRequest,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
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
    return fraud_check_service.check_fraud_service(db, payload)
