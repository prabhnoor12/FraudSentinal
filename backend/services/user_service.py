from sqlalchemy.orm import Session

from cruds import user_crud
from schemas.user_schemas import UserCreate, UserUpdate
from utils.exception_handling_utils import ConflictError, NotFoundError, ValidationError
from utils.security_utils import normalize_email, is_strong_password
from auth import hash_password


def create_user_service(
    db: Session, payload: UserCreate, organisation_id: int | None = None
):
    email = normalize_email(payload.email)
    if user_crud.get_user_by_email(db, email):
        raise ConflictError("User with this email already exists")

    # Password strength validation
    user_info = {
        "email": email,
        "full_name": payload.full_name or "",
        "phone": payload.phone or "",
    }
    if not is_strong_password(payload.password, user_info):
        raise ValidationError("Password does not meet complexity requirements")

    data = payload.model_dump()
    data["email"] = email
    data["organisation_id"] = organisation_id
    data["password_hash"] = hash_password(data.pop("password"))

    return user_crud.create_user(db, **data)


def list_users_service(
    db: Session,
    *,
    organisation_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
):
    items = user_crud.list_users(
        db,
        organisation_id=organisation_id,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    total = user_crud.count_users(db, organisation_id=organisation_id)
    return items, total


def get_user_service(db: Session, user_id: int, organisation_id: int | None = None):
    user = user_crud.get_user_by_id(db, user_id)
    if not user:
        raise NotFoundError("User not found")

    if organisation_id is not None and user.organisation_id != organisation_id:
        raise NotFoundError("User not found")

    return user


def update_user_service(
    db: Session, user_id: int, payload: UserUpdate, organisation_id: int | None = None
):
    user = get_user_service(db, user_id, organisation_id=organisation_id)
    updates = payload.model_dump(exclude_unset=True)

    if "password" in updates:
        password = updates.pop("password")
        user_info = {
            "email": updates.get("email", user.email),
            "full_name": updates.get("full_name", user.full_name or ""),
            "phone": updates.get("phone", user.phone or ""),
        }
        if not is_strong_password(password, user_info):
            raise ValidationError("Password does not meet complexity requirements")
        updates["password_hash"] = hash_password(password)

    if "email" in updates:
        updates["email"] = normalize_email(updates["email"])
        existing = user_crud.get_user_by_email(db, updates["email"])
        if existing and existing.id != user.id:
            raise ConflictError("User with this email already exists")

    return user_crud.update_user(db, user, **updates)


def delete_user_service(
    db: Session, user_id: int, organisation_id: int | None = None
) -> None:
    user = get_user_service(db, user_id, organisation_id=organisation_id)
    user_crud.delete_user(db, user)
