from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from auth_dependencies import (
    get_current_org_id,
    get_current_principal,
    require_scopes,
)
from database import get_db
from schemas.audit_schemas import AuditContext
from schemas.transaction_schemas import (
    TransactionCreate,
    TransactionListResponse,
    TransactionOut,
)
from services import audit_service, transaction_service
from utils.pagination_utils import (
    build_paginated_payload,
    normalize_limit,
    normalize_offset,
    normalize_sort_dir,
)


router = APIRouter(prefix="/transactions", tags=["transactions"])


def get_audit_ctx(
    request: Request,
    org_id: int = Depends(get_current_org_id),
    principal=Depends(get_current_principal),
) -> AuditContext:
    return AuditContext(
        user_id=getattr(principal.user, "id", None),
        organisation_id=org_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.get(
    "",
    response_model=TransactionListResponse,
    summary="List transactions",
    description="Returns transactions for the authenticated organisation using the standard v1 paginated list envelope.",
)
def list_transactions(
    request: Request,
    user_id: int | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    principal=Depends(require_scopes("transactions:read")),
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    items, total = transaction_service.list_transactions_service(
        db,
        user_id=user_id,
        organisation_id=org_id,
        offset=normalize_offset(offset),
        limit=normalize_limit(limit, default=100, maximum=200),
        sort_by=sort_by,
        sort_dir=normalize_sort_dir(sort_dir),
    )
    return build_paginated_payload(
        request=request,
        items=items,
        total=total,
        limit=normalize_limit(limit, default=100, maximum=200),
        offset=normalize_offset(offset),
    )


@router.post(
    "",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create transaction",
    description="Creates a transaction in the authenticated organisation. This endpoint requires an Idempotency-Key header in public API usage.",
)
def create_transaction(
    payload: TransactionCreate,
    principal=Depends(require_scopes("transactions:write")),
    org_id: int = Depends(get_current_org_id),
    audit_ctx: AuditContext = Depends(get_audit_ctx),
    db: Session = Depends(get_db),
):
    payload.organisation_id = org_id
    return transaction_service.create_transaction_service(
        db, payload, audit_ctx=audit_ctx
    )


@router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction(
    transaction_id: int,
    principal=Depends(require_scopes("transactions:read")),
    org_id: int = Depends(get_current_org_id),
    audit_ctx: AuditContext = Depends(get_audit_ctx),
    db: Session = Depends(get_db),
):
    transaction = transaction_service.get_transaction_service(
        db, transaction_id, organisation_id=org_id
    )

    # Log access to transaction
    audit_service.AuditService.log_resource_access(
        db,
        user_id=audit_ctx.user_id,
        organisation_id=audit_ctx.organisation_id,
        resource_type="transaction",
        resource_id=str(transaction_id),
        ip_address=audit_ctx.ip_address,
        user_agent=audit_ctx.user_agent,
    )

    return transaction
