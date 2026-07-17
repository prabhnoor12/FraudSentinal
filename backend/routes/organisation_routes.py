from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from auth import oauth2_scheme
from database import get_db
from schemas.organisation_schemas import OrganisationCreate, OrganisationOut, OrganisationUpdate
from services import auth_service, organisation_service


router = APIRouter(prefix="/organisations", tags=["organisations"])


def require_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return auth_service.get_authenticated_user_from_token(db, token)


@router.get("", response_model=list[OrganisationOut], dependencies=[Depends(require_auth)])
def list_organisations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return organisation_service.list_organisations_service(db, skip=skip, limit=limit)


@router.post("", response_model=OrganisationOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_auth)])
def create_organisation(payload: OrganisationCreate, db: Session = Depends(get_db)):
    return organisation_service.create_organisation_service(db, payload)


@router.get("/{organisation_id}", response_model=OrganisationOut, dependencies=[Depends(require_auth)])
def get_organisation(organisation_id: int, db: Session = Depends(get_db)):
    return organisation_service.get_organisation_service(db, organisation_id)


@router.put("/{organisation_id}", response_model=OrganisationOut, dependencies=[Depends(require_auth)])
def update_organisation(organisation_id: int, payload: OrganisationUpdate, db: Session = Depends(get_db)):
    return organisation_service.update_organisation_service(db, organisation_id, payload)


@router.delete("/{organisation_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_auth)])
def delete_organisation(organisation_id: int, db: Session = Depends(get_db)):
    organisation_service.delete_organisation_service(db, organisation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
