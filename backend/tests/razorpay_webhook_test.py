import json
import uuid

from fastapi import status

from cruds import audit_crud, billing_crud, organisation_crud
from utils.security_utils import generate_hmac_signature


def _register_and_login(client, *, email: str, password: str, organisation_name: str):
    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "organisation_name": organisation_name,
        },
    )
    assert register.status_code == status.HTTP_201_CREATED

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == status.HTTP_200_OK

    token = login.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == status.HTTP_200_OK
    return token, me.json()


def _promote_admin(db, user_id: int) -> None:
    from cruds import user_crud

    user = user_crud.get_user_by_id(db, user_id)
    user.role = "admin"
    db.commit()


def _build_razorpay_headers(raw_body: bytes, *, event_id: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": generate_hmac_signature(
            raw_body, "razorpay-test-webhook-secret"
        ),
        "x-razorpay-event-id": event_id,
    }


def test_razorpay_webhook_rejects_invalid_signature(client):
    payload = {"event": "payment.captured", "payload": {}}
    raw_body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    response = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": "invalid",
            "x-razorpay-event-id": "evt_invalid_signature",
        },
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["error"]["code"] == "unauthorized"


def test_razorpay_payment_captured_syncs_subscription_and_billing(client, db):
    suffix = uuid.uuid4().hex[:8]
    token, me = _register_and_login(
        client,
        email=f"rzp_capture_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"Razorpay Org {suffix}",
    )
    _promote_admin(db, me["id"])

    create_plan = client.post(
        "/api/v1/billing/plans",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": f"rzp-growth-plan-{suffix}",
        },
        json={
            "organisation_id": me["organisation_id"],
            "name": "Growth",
            "plan_code": "growth",
            "billing_provider": "razorpay",
            "provider_plan_id": "plan_rzp_growth",
            "price_per_unit": 499.0,
            "currency": "INR",
            "billing_interval": "monthly",
            "is_active": True,
        },
    )
    assert create_plan.status_code == status.HTTP_201_CREATED

    payload = {
        "event": "payment.captured",
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_rzp_123",
                    "customer_id": "cust_rzp_123",
                    "plan_id": "plan_rzp_growth",
                    "notes": {"organisation_id": me["organisation_id"]},
                }
            },
            "payment": {
                "entity": {
                    "id": "pay_rzp_123",
                    "invoice_id": "inv_rzp_123",
                    "subscription_id": "sub_rzp_123",
                    "customer_id": "cust_rzp_123",
                    "amount": 49900,
                    "currency": "INR",
                    "description": "Monthly subscription charge",
                    "notes": {"organisation_id": me["organisation_id"]},
                }
            },
        },
    }
    raw_body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    response = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers=_build_razorpay_headers(raw_body, event_id="evt_capture_123"),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["processed"] is True

    organisation = organisation_crud.get_organisation_by_id(db, me["organisation_id"])
    assert organisation.plan_code == "growth"
    assert organisation.subscription_status == "active"
    assert organisation.billing_provider == "razorpay"
    assert organisation.billing_customer_external_id == "cust_rzp_123"
    assert organisation.billing_subscription_external_id == "sub_rzp_123"

    billing_records = billing_crud.list_billing_records(
        db, organisation_id=me["organisation_id"]
    )
    assert len(billing_records) == 1
    assert billing_records[0].billing_provider == "razorpay"
    assert billing_records[0].status == "paid"
    assert billing_records[0].provider_payment_id == "pay_rzp_123"
    assert billing_records[0].provider_invoice_id == "inv_rzp_123"

    duplicate = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers=_build_razorpay_headers(raw_body, event_id="evt_capture_123"),
    )
    assert duplicate.status_code == status.HTTP_200_OK
    assert duplicate.json()["duplicate"] is True
    assert (
        len(billing_crud.list_billing_records(db, organisation_id=me["organisation_id"]))
        == 1
    )


