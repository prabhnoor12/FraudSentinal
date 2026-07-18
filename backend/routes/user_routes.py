from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from auth import get_current_org_id, oauth2_scheme
from database import get_db
from schemas.user_schemas import UserCreate, UserOut, UserUpdate
from services import auth_service, user_service


router = APIRouter(prefix="/users", tags=["users"])


def require_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return auth_service.get_authenticated_user_from_token(db, token)


@router.get("", response_model=list[UserOut])
def list_users(
    skip: int = 0,
    limit: int = 100,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    return user_service.list_users_service(db, organisation_id=org_id, skip=skip, limit=limit)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    # For now, users created via this route are assigned to the same org as the creator
    # In a real system, there might be a system admin role that can assign any org
    return user_service.create_user_service(db, payload, organisation_id=org_id)


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    return user_service.get_user_service(db, user_id, organisation_id=org_id)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    return user_service.update_user_service(db, user_id, payload, organisation_id=org_id)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    user_service.delete_user_service(db, user_id, organisation_id=org_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
