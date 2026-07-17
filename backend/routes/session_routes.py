from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from auth import oauth2_scheme
from database import get_db
from schemas.session_schemas import SessionCreate, SessionOut
from services import auth_service, session_service


router = APIRouter(prefix="/sessions", tags=["sessions"])


def require_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return auth_service.get_authenticated_user_from_token(db, token)


@router.get("", response_model=list[SessionOut], dependencies=[Depends(require_auth)])
def list_sessions(
    user_id: int | None = None,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
):
    return session_service.list_sessions_service(db, user_id=user_id, status=status_filter)


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_auth)])
def create_session(payload: SessionCreate, db: Session = Depends(get_db)):
    return session_service.create_session_service(db, payload)


@router.get("/{session_id}", response_model=SessionOut, dependencies=[Depends(require_auth)])
def get_session(session_id: int, db: Session = Depends(get_db)):
    return session_service.get_session_service(db, session_id)


@router.post("/{session_id}/end", response_model=SessionOut, dependencies=[Depends(require_auth)])
def end_session(session_id: int, db: Session = Depends(get_db)):
    return session_service.end_session_service(db, session_id)
