from sqlalchemy.orm import Session

from cruds import user_crud
from schemas.user_schemas import UserCreate, UserUpdate
from utils.exception_handling_utils import ConflictError, NotFoundError
from utils.security_utils import normalize_email


def create_user_service(db: Session, payload: UserCreate, organisation_id: int | None = None):
    email = normalize_email(payload.email)
    if user_crud.get_user_by_email(db, email):
        raise ConflictError("User with this email already exists")
    return user_crud.create_user(
        db,
        email=email,
        organisation_id=organisation_id,
        full_name=payload.full_name,
        is_active=payload.is_active,
    )


def list_users_service(db: Session, *, organisation_id: int | None = None, skip: int = 0, limit: int = 100):
    return user_crud.list_users(db, organisation_id=organisation_id, skip=skip, limit=limit)


def get_user_service(db: Session, user_id: int, organisation_id: int | None = None):
    user = user_crud.get_user_by_id(db, user_id)
    if not user:
        raise NotFoundError("User not found")

    if organisation_id is not None and user.organisation_id != organisation_id:
        raise NotFoundError("User not found")

    return user


def update_user_service(db: Session, user_id: int, payload: UserUpdate, organisation_id: int | None = None):
    user = get_user_service(db, user_id, organisation_id=organisation_id)
    updates = payload.model_dump(exclude_unset=True)
    if "email" in updates:
        updates["email"] = normalize_email(updates["email"])
        existing = user_crud.get_user_by_email(db, updates["email"])
        if existing and existing.id != user.id:
            raise ConflictError("User with this email already exists")
    return user_crud.update_user(db, user, **updates)


def delete_user_service(db: Session, user_id: int, organisation_id: int | None = None) -> None:
    user = get_user_service(db, user_id, organisation_id=organisation_id)
    user_crud.delete_user(db, user)
