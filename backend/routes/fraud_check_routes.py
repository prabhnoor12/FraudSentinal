from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import oauth2_scheme
from database import get_db
from schemas.fraud_check_schemas import FraudCheckRequest, FraudCheckResponse
from services import auth_service, fraud_check_service


router = APIRouter(prefix="/check-fraud", tags=["check-fraud"])


def require_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return auth_service.get_authenticated_user_from_token(db, token)


@router.post("", response_model=FraudCheckResponse, dependencies=[Depends(require_auth)])
def check_fraud(payload: FraudCheckRequest, db: Session = Depends(get_db)):
    return fraud_check_service.check_fraud_service(db, payload)
