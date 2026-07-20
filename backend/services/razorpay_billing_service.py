from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from cruds import billing_crud, organisation_crud, user_crud
from services import entitlement_service
from services.audit_service import AuditService
from utils.exception_handling_utils import (
    ExternalServiceError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from utils.security_utils import get_request_client_ip, hash_value, verify_hmac_signature

RAZORPAY_PROVIDER = "razorpay"
RAZORPAY_SUPPORTED_EVENTS = {
    "payment.authorized",
    "payment.captured",
    "payment.failed",
    "subscription.activated",
    "subscription.authenticated",
    "subscription.charged",
    "subscription.cancelled",
    "subscription.completed",
    "subscription.halted",
    "subscription.paused",
    "subscription.resumed",
}
SUBSCRIPTION_STATUS_BY_EVENT = {
    "subscription.activated": "active",
    "subscription.authenticated": "active",
    "subscription.charged": "active",
    "subscription.resumed": "active",
    "subscription.cancelled": "cancelled",
    "subscription.completed": "cancelled",
    "subscription.halted": "past_due",
    "subscription.paused": "past_due",
}


def get_razorpay_webhook_secret() -> str:
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise ExternalServiceError(
            "RAZORPAY_WEBHOOK_SECRET is not configured",
            details={"provider": RAZORPAY_PROVIDER},
        )
    return secret


def verify_razorpay_signature(*, raw_body: bytes, signature: str | None) -> None:
    if not signature:
        raise UnauthorizedError(
            "Missing Razorpay signature",
            details={"header": "X-Razorpay-Signature"},
        )
    if not verify_hmac_signature(raw_body, signature, get_razorpay_webhook_secret()):
        raise UnauthorizedError("Invalid Razorpay webhook signature")


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _resolve_period_bounds(
    *, paid_at: datetime | None = None, interval: str | None = None
) -> tuple[datetime, datetime]:
    current = _as_utc(paid_at) or datetime.now(UTC)
    normalized_interval = (interval or "monthly").strip().lower()
    start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    if normalized_interval == "yearly":
        return start, start.replace(year=start.year + 1)
    if normalized_interval == "weekly":
        return start, start + timedelta(days=7)
    return start, start + timedelta(days=30)


def _coerce_amount(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return 0.0
    if amount > 1000:
        return round(amount / 100.0, 2)
    return round(amount, 2)


def _get_payload_entity(payload: dict[str, Any], key: str) -> dict[str, Any]:
    entity = payload.get(key)
    if isinstance(entity, dict):
        return entity.get("entity", entity) if isinstance(entity.get("entity"), dict) else entity
    return {}


def _find_first_org_user_id(db: Session, organisation_id: int) -> int:
    users = user_crud.list_users(
        db,
        organisation_id=organisation_id,
        offset=0,
        limit=1,
        sort_by="id",
        sort_dir="asc",
    )
    if not users:
        raise NotFoundError("No organisation user found for billing sync")
    return users[0].id


def _resolve_organisation_from_event(
    db: Session,
    *,
    subscription: dict[str, Any],
    payment: dict[str, Any],
) -> Any:
    subscription_id = subscription.get("id") or payment.get("subscription_id")
    customer_id = subscription.get("customer_id") or payment.get("customer_id")

    organisation = None
    if subscription_id:
        organisation = organisation_crud.get_organisation_by_billing_subscription_external_id(
            db, subscription_id
        )
    if organisation is None and customer_id:
        organisation = organisation_crud.get_organisation_by_billing_customer_external_id(
            db, customer_id
        )

    notes = subscription.get("notes") or payment.get("notes") or {}
    organisation_id = notes.get("organisation_id") or notes.get("org_id")
    if organisation is None and organisation_id is not None:
        try:
            organisation = organisation_crud.get_organisation_by_id(db, int(organisation_id))
        except (TypeError, ValueError):
            organisation = None

    if organisation is None:
        raise NotFoundError(
            "Organisation not found for Razorpay webhook",
            details={
                "provider": RAZORPAY_PROVIDER,
                "provider_subscription_id": subscription_id,
                "provider_customer_id": customer_id,
            },
        )
    return organisation


def _sync_organisation_provider_fields(
    db: Session,
    *,
    organisation,
    subscription: dict[str, Any],
    payment: dict[str, Any],
    commit: bool = False,
) -> None:
    organisation_crud.update_organisation(
        db,
        organisation,
        commit=commit,
        billing_provider=RAZORPAY_PROVIDER,
        billing_customer_external_id=subscription.get("customer_id")
        or payment.get("customer_id")
        or organisation.billing_customer_external_id,
        billing_subscription_external_id=subscription.get("id")
        or payment.get("subscription_id")
        or organisation.billing_subscription_external_id,
    )


def _resolve_plan_code(
    db: Session,
    *,
    organisation_id: int,
    current_plan_code: str,
    subscription: dict[str, Any],
) -> str:
    notes = subscription.get("notes") or {}
    if notes.get("plan_code"):
        return entitlement_service._normalize_plan_code(notes["plan_code"])

    plan_id = subscription.get("plan_id")
    if plan_id:
        billing_plan = billing_crud.get_billing_plan_by_provider_plan_id(
            db,
            billing_provider=RAZORPAY_PROVIDER,
            provider_plan_id=plan_id,
        )
        if billing_plan is not None and billing_plan.organisation_id == organisation_id:
            return billing_plan.plan_code

    return entitlement_service._normalize_plan_code(current_plan_code)


def _upsert_billing_record_from_payment(
    db: Session,
    *,
    organisation,
    payment: dict[str, Any],
    subscription: dict[str, Any],
    event_id: str,
    event_type: str,
) -> Any:
    provider_invoice_id = payment.get("invoice_id")
    provider_payment_id = payment.get("id")
    provider_subscription_id = payment.get("subscription_id") or subscription.get("id")
    record = billing_crud.get_billing_record_by_provider_references(
        db,
        billing_provider=RAZORPAY_PROVIDER,
        organisation_id=organisation.id,
        provider_invoice_id=provider_invoice_id,
        provider_payment_id=provider_payment_id,
        provider_subscription_id=provider_subscription_id,
    )

    interval = subscription.get("remaining_count")
    paid_at = datetime.now(UTC)
    period_start, period_end = _resolve_period_bounds(paid_at=paid_at)
    amount = _coerce_amount(payment.get("amount") or payment.get("amount_due"))
    status = "paid" if event_type == "payment.captured" else "failed"
    billable_user_id = _find_first_org_user_id(db, organisation.id)

    updates = {
        "billing_provider": RAZORPAY_PROVIDER,
        "provider_invoice_id": provider_invoice_id,
        "provider_payment_id": provider_payment_id,
        "provider_subscription_id": provider_subscription_id,
        "provider_event_id": event_id,
        "status": status,
        "amount": amount,
        "currency": str(payment.get("currency") or "INR").upper(),
        "description": payment.get("description")
        or f"Razorpay {event_type} for subscription {provider_subscription_id}",
        "billed_at": paid_at if status == "paid" else None,
    }

    if record is None:
        record = billing_crud.create_billing_record(
            db,
            commit=False,
            user_id=billable_user_id,
            organisation_id=organisation.id,
            usage_event_id=None,
            invoice_id=None,
            billing_period_start=period_start,
            billing_period_end=period_end,
            **updates,
        )
    else:
        billing_crud.update_billing_record(db, record, commit=False, **updates)
    return record


def _audit_subscription_sync(
    db: Session,
    *,
    organisation,
    old_state: dict[str, Any],
    new_state: dict[str, Any],
    action: str,
    event_id: str,
    request,
) -> None:
    AuditService.log_subscription_change(
        db,
        action=action,
        user_id=None,
        organisation_id=organisation.id,
        old_value=old_state,
        new_value=new_state,
        details={
            "provider": RAZORPAY_PROVIDER,
            "provider_event_id": event_id,
        },
        ip_address=get_request_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        commit=False,
    )


def process_razorpay_webhook(
    db: Session,
    *,
    raw_body: bytes,
    payload: dict[str, Any],
    event_id: str,
    request,
) -> dict[str, Any]:
    event_type = str(payload.get("event") or "").strip()
    if not event_type:
        raise ValidationError("Razorpay webhook event is missing")
    if event_type not in RAZORPAY_SUPPORTED_EVENTS:
        return {
            "provider": RAZORPAY_PROVIDER,
            "event_id": event_id,
            "event_type": event_type,
            "processed": False,
            "ignored": True,
        }

    existing_event = billing_crud.get_billing_webhook_event(
        db,
        provider=RAZORPAY_PROVIDER,
        event_id=event_id,
    )
    payload_hash = hash_value(raw_body.decode("utf-8"))
    if existing_event is not None:
        return {
            "provider": RAZORPAY_PROVIDER,
            "event_id": event_id,
            "event_type": existing_event.event_type,
            "processed": existing_event.processing_status == "processed",
            "duplicate": True,
        }

    subscription = _get_payload_entity(payload.get("payload", {}), "subscription")
    payment = _get_payload_entity(payload.get("payload", {}), "payment")
    organisation = _resolve_organisation_from_event(
        db,
        subscription=subscription,
        payment=payment,
    )

    webhook_event = billing_crud.create_billing_webhook_event(
        db,
        commit=False,
        provider=RAZORPAY_PROVIDER,
        event_id=event_id,
        event_type=event_type,
        organisation_id=organisation.id,
        processing_status="received",
        payload_hash=payload_hash,
    )

    previous_state = {
        "plan_code": organisation.plan_code,
        "subscription_status": organisation.subscription_status,
        "trial_ends_at": organisation.trial_ends_at.isoformat()
        if organisation.trial_ends_at
        else None,
    }

    try:
        _sync_organisation_provider_fields(
            db,
            organisation=organisation,
            subscription=subscription,
            payment=payment,
            commit=False,
        )

        if event_type in SUBSCRIPTION_STATUS_BY_EVENT:
            next_plan_code = _resolve_plan_code(
                db,
                organisation_id=organisation.id,
                current_plan_code=organisation.plan_code,
                subscription=subscription,
            )
            next_status = SUBSCRIPTION_STATUS_BY_EVENT[event_type]
            organisation_crud.update_organisation(
                db,
                organisation,
                commit=False,
                plan_code=next_plan_code,
                subscription_status=next_status,
            )
            _audit_subscription_sync(
                db,
                organisation=organisation,
                old_state=previous_state,
                new_state={
                    "plan_code": next_plan_code,
                    "subscription_status": next_status,
                    "trial_ends_at": previous_state["trial_ends_at"],
                },
                action=event_type,
                event_id=event_id,
                request=request,
            )

        if event_type in {"payment.captured", "payment.failed"}:
            record = _upsert_billing_record_from_payment(
                db,
                organisation=organisation,
                payment=payment,
                subscription=subscription,
                event_id=event_id,
                event_type=event_type,
            )
            if event_type == "payment.failed":
                organisation_crud.update_organisation(
                    db,
                    organisation,
                    commit=False,
                    subscription_status="past_due",
                )
            elif event_type == "payment.captured":
                next_plan_code = _resolve_plan_code(
                    db,
                    organisation_id=organisation.id,
                    current_plan_code=organisation.plan_code,
                    subscription=subscription,
                )
                organisation_crud.update_organisation(
                    db,
                    organisation,
                    commit=False,
                    plan_code=next_plan_code,
                    subscription_status="active",
                )
            _audit_subscription_sync(
                db,
                organisation=organisation,
                old_state=previous_state,
                new_state={
                    "plan_code": organisation.plan_code,
                    "subscription_status": organisation.subscription_status,
                    "trial_ends_at": previous_state["trial_ends_at"],
                },
                action=event_type,
                event_id=event_id,
                request=request,
            )
            billing_crud.update_billing_webhook_event(
                db,
                webhook_event,
                commit=False,
                processing_status="processed",
                processed_at=datetime.now(UTC),
            )
            db.commit()
            entitlement_service.invalidate_entitlement_cache(organisation.id)
            return {
                "provider": RAZORPAY_PROVIDER,
                "event_id": event_id,
                "event_type": event_type,
                "processed": True,
                "organisation_id": organisation.id,
                "billing_record_id": record.id,
            }

        billing_crud.update_billing_webhook_event(
            db,
            webhook_event,
            commit=False,
            processing_status="processed",
            processed_at=datetime.now(UTC),
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        try:
            billing_crud.update_billing_webhook_event(
                db,
                webhook_event,
                commit=True,
                processing_status="failed",
                error_message=str(exc),
            )
        except Exception:
            db.rollback()
        raise

    entitlement_service.invalidate_entitlement_cache(organisation.id)
    return {
        "provider": RAZORPAY_PROVIDER,
        "event_id": event_id,
        "event_type": event_type,
        "processed": True,
        "organisation_id": organisation.id,
    }
