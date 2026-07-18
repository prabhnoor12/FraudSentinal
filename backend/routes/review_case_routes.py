from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import get_current_org_id, oauth2_scheme
from database import get_db
from schemas.review_case_schemas import ReviewCaseOut, ReviewCaseUpdate
from services import auth_service, review_case_service

router = APIRouter(prefix="/review-cases", tags=["review-cases"])


def require_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return auth_service.get_authenticated_user_from_token(db, token)


@router.get("", response_model=list[ReviewCaseOut])
def list_review_cases(
    transaction_id: int | None = None,
    decision_id: int | None = None,
    status: str | None = None,
    limit: int = 200,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    return review_case_service.list_review_cases_service(
        db,
        organisation_id=org_id,
        transaction_id=transaction_id,
        decision_id=decision_id,
        status=status,
        limit=limit,
    )


@router.get("/{case_id}", response_model=ReviewCaseOut)
def get_review_case(
    case_id: int,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    return review_case_service.get_review_case_service(db, case_id, organisation_id=org_id)


@router.put("/{case_id}", response_model=ReviewCaseOut)
def update_review_case(
    case_id: int,
    payload: ReviewCaseUpdate,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    return review_case_service.update_review_case_service(db, case_id, payload, organisation_id=org_id)
