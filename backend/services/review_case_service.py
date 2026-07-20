from __future__ import annotations

from datetime import datetime, UTC

from sqlalchemy.orm import Session

from typing import Optional

from cruds import decision_crud, review_case_crud, transaction_crud
from schemas.audit_schemas import AuditContext
from schemas.review_case_schemas import (
    ReviewCaseCreate,
    ReviewCaseReopen,
    ReviewCaseResolve,
    ReviewCaseStatus,
    ReviewCaseUpdate,
)
from services.audit_service import AuditService
from utils.exception_handling_utils import ConflictError, NotFoundError, ValidationError


def _ensure_case_owners_exist(
    db: Session, *, transaction_id: int, decision_id: int
) -> None:
    if not transaction_crud.get_transaction_by_id(db, transaction_id):
        raise NotFoundError("Transaction not found")
    if not decision_crud.get_decision_by_id(db, decision_id):
        raise NotFoundError("Decision not found")


def create_review_case_service(
    db: Session, payload: ReviewCaseCreate, *, commit: bool = True
):
    _ensure_case_owners_exist(
        db, transaction_id=payload.transaction_id, decision_id=payload.decision_id
    )
    if review_case_crud.get_review_case_by_decision_id(db, payload.decision_id):
        raise ConflictError("Review case already exists for this decision")
    return review_case_crud.create_review_case(
        db, commit=commit, **payload.model_dump()
    )


def create_review_case_if_needed(
    db: Session,
    *,
    transaction_id: int,
    decision_id: int,
    organisation_id: int,
    user_id: int,
    decision_value: str,
    commit: bool = True,
):
    if decision_value != "review":
        return None
    existing = review_case_crud.get_review_case_by_decision_id(db, decision_id)
    if existing:
        return existing
    return create_review_case_service(
        db,
        ReviewCaseCreate(
            transaction_id=transaction_id,
            decision_id=decision_id,
            organisation_id=organisation_id,
            user_id=user_id,
            status=ReviewCaseStatus.open,
            resolution=None,
            notes=None,
            metadata={},
        ),
        commit=commit,
    )


def get_review_case_service(
    db: Session, case_id: int, organisation_id: int | None = None
):
    review_case = review_case_crud.get_review_case_by_id(db, case_id)
    if not review_case:
        raise NotFoundError("Review case not found")

    if organisation_id is not None and review_case.organisation_id != organisation_id:
        raise NotFoundError("Review case not found")

    return review_case


def list_review_cases_service(
    db: Session,
    *,
    organisation_id: int | None = None,
    transaction_id: int | None = None,
    decision_id: int | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 200,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> tuple[list, int]:
    review_cases = review_case_crud.list_review_cases(
        db,
        organisation_id=organisation_id,
        transaction_id=transaction_id,
        decision_id=decision_id,
        status=status,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    total = review_case_crud.count_review_cases(
        db,
        organisation_id=organisation_id,
        transaction_id=transaction_id,
        decision_id=decision_id,
        status=status,
    )
    return review_cases, total


def update_review_case_service(
    db: Session,
    case_id: int,
    payload: ReviewCaseUpdate,
    organisation_id: int | None = None,
):
    review_case = get_review_case_service(db, case_id, organisation_id=organisation_id)
    updates = payload.model_dump(exclude_unset=True)

    requested_status = updates.get("status")
    requested_resolution = updates.get("resolution")

    if (
        requested_resolution is not None
        and requested_status != ReviewCaseStatus.resolved
    ):
        raise ValidationError("Resolution can only be set when status is resolved")

    if requested_status == ReviewCaseStatus.resolved:
        effective_resolution = (
            requested_resolution if "resolution" in updates else review_case.resolution
        )
        if effective_resolution is None:
            raise ValidationError("Resolution is required when resolving a review case")
        updates["resolved_at"] = (
            datetime.now(UTC)
            if review_case.resolved_at is None
            else review_case.resolved_at
        )
    elif requested_status is not None:
        updates["resolution"] = None
        updates["resolved_at"] = None

    return review_case_crud.update_review_case(db, review_case, **updates)


def resolve_review_case_service(
    db: Session,
    case_id: int,
    payload: ReviewCaseResolve,
    organisation_id: int | None = None,
    audit_ctx: Optional[AuditContext] = None,
):
    """Explicitly resolve a review case."""
    review_case = get_review_case_service(db, case_id, organisation_id=organisation_id)

    if review_case.status == ReviewCaseStatus.resolved:
        raise ValidationError("Review case is already resolved")

    updates = {
        "status": ReviewCaseStatus.resolved,
        "resolution": payload.resolution,
        "notes": payload.notes or review_case.notes,
        "resolved_at": datetime.now(UTC),
    }
    if payload.metadata:
        merged_metadata = (review_case.case_metadata or {}).copy()
        merged_metadata.update(payload.metadata)
        updates["metadata"] = merged_metadata

    result = review_case_crud.update_review_case(db, review_case, **updates)

    if audit_ctx:
        AuditService.log_case_action(
            db,
            user_id=audit_ctx.user_id,
            organisation_id=audit_ctx.organisation_id,
            action="resolve",
            case_id=case_id,
            notes=payload.notes,
            ip_address=audit_ctx.ip_address,
            user_agent=audit_ctx.user_agent,
        )

    return result


def reopen_review_case_service(
    db: Session,
    case_id: int,
    payload: ReviewCaseReopen,
    organisation_id: int | None = None,
    audit_ctx: Optional[AuditContext] = None,
):
    """Explicitly reopen a resolved review case."""
    review_case = get_review_case_service(db, case_id, organisation_id=organisation_id)

    if review_case.status == ReviewCaseStatus.open:
        raise ValidationError("Review case is already open")

    updates = {
        "status": ReviewCaseStatus.open,
        "resolution": None,
        "resolved_at": None,
        "notes": payload.notes or review_case.notes,
    }
    if payload.metadata:
        merged_metadata = (review_case.case_metadata or {}).copy()
        merged_metadata.update(payload.metadata)
        updates["metadata"] = merged_metadata

    result = review_case_crud.update_review_case(db, review_case, **updates)

    if audit_ctx:
        AuditService.log_case_action(
            db,
            user_id=audit_ctx.user_id,
            organisation_id=audit_ctx.organisation_id,
            action="reopen",
            case_id=case_id,
            notes=payload.notes,
            ip_address=audit_ctx.ip_address,
            user_agent=audit_ctx.user_agent,
        )

    return result


def list_my_queue_service(
    db: Session,
    organisation_id: int,
    offset: int = 0,
    limit: int = 100,
) -> tuple[list, int]:
    """List open review cases for the current organisation (my queue)."""
    review_cases = review_case_crud.list_review_cases(
        db,
        organisation_id=organisation_id,
        status=ReviewCaseStatus.open,
        offset=offset,
        limit=limit,
    )
    total = review_case_crud.count_review_cases(
        db,
        organisation_id=organisation_id,
        status=ReviewCaseStatus.open,
    )
    return review_cases, total
