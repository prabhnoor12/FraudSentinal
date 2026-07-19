from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import get_current_org_id, oauth2_scheme
from database import get_db
from schemas.decision_schemas import DecisionOut
from services import auth_service, decision_service


router = APIRouter(prefix="/decisions", tags=["decisions"])


def require_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return auth_service.get_authenticated_user_from_token(db, token)


@router.get("", response_model=list[DecisionOut])
def list_decisions(
    user_id: int | None = None,
    transaction_id: int | None = None,
    limit: int = 100,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    return decision_service.list_decisions_service(
        db,
        user_id=user_id,
        organisation_id=org_id,
        transaction_id=transaction_id,
        limit=limit,
    )


@router.get("/{decision_id}", response_model=DecisionOut)
def get_decision(
    decision_id: int,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    return decision_service.get_decision_service(
        db, decision_id, organisation_id=org_id
    )
