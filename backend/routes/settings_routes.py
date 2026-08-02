from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import get_current_org_id, oauth2_scheme
from database import get_db
from schemas.settings_schemas import (
    OrganisationSettingsCreate,
    OrganisationSettingsOut,
    OrganisationSettingsUpdate,
)
from services import auth_service, settings_service
from utils.ownership_utils import require_organisation


router = APIRouter(prefix="/settings", tags=["settings"])


def require_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return auth_service.get_authenticated_user_from_token(db, token)


@router.post(
    "",
    response_model=OrganisationSettingsOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_auth)],
)
def create_settings(
    payload: OrganisationSettingsCreate,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    payload.organisation_id = org_id
    return settings_service.create_settings_service(db, payload, organisation_id=org_id)


@router.get(
    "/{organisation_id}",
    response_model=OrganisationSettingsOut,
    dependencies=[Depends(require_auth)],
)
def get_settings(
    organisation_id: int,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    require_organisation(db, organisation_id)
    if organisation_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation settings not found")
    return settings_service.get_settings_service(db, organisation_id)


@router.put(
    "/{organisation_id}",
    response_model=OrganisationSettingsOut,
    dependencies=[Depends(require_auth)],
)
def update_settings(
    organisation_id: int,
    payload: OrganisationSettingsUpdate,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    require_organisation(db, organisation_id)
    if organisation_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation settings not found")
    return settings_service.update_settings_service(db, organisation_id, payload)
