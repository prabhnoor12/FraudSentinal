from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from auth import get_current_org_id, oauth2_scheme
from database import get_db
from schemas.user_schemas import UserCreate, UserListResponse, UserOut, UserUpdate
from services import auth_service, user_service
from utils.pagination_utils import (
    build_paginated_payload,
    normalize_limit,
    normalize_offset,
    normalize_sort_dir,
)


router = APIRouter(prefix="/users", tags=["users"])


def require_auth(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    return auth_service.get_authenticated_user_from_token(db, token)


def require_admin(
    user=Depends(require_auth),
):
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )
    return user


@router.get("", response_model=UserListResponse)
def list_users(
    request: Request,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    normalized_offset = normalize_offset(offset)
    normalized_limit = normalize_limit(limit, default=100, maximum=200)
    items, total = user_service.list_users_service(
        db,
        organisation_id=org_id,
        offset=normalized_offset,
        limit=normalized_limit,
        sort_by=sort_by,
        sort_dir=normalize_sort_dir(sort_dir),
    )
    return build_paginated_payload(
        request=request,
        items=items,
        total=total,
        limit=normalized_limit,
        offset=normalized_offset,
    )


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
    return user_service.update_user_service(
        db, user_id, payload, organisation_id=org_id
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    user_service.delete_user_service(db, user_id, organisation_id=org_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/{user_id}/role", response_model=UserOut, dependencies=[Depends(require_admin)]
)
def update_user_role(
    user_id: int,
    role: str,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """Update a user's role within the organisation (Admin only)."""
    if role not in ["admin", "investigator"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    return user_service.update_user_service(
        db, user_id, UserUpdate(role=role), organisation_id=org_id
    )
