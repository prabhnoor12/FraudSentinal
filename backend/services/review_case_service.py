from __future__ import annotations

from datetime import datetime, UTC

from sqlalchemy.orm import Session

from typing import Optional

from cruds import decision_crud, review_case_crud
from schemas.audit_schemas import AuditContext
from schemas.review_case_schemas import (
    ReviewCaseCreate,
    ReviewCaseManualOverride,
    ReviewCaseReopen,
    ReviewCaseResolve,
    ReviewCaseStatus,
    ReviewCaseUpdate,
    ReviewCaseStatsOut,
)
from services.audit_service import AuditService
from utils.exception_handling_utils import ConflictError, NotFoundError, ValidationError
from utils.ownership_utils import require_transaction_and_decision_in_organisation


def _get_case_organisation_id(db: Session, *, decision_id: int) -> int:
    decision = decision_crud.get_decision_by_id(db, decision_id)
    if not decision:
        raise NotFoundError("Decision not found")
    return decision.organisation_id


def _ensure_case_owners_exist(
    db: Session, *, transaction_id: int, decision_id: int
) -> tuple[object, object]:
    return require_transaction_and_decision_in_organisation(
        db,
        transaction_id=transaction_id,
        decision_id=decision_id,
        organisation_id=_get_case_organisation_id(db, decision_id=decision_id),
    )


def _record_review_feedback(
    db: Session,
    *,
    review_case,
    action: str,
    notes: str | None = None,
) -> None:
    decision = decision_crud.get_decision_by_id(db, review_case.decision_id)
    if not decision:
        return

    snapshot = dict(decision.scoring_snapshot or {})
    feedback = dict(snapshot.get("review_feedback") or {})
    history = list(feedback.get("history") or [])
    history.append(
        {
            "action": action,
            "review_case_id": review_case.id,
            "resolution": review_case.resolution,
            "status": review_case.status,
            "notes": notes,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
    )
    feedback.update(
        {
            "latest_action": action,
            "latest_resolution": review_case.resolution,
            "latest_status": review_case.status,
            "history": history,
        }
    )
    snapshot["review_feedback"] = feedback
    decision.scoring_snapshot = snapshot
    db.add(decision)
    db.commit()
    db.refresh(decision)


def _map_override_resolution_to_decision(resolution: str) -> str:
    if resolution in {"approved_by_analyst", "false_positive"}:
        return "approve"
    if resolution in {"declined_by_analyst", "fraud_confirmed"}:
        return "decline"
    return "review"


def create_review_case_service(
    db: Session, payload: ReviewCaseCreate, *, commit: bool = True
):
    transaction, decision = _ensure_case_owners_exist(
        db, transaction_id=payload.transaction_id, decision_id=payload.decision_id
    )
    if payload.organisation_id != decision.organisation_id:
        raise NotFoundError("Decision not found")
    if payload.user_id != transaction.user_id:
        raise ValidationError("Transaction does not belong to the target user")
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

    _record_review_feedback(
        db,
        review_case=result,
        action="resolve",
        notes=payload.notes,
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

    _record_review_feedback(
        db,
        review_case=result,
        action="reopen",
        notes=payload.notes,
    )

    return result


def apply_manual_override_service(
    db: Session,
    case_id: int,
    payload: ReviewCaseManualOverride,
    organisation_id: int | None = None,
    audit_ctx: Optional[AuditContext] = None,
):
    """Apply an analyst override and persist the reason on both the case and decision."""
    review_case = get_review_case_service(db, case_id, organisation_id=organisation_id)
    decision = decision_crud.get_decision_by_id(db, review_case.decision_id)
    if not decision:
        raise NotFoundError("Decision not found")

    override_decision = _map_override_resolution_to_decision(payload.resolution.value)
    updates = {
        "status": ReviewCaseStatus.resolved,
        "resolution": payload.resolution,
        "notes": payload.notes or review_case.notes,
        "resolved_at": datetime.now(UTC),
    }
    merged_metadata = (review_case.case_metadata or {}).copy()
    merged_metadata.update(payload.metadata or {})
    merged_metadata["manual_override"] = {
        "override_reason": payload.override_reason,
        "resolution": payload.resolution.value,
        "notes": payload.notes,
        "review_case_id": review_case.id,
        "decision_id": decision.id,
        "recorded_at": datetime.now(UTC).isoformat(),
        "analyst_user_id": getattr(audit_ctx, "user_id", None),
    }
    updates["metadata"] = merged_metadata

    result = review_case_crud.update_review_case(db, review_case, commit=False, **updates)

    snapshot = dict(decision.scoring_snapshot or {})
    snapshot["manual_override"] = merged_metadata["manual_override"]
    snapshot["manual_override"]["previous_decision"] = decision.decision
    snapshot["manual_override"]["new_decision"] = override_decision
    snapshot["manual_override"]["organisation_id"] = decision.organisation_id
    snapshot["manual_override"]["status"] = getattr(result.status, "value", result.status)
    snapshot["manual_override"]["resolution"] = getattr(
        result.resolution, "value", result.resolution
    )
    decision.decision = override_decision
    decision.scoring_snapshot = snapshot
    db.add(decision)
    db.commit()
    db.refresh(decision)

    if audit_ctx:
        AuditService.log_case_action(
            db,
            user_id=audit_ctx.user_id,
            organisation_id=audit_ctx.organisation_id,
            action="manual_override",
            case_id=case_id,
            notes=payload.override_reason,
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


def get_review_case_stats_service(
    db: Session, organisation_id: int, *, overdue_hours: int = 24
) -> ReviewCaseStatsOut:
    open_cases = review_case_crud.list_review_cases(
        db,
        organisation_id=organisation_id,
        status=ReviewCaseStatus.open,
        offset=0,
        limit=10,
        sort_by="created_at",
        sort_dir="desc",
    )
    total_open = review_case_crud.count_review_cases(
        db, organisation_id=organisation_id, status=ReviewCaseStatus.open
    )
    total_resolved = review_case_crud.count_review_cases(
        db, organisation_id=organisation_id, status=ReviewCaseStatus.resolved
    )
    oldest_open_case_at = open_cases[-1].created_at if open_cases else None
    overdue_cutoff = datetime.now(UTC).timestamp() - overdue_hours * 3600
    overdue_count = sum(
        1 for case in open_cases if case.created_at and case.created_at.timestamp() < overdue_cutoff
    )
    return ReviewCaseStatsOut(
        total=total_open + total_resolved,
        open_count=total_open,
        resolved_count=total_resolved,
        overdue_count=overdue_count,
        oldest_open_case_at=oldest_open_case_at,
        recent_open_cases=open_cases,
    )
