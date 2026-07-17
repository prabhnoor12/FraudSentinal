from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from auth import oauth2_scheme
from database import get_db
from schemas.user_schemas import UserCreate, UserOut, UserUpdate
from services import auth_service, user_service


router = APIRouter(prefix="/users", tags=["users"])


def require_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return auth_service.get_authenticated_user_from_token(db, token)


@router.get("", response_model=list[UserOut], dependencies=[Depends(require_auth)])
def list_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return user_service.list_users_service(db, skip=skip, limit=limit)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_auth)])
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    return user_service.create_user_service(db, payload)


@router.get("/{user_id}", response_model=UserOut, dependencies=[Depends(require_auth)])
def get_user(user_id: int, db: Session = Depends(get_db)):
    return user_service.get_user_service(db, user_id)


@router.put("/{user_id}", response_model=UserOut, dependencies=[Depends(require_auth)])
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)):
    return user_service.update_user_service(db, user_id, payload)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_auth)])
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user_service.delete_user_service(db, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
