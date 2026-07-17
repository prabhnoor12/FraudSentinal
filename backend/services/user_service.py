from sqlalchemy.orm import Session

from cruds import user_crud
from schemas.user_schemas import UserCreate, UserUpdate
from utils.exception_handling_utils import ConflictError, NotFoundError
from utils.security_utils import normalize_email


def create_user_service(db: Session, payload: UserCreate):
    email = normalize_email(payload.email)
    if user_crud.get_user_by_email(db, email):
        raise ConflictError("User with this email already exists")
    return user_crud.create_user(
        db,
        email=email,
        full_name=payload.full_name,
        is_active=payload.is_active,
    )


def list_users_service(db: Session, *, skip: int = 0, limit: int = 100):
    return user_crud.list_users(db, skip=skip, limit=limit)


def get_user_service(db: Session, user_id: int):
    user = user_crud.get_user_by_id(db, user_id)
    if not user:
        raise NotFoundError("User not found")
    return user


def update_user_service(db: Session, user_id: int, payload: UserUpdate):
    user = get_user_service(db, user_id)
    updates = payload.model_dump(exclude_unset=True)
    if "email" in updates:
        updates["email"] = normalize_email(updates["email"])
        existing = user_crud.get_user_by_email(db, updates["email"])
        if existing and existing.id != user.id:
            raise ConflictError("User with this email already exists")
    return user_crud.update_user(db, user, **updates)


def delete_user_service(db: Session, user_id: int) -> None:
    user = get_user_service(db, user_id)
    user_crud.delete_user(db, user)
