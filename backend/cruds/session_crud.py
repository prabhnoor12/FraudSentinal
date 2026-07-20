from datetime import datetime, UTC

from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from models.session_models import UserSession
from models.user_models import User


def create_session(
    db: Session,
    *,
    user_id: int,
    session_token: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    status: str = "active",
) -> UserSession:
    session = UserSession(
        user_id=user_id,
        session_token=session_token,
        ip_address=ip_address,
        user_agent=user_agent,
        status=status,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session_by_id(db: Session, session_id: int) -> UserSession | None:
    return db.query(UserSession).filter(UserSession.id == session_id).first()


def get_session_by_token(db: Session, session_token: str) -> UserSession | None:
    return (
        db.query(UserSession).filter(UserSession.session_token == session_token).first()
    )


def list_sessions(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "started_at",
    sort_dir: str = "desc",
) -> list[UserSession]:
    query = db.query(UserSession)
    if organisation_id is not None:
        query = query.join(User, User.id == UserSession.user_id).filter(
            User.organisation_id == organisation_id
        )
    if user_id is not None:
        query = query.filter(UserSession.user_id == user_id)
    if status is not None:
        query = query.filter(UserSession.status == status)
    order_column = {
        "started_at": UserSession.started_at,
        "ended_at": UserSession.ended_at,
        "status": UserSession.status,
        "id": UserSession.id,
    }.get(sort_by, UserSession.started_at)
    order_func = asc if sort_dir == "asc" else desc
    return (
        query.order_by(order_func(order_column), desc(UserSession.id))
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_sessions(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
    status: str | None = None,
) -> int:
    query = db.query(func.count(UserSession.id))
    if organisation_id is not None:
        query = query.join(User, User.id == UserSession.user_id).filter(
            User.organisation_id == organisation_id
        )
    if user_id is not None:
        query = query.filter(UserSession.user_id == user_id)
    if status is not None:
        query = query.filter(UserSession.status == status)
    return query.scalar() or 0


def end_session(db: Session, session: UserSession) -> UserSession:
    session.status = "ended"
    session.ended_at = datetime.now(UTC)
    db.commit()
    db.refresh(session)
    return session
