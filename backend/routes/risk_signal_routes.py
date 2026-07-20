from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from auth import get_current_org_id, oauth2_scheme
from database import get_db
from schemas.risk_signal_schemas import RiskSignalListResponse, RiskSignalOut
from services import auth_service, risk_signal_service
from utils.pagination_utils import (
    build_paginated_payload,
    normalize_limit,
    normalize_offset,
    normalize_sort_dir,
)


router = APIRouter(prefix="/risk-signals", tags=["risk-signals"])


def require_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return auth_service.get_authenticated_user_from_token(db, token)


@router.get("", response_model=RiskSignalListResponse)
def list_risk_signals(
    request: Request,
    transaction_id: int | None = None,
    decision_id: int | None = None,
    offset: int = 0,
    limit: int = 200,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    normalized_offset = normalize_offset(offset)
    normalized_limit = normalize_limit(limit, default=100, maximum=200)
    items, total = risk_signal_service.list_risk_signals_service(
        db,
        organisation_id=org_id,
        transaction_id=transaction_id,
        decision_id=decision_id,
        offset=normalized_offset,
        limit=normalized_limit,
        sort_by=sort_by,
        sort_dir=normalize_sort_dir(sort_dir),
    )
    return build_paginated_payload(
        request=request,
        items=items,
        total=total,
        limit=normalized_limit,
        offset=normalized_offset,
    )


@router.get("/{risk_signal_id}", response_model=RiskSignalOut)
def get_risk_signal(
    risk_signal_id: int,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    return risk_signal_service.get_risk_signal_service(
        db, risk_signal_id, organisation_id=org_id
    )
