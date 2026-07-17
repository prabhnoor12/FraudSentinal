from sqlalchemy.orm import Session

from cruds import organisation_crud
from schemas.organisation_schemas import OrganisationCreate, OrganisationUpdate
from utils.exception_handling_utils import ConflictError, NotFoundError


def create_organisation_service(db: Session, payload: OrganisationCreate):
    if payload.slug and organisation_crud.get_organisation_by_slug(db, payload.slug):
        raise ConflictError("Organisation slug already exists")
    return organisation_crud.create_organisation(
        db,
        name=payload.name,
        slug=payload.slug,
        is_active=payload.is_active,
    )


def list_organisations_service(db: Session, *, skip: int = 0, limit: int = 100):
    return organisation_crud.list_organisations(db, skip=skip, limit=limit)


def get_organisation_service(db: Session, organisation_id: int):
    organisation = organisation_crud.get_organisation_by_id(db, organisation_id)
    if not organisation:
        raise NotFoundError("Organisation not found")
    return organisation


def update_organisation_service(db: Session, organisation_id: int, payload: OrganisationUpdate):
    organisation = get_organisation_service(db, organisation_id)
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("slug"):
        existing = organisation_crud.get_organisation_by_slug(db, updates["slug"])
        if existing and existing.id != organisation.id:
            raise ConflictError("Organisation slug already exists")
    return organisation_crud.update_organisation(db, organisation, **updates)


def delete_organisation_service(db: Session, organisation_id: int) -> None:
    organisation = get_organisation_service(db, organisation_id)
    organisation_crud.delete_organisation(db, organisation)
