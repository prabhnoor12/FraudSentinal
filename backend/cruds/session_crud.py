from datetime import datetime

from sqlalchemy.orm import Session

from models.session_models import UserSession


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
    return db.query(UserSession).filter(UserSession.session_token == session_token).first()


def list_sessions(db: Session, *, user_id: int | None = None, status: str | None = None) -> list[UserSession]:
    query = db.query(UserSession)
    if user_id is not None:
        query = query.filter(UserSession.user_id == user_id)
    if status is not None:
        query = query.filter(UserSession.status == status)
    return query.order_by(UserSession.started_at.desc()).all()


def end_session(db: Session, session: UserSession) -> UserSession:
    session.status = "ended"
    session.ended_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return session
