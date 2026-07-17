from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from auth import oauth2_scheme
from database import get_db
from schemas.settings_schemas import (
    OrganisationSettingsCreate,
    OrganisationSettingsOut,
    OrganisationSettingsUpdate,
)
from services import auth_service, settings_service


router = APIRouter(prefix="/settings", tags=["settings"])


def require_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return auth_service.get_authenticated_user_from_token(db, token)


@router.post("", response_model=OrganisationSettingsOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_auth)])
def create_settings(payload: OrganisationSettingsCreate, db: Session = Depends(get_db)):
    return settings_service.create_settings_service(db, payload)


@router.get("/{organisation_id}", response_model=OrganisationSettingsOut, dependencies=[Depends(require_auth)])
def get_settings(organisation_id: int, db: Session = Depends(get_db)):
    return settings_service.get_settings_service(db, organisation_id)


@router.put("/{organisation_id}", response_model=OrganisationSettingsOut, dependencies=[Depends(require_auth)])
def update_settings(organisation_id: int, payload: OrganisationSettingsUpdate, db: Session = Depends(get_db)):
    return settings_service.update_settings_service(db, organisation_id, payload)
