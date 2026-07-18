from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import get_current_org_id, oauth2_scheme
from database import get_db
from schemas.transaction_schemas import TransactionOut
from services import auth_service, transaction_service


router = APIRouter(prefix="/transactions", tags=["transactions"])


def require_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return auth_service.get_authenticated_user_from_token(db, token)


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    user_id: int | None = None,
    limit: int = 100,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    return transaction_service.list_transactions_service(
        db,
        user_id=user_id,
        organisation_id=org_id,
        limit=limit,
    )


@router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction(
    transaction_id: int,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    return transaction_service.get_transaction_service(db, transaction_id, organisation_id=org_id)
