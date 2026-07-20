from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from auth import get_current_org_id, oauth2_scheme
from database import get_db
from schemas.audit_schemas import AuditContext
from schemas.review_case_schemas import (
    ReviewCaseListResponse,
    ReviewCaseOut,
    ReviewCaseReopen,
    ReviewCaseResolve,
    ReviewCaseUpdate,
)
from services import auth_service, review_case_service
from utils.pagination_utils import (
    build_paginated_payload,
    normalize_limit,
    normalize_offset,
    normalize_sort_dir,
)

router = APIRouter(prefix="/review-cases", tags=["review-cases"])


def get_audit_ctx(
    request: Request,
    org_id: int = Depends(get_current_org_id),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> AuditContext:
    user = auth_service.get_authenticated_user_from_token(db, token)
    return AuditContext(
        user_id=user.id,
        organisation_id=org_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.get("", response_model=ReviewCaseListResponse)
def list_review_cases(
    request: Request,
    transaction_id: int | None = None,
    decision_id: int | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 200,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    normalized_offset = normalize_offset(offset)
    normalized_limit = normalize_limit(limit, default=100, maximum=200)
    items, total = review_case_service.list_review_cases_service(
        db,
        organisation_id=org_id,
        transaction_id=transaction_id,
        decision_id=decision_id,
        status=status,
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


@router.get("/{case_id}", response_model=ReviewCaseOut)
def get_review_case(
    case_id: int,
    org_id: int = Depends(get_current_org_id),
    audit_ctx: AuditContext = Depends(get_audit_ctx),
    db: Session = Depends(get_db),
):
    review_case = review_case_service.get_review_case_service(
        db, case_id, organisation_id=org_id
    )

    # Log access to review case
    from services.audit_service import AuditService

    AuditService.log_resource_access(
        db,
        user_id=audit_ctx.user_id,
        organisation_id=audit_ctx.organisation_id,
        resource_type="review_case",
        resource_id=str(case_id),
        ip_address=audit_ctx.ip_address,
        user_agent=audit_ctx.user_agent,
    )

    return review_case


@router.put("/{case_id}", response_model=ReviewCaseOut)
def update_review_case(
    case_id: int,
    payload: ReviewCaseUpdate,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    return review_case_service.update_review_case_service(
        db, case_id, payload, organisation_id=org_id
    )


@router.get("/queue/my", response_model=ReviewCaseListResponse)
def list_my_queue(
    request: Request,
    offset: int = 0,
    limit: int = 100,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """List open review cases for the current organisation (my queue)."""
    normalized_offset = normalize_offset(offset)
    normalized_limit = normalize_limit(limit, default=100, maximum=200)
    items, total = review_case_service.list_my_queue_service(
        db,
        organisation_id=org_id,
        offset=normalized_offset,
        limit=normalized_limit,
    )
    return build_paginated_payload(
        request=request,
        items=items,
        total=total,
        limit=normalized_limit,
        offset=normalized_offset,
    )


@router.post("/{case_id}/resolve", response_model=ReviewCaseOut)
def resolve_review_case(
    case_id: int,
    payload: ReviewCaseResolve,
    org_id: int = Depends(get_current_org_id),
    audit_ctx: AuditContext = Depends(get_audit_ctx),
    db: Session = Depends(get_db),
):
    """Explicitly resolve a review case."""
    return review_case_service.resolve_review_case_service(
        db, case_id, payload, organisation_id=org_id, audit_ctx=audit_ctx
    )


@router.post("/{case_id}/reopen", response_model=ReviewCaseOut)
def reopen_review_case(
    case_id: int,
    payload: ReviewCaseReopen,
    org_id: int = Depends(get_current_org_id),
    audit_ctx: AuditContext = Depends(get_audit_ctx),
    db: Session = Depends(get_db),
):
    """Explicitly reopen a resolved review case."""
    return review_case_service.reopen_review_case_service(
        db, case_id, payload, organisation_id=org_id, audit_ctx=audit_ctx
    )
