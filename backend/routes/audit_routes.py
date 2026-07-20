from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from auth import get_current_org_id, oauth2_scheme
from database import get_db
from schemas.audit_schemas import AuditLogListResponse
from services import auth_service, audit_service
from utils.pagination_utils import (
    build_paginated_payload,
    normalize_limit,
    normalize_offset,
    normalize_sort_dir,
)

router = APIRouter(prefix="/audit", tags=["audit"])


def require_admin(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """Secondary permission check: ensure user has admin role."""
    user = auth_service.get_authenticated_user_from_token(db, token)
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Secondary permission check failed: Admin role required for audit access",
        )
    return user


@router.get("", response_model=AuditLogListResponse, dependencies=[Depends(require_admin)])
def list_audit_logs(
    request: Request,
    event_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    user_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """List audit logs with multi-condition filtering and tenant isolation."""
    normalized_limit = normalize_limit(limit, default=100, maximum=500)
    normalized_offset = normalize_offset(offset)
    items, total = audit_service.AuditService.list_logs(
        db,
        organisation_id=org_id,
        event_type=event_type,
        resource_type=resource_type,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        limit=normalized_limit,
        offset=normalized_offset,
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


@router.get("/stats", dependencies=[Depends(require_admin)])
def get_audit_stats(
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """Get aggregate statistics for audit logs."""
    return audit_service.AuditService.get_stats(db, organisation_id=org_id)


@router.get("/export", dependencies=[Depends(require_admin)])
def export_audit_logs(
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """Export audit logs as CSV."""
    csv_content = audit_service.AuditService.export_logs_csv(db, organisation_id=org_id)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=audit_logs_{org_id}.csv"
        },
    )
