from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from models.user_models import User


def create_user(
    db: Session,
    *,
    email: str,
    organisation_id: int | None = None,
    full_name: str | None = None,
    phone: str | None = None,
    role: str = "investigator",
    is_active: bool = True,
    password_hash: str | None = None,
) -> User:
    user = User(
        email=email,
        organisation_id=organisation_id,
        full_name=full_name,
        phone=phone,
        role=role,
        is_active=is_active,
        password_hash=password_hash,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def list_users(
    db: Session,
    *,
    organisation_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> list[User]:
    query = db.query(User)
    if organisation_id is not None:
        query = query.filter(User.organisation_id == organisation_id)
    order_column = {
        "created_at": User.created_at,
        "updated_at": User.updated_at,
        "email": User.email,
        "id": User.id,
    }.get(sort_by, User.created_at)
    order_func = asc if sort_dir == "asc" else desc
    return (
        query.order_by(order_func(order_column), desc(User.id))
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_users(db: Session, *, organisation_id: int | None = None) -> int:
    query = db.query(func.count(User.id))
    if organisation_id is not None:
        query = query.filter(User.organisation_id == organisation_id)
    return query.scalar() or 0


def update_user(db: Session, user: User, **updates) -> User:
    for field, value in updates.items():
        if value is not None:
            setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user: User) -> None:
    db.delete(user)
    db.commit()
