from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from auth import get_current_org_id, oauth2_scheme
from database import get_db
from schemas.organisation_schemas import OrganisationCreate, OrganisationOut, OrganisationUpdate
from services import auth_service, organisation_service, organisation_summary_service


router = APIRouter(prefix="/organisations", tags=["organisations"])


def require_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return auth_service.get_authenticated_user_from_token(db, token)


@router.get("", response_model=list[OrganisationOut])
def list_organisations(
    skip: int = 0,
    limit: int = 100,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    # For now, a user can only see their own organisation in the list
    # In a system admin context, this would be different
    return [organisation_service.get_organisation_service(db, org_id)]


@router.get("/dashboard/summary")
def get_organisation_summary(
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """Get a summary of activity for the organisation dashboard."""
    return organisation_summary_service.OrganisationSummaryService.get_dashboard_summary(db, organisation_id=org_id)


@router.post("", response_model=OrganisationOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_auth)])
def create_organisation(payload: OrganisationCreate, db: Session = Depends(get_db)):
    # Creation is still allowed for now, but usually restricted to system admins
    return organisation_service.create_organisation_service(db, payload)


@router.get("/{organisation_id}", response_model=OrganisationOut)
def get_organisation(
    organisation_id: int,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    if organisation_id != org_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")
    return organisation_service.get_organisation_service(db, organisation_id)


@router.put("/{organisation_id}", response_model=OrganisationOut)
def update_organisation(
    organisation_id: int,
    payload: OrganisationUpdate,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    if organisation_id != org_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")
    return organisation_service.update_organisation_service(db, organisation_id, payload)


@router.delete("/{organisation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organisation(
    organisation_id: int,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    if organisation_id != org_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")
    organisation_service.delete_organisation_service(db, organisation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
