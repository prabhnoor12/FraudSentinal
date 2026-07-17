from sqlalchemy.orm import Session

from cruds import organisation_crud, settings_crud
from schemas.settings_schemas import OrganisationSettingsCreate, OrganisationSettingsUpdate
from utils.exception_handling_utils import ConflictError, NotFoundError


def create_settings_service(db: Session, payload: OrganisationSettingsCreate):
    if not organisation_crud.get_organisation_by_id(db, payload.organisation_id):
        raise NotFoundError("Organisation not found")
    if settings_crud.get_settings_by_organisation_id(db, payload.organisation_id):
        raise ConflictError("Settings already exist for this organisation")
    return settings_crud.create_settings(db, **payload.model_dump())


def get_settings_service(db: Session, organisation_id: int):
    settings = settings_crud.get_settings_by_organisation_id(db, organisation_id)
    if not settings:
        raise NotFoundError("Organisation settings not found")
    return settings


def update_settings_service(db: Session, organisation_id: int, payload: OrganisationSettingsUpdate):
    settings = get_settings_service(db, organisation_id)
    return settings_crud.update_settings(db, settings, **payload.model_dump(exclude_unset=True))
