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
    db: Session, *, organisation_id: int | None = None, skip: int = 0, limit: int = 100
) -> list[User]:
    query = db.query(User)
    if organisation_id is not None:
        query = query.filter(User.organisation_id == organisation_id)
    return query.offset(skip).limit(limit).all()


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
