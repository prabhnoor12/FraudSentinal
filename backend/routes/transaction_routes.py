from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from auth import get_current_org_id, oauth2_scheme
from database import get_db
from schemas.audit_schemas import AuditContext
from schemas.transaction_schemas import TransactionCreate, TransactionOut
from services import audit_service, auth_service, transaction_service


router = APIRouter(prefix="/transactions", tags=["transactions"])


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


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    user_id: int | None = None,
    limit: int = 100,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    return transaction_service.list_transactions_service(
        db,
        user_id=user_id,
        organisation_id=org_id,
        limit=limit,
    )


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate,
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
