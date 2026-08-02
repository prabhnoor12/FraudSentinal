from sqlalchemy.orm import Session

from cruds import session_crud, user_crud
from schemas.session_schemas import SessionCreate
from utils.exception_handling_utils import ConflictError, NotFoundError
from utils.security_utils import generate_secret_key
from utils.ownership_utils import require_session_in_organisation, require_user_in_organisation


def create_session_service(
    db: Session,
    payload: SessionCreate,
    *,
    organisation_id: int | None = None,
):
    target_organisation_id = payload.organisation_id

    if organisation_id is not None:
        if target_organisation_id is not None and target_organisation_id != organisation_id:
            raise NotFoundError("User not found")
        target_organisation_id = organisation_id
        require_user_in_organisation(
            db,
            user_id=payload.user_id,
            organisation_id=organisation_id,
        )
    else:
        user = user_crud.get_user_by_id(db, payload.user_id)
        if not user:
            raise NotFoundError("User not found")
        if target_organisation_id is None:
            target_organisation_id = user.organisation_id
        if user.organisation_id != target_organisation_id:
            raise NotFoundError("User not found")

    if target_organisation_id is None:
        raise NotFoundError("User not found")

    session_token = payload.session_token or generate_secret_key(24)
    if session_crud.get_session_by_token(db, session_token):
        raise ConflictError("Session token already exists")
    return session_crud.create_session(
        db,
        user_id=payload.user_id,
        organisation_id=target_organisation_id,
        session_token=session_token,
        ip_address=payload.ip_address,
        user_agent=payload.user_agent,
        status=payload.status,
    )


def list_sessions_service(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "started_at",
    sort_dir: str = "desc",
):
    items = session_crud.list_sessions(
        db,
        user_id=user_id,
        organisation_id=organisation_id,
        status=status,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    total = session_crud.count_sessions(
        db,
        user_id=user_id,
        organisation_id=organisation_id,
        status=status,
    )
    return items, total


def get_session_service(
    db: Session,
    session_id: int,
    *,
    organisation_id: int | None = None,
):
    if organisation_id is not None:
        return require_session_in_organisation(
            db,
            session_id=session_id,
            organisation_id=organisation_id,
        )
    session = session_crud.get_session_by_id(db, session_id)
    if not session:
        raise NotFoundError("Session not found")
    return session


def end_session_service(
    db: Session,
    session_id: int,
    *,
    organisation_id: int | None = None,
):
    session = get_session_service(
        db,
        session_id,
        organisation_id=organisation_id,
    )
    return session_crud.end_session(db, session)
