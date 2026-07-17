from sqlalchemy.orm import Session

from models.user_models import User


def create_user(
    db: Session,
    *,
    email: str,
    full_name: str | None = None,
    is_active: bool = True,
    password_hash: str | None = None,
) -> User:
    user = User(
        email=email,
        full_name=full_name,
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


def list_users(db: Session, *, skip: int = 0, limit: int = 100) -> list[User]:
    return db.query(User).offset(skip).limit(limit).all()


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
