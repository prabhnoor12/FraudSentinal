from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from auth import oauth2_scheme
from database import get_db
from schemas.limit_tracking_schemas import (
    LimitUsageRecordCreate,
    LimitUsageRecordOut,
    UsageLimitCreate,
    UsageLimitOut,
)
from services import auth_service, limit_tracking_service


router = APIRouter(prefix="/limit-tracking", tags=["limit-tracking"])


def require_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return auth_service.get_authenticated_user_from_token(db, token)


@router.get("/limits", response_model=list[UsageLimitOut], dependencies=[Depends(require_auth)])
def list_usage_limits(
    user_id: int | None = None,
    organisation_id: int | None = None,
    limit_type: str | None = None,
    db: Session = Depends(get_db),
):
    return limit_tracking_service.list_usage_limits_service(
        db,
        user_id=user_id,
        organisation_id=organisation_id,
        limit_type=limit_type,
    )


@router.post("/limits", response_model=UsageLimitOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_auth)])
def create_usage_limit(payload: UsageLimitCreate, db: Session = Depends(get_db)):
    return limit_tracking_service.create_usage_limit_service(db, payload)


@router.get("/records", response_model=list[LimitUsageRecordOut], dependencies=[Depends(require_auth)])
def list_limit_usage_records(
    usage_limit_id: int | None = None,
    db: Session = Depends(get_db),
):
    return limit_tracking_service.list_limit_usage_records_service(
        db,
        usage_limit_id=usage_limit_id,
    )


@router.post("/records", response_model=LimitUsageRecordOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_auth)])
def create_limit_usage_record(payload: LimitUsageRecordCreate, db: Session = Depends(get_db)):
    return limit_tracking_service.create_limit_usage_record_service(db, payload)
