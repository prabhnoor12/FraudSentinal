from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy.orm import Session

from auth import get_current_org_id, oauth2_scheme
from database import get_db
from services import auth_service, audit_service
from schemas.audit_schemas import AuditContext

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
            detail="Secondary permission check failed: Admin role required for audit access"
        )
    return user

@router.get("", dependencies=[Depends(require_admin)])
def list_audit_logs(
    event_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    user_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """List audit logs with multi-condition filtering and tenant isolation."""
    return audit_service.AuditService.list_logs(
        db,
        organisation_id=org_id,
        event_type=event_type,
        resource_type=resource_type,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset
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
        headers={"Content-Disposition": f"attachment; filename=audit_logs_{org_id}.csv"}
    )