def test_razorpay_payment_failed_marks_org_past_due(client, db):
    suffix = uuid.uuid4().hex[:8]
    token, me = _register_and_login(
        client,
        email=f"rzp_failed_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"Failed Org {suffix}",
    )
    _promote_admin(db, me["id"])

    client.post(
        "/api/v1/billing/plans",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": f"rzp-starter-plan-{suffix}",
        },
        json={
            "organisation_id": me["organisation_id"],
            "name": "Starter",
            "plan_code": "starter",
            "billing_provider": "razorpay",
            "provider_plan_id": "plan_rzp_starter",
            "price_per_unit": 199.0,
            "currency": "INR",
            "billing_interval": "monthly",
            "is_active": True,
        },
    )

    payload = {
        "event": "payment.failed",
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_rzp_failed",
                    "customer_id": "cust_rzp_failed",
                    "plan_id": "plan_rzp_starter",
                    "notes": {"organisation_id": me["organisation_id"]},
                }
            },
            "payment": {
                "entity": {
                    "id": "pay_rzp_failed",
                    "invoice_id": "inv_rzp_failed",
                    "subscription_id": "sub_rzp_failed",
                    "customer_id": "cust_rzp_failed",
                    "amount": 19900,
                    "currency": "INR",
                    "description": "Subscription renewal failed",
                    "notes": {"organisation_id": me["organisation_id"]},
                }
            },
        },
    }
    raw_body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    response = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers=_build_razorpay_headers(raw_body, event_id="evt_failed_123"),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["processed"] is True

    organisation = organisation_crud.get_organisation_by_id(db, me["organisation_id"])
    assert organisation.subscription_status == "past_due"
    assert organisation.billing_subscription_external_id == "sub_rzp_failed"

    billing_records = billing_crud.list_billing_records(
        db, organisation_id=me["organisation_id"]
    )
    assert len(billing_records) == 1
    assert billing_records[0].status == "failed"
    assert billing_records[0].provider_event_id == "evt_failed_123"


def test_razorpay_link_endpoint_persists_provider_ids_and_audits(client, db):
    suffix = uuid.uuid4().hex[:8]
    token, me = _register_and_login(
        client,
        email=f"rzp_link_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"Link Org {suffix}",
    )
    _promote_admin(db, me["id"])

    response = client.post(
        "/api/v1/billing/razorpay/link",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": f"rzp-link-{suffix}",
        },
        json={
            "customer_external_id": "cust_link_123",
            "subscription_external_id": "sub_link_123",
        },
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["billing_provider"] == "razorpay"
    assert body["billing_customer_external_id"] == "cust_link_123"
    assert body["billing_subscription_external_id"] == "sub_link_123"

    organisation = organisation_crud.get_organisation_by_id(db, me["organisation_id"])
    assert organisation.billing_provider == "razorpay"
    assert organisation.billing_customer_external_id == "cust_link_123"
    assert organisation.billing_subscription_external_id == "sub_link_123"

    audit_logs = audit_crud.list_audit_logs(
        db,
        organisation_id=me["organisation_id"],
        event_type="billing_subscription",
        resource_type="organisation_subscription",
    )
    assert any(log.action == "billing_provider_linked" for log in audit_logs)


def test_razorpay_webhook_resolves_org_from_linked_provider_ids(client, db):
    suffix = uuid.uuid4().hex[:8]
    token, me = _register_and_login(
        client,
        email=f"rzp_linked_capture_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"Linked Capture Org {suffix}",
    )
    _promote_admin(db, me["id"])

    create_plan = client.post(
        "/api/v1/billing/plans",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": f"rzp-linked-plan-{suffix}",
        },
        json={
            "organisation_id": me["organisation_id"],
            "name": "Growth",
            "plan_code": "growth",
            "billing_provider": "razorpay",
            "provider_plan_id": "plan_rzp_linked_growth",
            "price_per_unit": 499.0,
            "currency": "INR",
            "billing_interval": "monthly",
            "is_active": True,
        },
    )
    assert create_plan.status_code == status.HTTP_201_CREATED

    link = client.post(
        "/api/v1/billing/razorpay/link",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": f"rzp-link-existing-{suffix}",
        },
        json={
            "customer_external_id": "cust_linked_capture",
            "subscription_external_id": "sub_linked_capture",
        },
    )
    assert link.status_code == status.HTTP_200_OK

    payload = {
        "event": "payment.captured",
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_linked_capture",
                    "customer_id": "cust_linked_capture",
                    "plan_id": "plan_rzp_linked_growth",
                }
            },
            "payment": {
                "entity": {
                    "id": "pay_linked_capture",
                    "invoice_id": "inv_linked_capture",
                    "subscription_id": "sub_linked_capture",
                    "customer_id": "cust_linked_capture",
                    "amount": 49900,
                    "currency": "INR",
                    "description": "Linked subscription charge",
                }
            },
        },
    }
    raw_body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    response = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers=_build_razorpay_headers(raw_body, event_id="evt_linked_capture"),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["processed"] is True

    organisation = organisation_crud.get_organisation_by_id(db, me["organisation_id"])
    assert organisation.plan_code == "growth"
    assert organisation.subscription_status == "active"

    billing_records = billing_crud.list_billing_records(
        db, organisation_id=me["organisation_id"]
    )
    assert len(billing_records) == 1
    assert billing_records[0].provider_payment_id == "pay_linked_capture"
