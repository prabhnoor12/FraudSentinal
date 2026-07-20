from datetime import UTC, datetime

from sqlalchemy.orm import Session

from cruds import billing_crud, organisation_crud, usage_crud, user_crud
from schemas.billing_schemas import (
    BillingPlanCreate,
    BillingRecordCreate,
    SubscriptionMutationInput,
)
from services import entitlement_service
from services.audit_service import AuditService
from utils.exception_handling_utils import ForbiddenError, NotFoundError, ValidationError

SUBSCRIPTION_ACTIONS = {
    "upgrade",
    "downgrade",
    "renew",
    "cancel",
    "payment_failed",
}


def create_billing_plan_service(db: Session, payload: BillingPlanCreate):
    if not organisation_crud.get_organisation_by_id(db, payload.organisation_id):
        raise NotFoundError("Organisation not found")
    return billing_crud.create_billing_plan(db, **payload.model_dump())


def list_billing_plans_service(
    db: Session,
    *,
    organisation_id: int | None = None,
    is_active: bool | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
):
    items = billing_crud.list_billing_plans(
        db,
        organisation_id=organisation_id,
        is_active=is_active,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    total = billing_crud.count_billing_plans(
        db,
        organisation_id=organisation_id,
        is_active=is_active,
    )
    return items, total


def create_billing_record_service(db: Session, payload: BillingRecordCreate):
    user = user_crud.get_user_by_id(db, payload.user_id)
    if not user or user.organisation_id != payload.organisation_id:
        raise NotFoundError("User not found")
    if not organisation_crud.get_organisation_by_id(db, payload.organisation_id):
        raise NotFoundError("Organisation not found")
    if payload.usage_event_id is not None:
        usage_events = usage_crud.list_usage_events(
            db,
            user_id=payload.user_id,
            organisation_id=payload.organisation_id,
        )
        if not any(event.id == payload.usage_event_id for event in usage_events):
            raise NotFoundError("Usage event not found")
    record = billing_crud.create_billing_record(db, **payload.model_dump())
    entitlement_service.invalidate_entitlement_cache(payload.organisation_id)
    return record


def list_billing_records_service(
    db: Session,
    *,
    user_id: int | None = None,
    organisation_id: int | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
):
    items = billing_crud.list_billing_records(
        db,
        user_id=user_id,
        organisation_id=organisation_id,
        status=status,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    total = billing_crud.count_billing_records(
        db,
        user_id=user_id,
        organisation_id=organisation_id,
        status=status,
    )
    return items, total


def _require_subscription_admin(principal) -> None:
    if principal.user and principal.user.role != "admin":
        raise ForbiddenError("Only organisation admins can manage subscriptions")


def _get_required_billing_record(
    db: Session,
    *,
    organisation_id: int,
    billing_record_id: int | None,
):
    if billing_record_id is None:
        raise ValidationError("billing_record_id is required for this billing mutation")
    billing_record = billing_crud.get_billing_record_by_id(db, billing_record_id)
    if not billing_record or billing_record.organisation_id != organisation_id:
        raise NotFoundError("Billing record not found")
    return billing_record


def _get_target_plan(db: Session, *, organisation_id: int, plan_code: str | None):
    if not plan_code:
        raise ValidationError("target_plan_code is required for this billing mutation")
    normalized_plan_code = entitlement_service._normalize_plan_code(plan_code)
    billing_plan = billing_crud.get_active_billing_plan(
        db,
        organisation_id=organisation_id,
        plan_code=normalized_plan_code,
    )
    if billing_plan is None:
        raise ValidationError(
            "Target billing plan is not active for this organisation",
            details={"target_plan_code": normalized_plan_code},
        )
    return normalized_plan_code, billing_plan


def update_subscription_service(
    db: Session,
    *,
    principal,
    organisation_id: int,
    payload: SubscriptionMutationInput,
    ip_address: str | None = None,
    user_agent: str | None = None,
):
    _require_subscription_admin(principal)
    organisation = organisation_crud.get_organisation_by_id(db, organisation_id)
    if not organisation:
        raise NotFoundError("Organisation not found")

    action = payload.action.strip().lower()
    if action not in SUBSCRIPTION_ACTIONS:
        raise ValidationError(
            "Unsupported subscription action",
            details={"allowed_actions": sorted(SUBSCRIPTION_ACTIONS)},
        )

    previous_plan_code = organisation.plan_code
    previous_subscription_status = organisation.subscription_status
    previous_trial_ends_at = organisation.trial_ends_at
    next_plan_code = previous_plan_code
    next_subscription_status = previous_subscription_status
    next_trial_ends_at = organisation.trial_ends_at
    billing_record = None

    if action in {"upgrade", "downgrade"}:
        target_plan_code, _ = _get_target_plan(
            db,
            organisation_id=organisation_id,
            plan_code=payload.target_plan_code,
        )
        if target_plan_code == previous_plan_code:
            raise ValidationError("Target plan must be different from the current plan")
        billing_record = _get_required_billing_record(
            db,
            organisation_id=organisation_id,
            billing_record_id=payload.billing_record_id,
        )
        if str(billing_record.status).strip().lower() != "paid":
            raise ValidationError(
                "A paid billing record is required before changing plans",
                details={"billing_record_status": billing_record.status},
            )
        next_plan_code = target_plan_code
        next_subscription_status = "active"

    elif action == "renew":
        billing_record = _get_required_billing_record(
            db,
            organisation_id=organisation_id,
            billing_record_id=payload.billing_record_id,
        )
        if str(billing_record.status).strip().lower() != "paid":
            raise ValidationError(
                "A paid billing record is required before renewing a subscription",
                details={"billing_record_status": billing_record.status},
            )
        _get_target_plan(
            db,
            organisation_id=organisation_id,
            plan_code=organisation.plan_code,
        )
        next_subscription_status = "active"
        next_trial_ends_at = None

    elif action == "cancel":
        if not payload.reason:
            raise ValidationError("reason is required when cancelling a subscription")
        next_subscription_status = "cancelled"

    elif action == "payment_failed":
        billing_record = _get_required_billing_record(
            db,
            organisation_id=organisation_id,
            billing_record_id=payload.billing_record_id,
        )
        billing_crud.update_billing_record(
            db,
            billing_record,
            commit=False,
            status="failed",
        )
        next_subscription_status = "past_due"

    if payload.trial_ends_at is not None:
        next_trial_ends_at = payload.trial_ends_at

    try:
        organisation_crud.update_organisation(
            db,
            organisation,
            commit=False,
            plan_code=next_plan_code,
            subscription_status=next_subscription_status,
            trial_ends_at=next_trial_ends_at,
        )
        AuditService.log_subscription_change(
            db,
            action=action,
            user_id=getattr(principal.user, "id", None),
            organisation_id=organisation_id,
            old_value={
                "plan_code": previous_plan_code,
                "subscription_status": previous_subscription_status,
                "trial_ends_at": previous_trial_ends_at.isoformat()
                if previous_trial_ends_at
                else None,
            },
            new_value={
                "plan_code": next_plan_code,
                "subscription_status": next_subscription_status,
                "trial_ends_at": next_trial_ends_at.isoformat()
                if next_trial_ends_at
                else None,
            },
            details={
                "billing_record_id": getattr(billing_record, "id", None),
                "reason": payload.reason,
                "actor_type": principal.principal_type,
                "service_account_id": getattr(principal.service_account, "id", None),
            },
            ip_address=ip_address,
            user_agent=user_agent,
            commit=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(organisation)
    entitlement_service.invalidate_entitlement_cache(organisation_id)
    return {
        "organisation_id": organisation_id,
        "action": action,
        "previous_plan_code": previous_plan_code,
        "current_plan_code": organisation.plan_code,
        "previous_subscription_status": previous_subscription_status,
        "current_subscription_status": organisation.subscription_status,
        "billing_record_id": getattr(billing_record, "id", None),
        "changed_at": datetime.now(UTC),
    }
