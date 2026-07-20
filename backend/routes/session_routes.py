from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from auth import get_current_org_id, oauth2_scheme
from database import get_db
from schemas.session_schemas import SessionCreate, SessionListResponse, SessionOut
from services import auth_service, session_service
from utils.pagination_utils import (
    build_paginated_payload,
    normalize_limit,
    normalize_offset,
    normalize_sort_dir,
)


router = APIRouter(prefix="/sessions", tags=["sessions"])


def require_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return auth_service.get_authenticated_user_from_token(db, token)


@router.get("", response_model=SessionListResponse, dependencies=[Depends(require_auth)])
def list_sessions(
    request: Request,
    user_id: int | None = None,
    status_filter: str | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "started_at",
    sort_dir: str = "desc",
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    normalized_offset = normalize_offset(offset)
    normalized_limit = normalize_limit(limit, default=100, maximum=200)
    items, total = session_service.list_sessions_service(
        db,
        user_id=user_id,
        organisation_id=org_id,
        status=status_filter,
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


@router.post(
    "",
    response_model=SessionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_auth)],
)
def create_session(payload: SessionCreate, db: Session = Depends(get_db)):
    return session_service.create_session_service(db, payload)


@router.get(
    "/{session_id}", response_model=SessionOut, dependencies=[Depends(require_auth)]
)
def get_session(session_id: int, db: Session = Depends(get_db)):
    return session_service.get_session_service(db, session_id)


@router.post(
    "/{session_id}/end", response_model=SessionOut, dependencies=[Depends(require_auth)]
)
def end_session(session_id: int, db: Session = Depends(get_db)):
    return session_service.end_session_service(db, session_id)
