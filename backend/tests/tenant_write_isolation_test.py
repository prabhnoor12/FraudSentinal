from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import status

from models.settings_models import OrganisationSettings
from models.user_models import User
from schemas.decision_schemas import FraudDecision
from services import fraud_rule_service


def _register_and_login(
    client, *, email: str, password: str, organisation_name: str | None
):
    payload = {"email": email, "password": password}
    if organisation_name is not None:
        payload["organisation_name"] = organisation_name

    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)

    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == status.HTTP_200_OK
    token = login.json()["access_token"]
    assert token

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == status.HTTP_200_OK
    return token, me.json()


def _two_org_contexts(client):
    suffix_a = uuid.uuid4().hex[:8]
    suffix_b = uuid.uuid4().hex[:8]
    token_a, me_a = _register_and_login(
        client,
        email=f"tenant_a_{suffix_a}@example.com",
        password="StrongPass123!",
        organisation_name=f"TenantA_{suffix_a}",
    )
    token_b, me_b = _register_and_login(
        client,
        email=f"tenant_b_{suffix_b}@example.com",
        password="StrongPass123!",
        organisation_name=f"TenantB_{suffix_b}",
    )
    return (token_a, me_a), (token_b, me_b)


def _make_admin(db, *, user_id: int) -> None:
    user = db.query(User).filter(User.id == user_id).first()
    assert user is not None
    user.role = "admin"
    db.add(user)
    db.commit()


def _idempotency_headers(headers: dict[str, str], prefix: str) -> dict[str, str]:
    return {**headers, "Idempotency-Key": f"{prefix}-{uuid.uuid4().hex[:8]}"}


def test_cross_tenant_creates_are_scoped_to_the_request_org(client, db):
    (token_a, me_a), (token_b, me_b) = _two_org_contexts(client)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    now = datetime.now(timezone.utc)

    limit_resp = client.post(
        "/api/v1/limit-tracking/limits",
        headers=_idempotency_headers(headers_a, "limit-create"),
        json={
            "user_id": me_a["id"],
            "limit_type": "fraud_checks",
            "limit_value": 100,
            "period": "monthly",
            "is_active": "true",
        },
    )
    assert limit_resp.status_code == status.HTTP_201_CREATED
    limit_id = limit_resp.json()["id"]

    usage_event_resp = client.post(
        "/api/v1/usage/events",
        headers=_idempotency_headers(headers_a, "usage-event"),
        json={
            "user_id": me_a["id"],
            "event_type": "check_fraud",
            "units": 1.0,
            "unit_type": "request",
            "description": "seed",
            "status": "recorded",
        },
    )
    assert usage_event_resp.status_code == status.HTTP_201_CREATED
    usage_event_id = usage_event_resp.json()["id"]

    session_resp = client.post(
        "/api/v1/sessions",
        json={
            "user_id": me_a["id"],
            "session_token": f"sess_{uuid.uuid4().hex}",
            "ip_address": "127.0.0.1",
            "user_agent": "pytest",
            "status": "active",
        },
        headers=headers_a,
    )
    assert session_resp.status_code == status.HTTP_201_CREATED
    session_id = session_resp.json()["id"]

    plan_resp = client.post(
        "/api/v1/billing/plans",
        headers={**headers_b, "Idempotency-Key": f"plan-{uuid.uuid4().hex[:8]}"},
        json={
            "organisation_id": me_a["organisation_id"],
            "name": "Starter",
            "price_per_unit": 1.5,
            "currency": "USD",
            "billing_interval": "monthly",
            "is_active": True,
        },
    )
    assert plan_resp.status_code == status.HTTP_201_CREATED
    assert plan_resp.json()["organisation_id"] == me_b["organisation_id"]

    assert (
        client.post(
            "/api/v1/transactions",
            headers=_idempotency_headers(headers_b, "tx-cross"),
            json={
                "user_id": me_a["id"],
                "amount": 50,
                "currency": "USD",
                "payment_method": "cc",
                "channel": "web",
            },
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    assert (
        client.post(
            "/api/v1/usage/events",
            headers=_idempotency_headers(headers_b, "usage-cross"),
            json={
                "user_id": me_a["id"],
                "event_type": "check_fraud",
                "units": 1.0,
                "unit_type": "request",
                "status": "recorded",
            },
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    assert (
        client.post(
            "/api/v1/usage/summaries",
            headers=_idempotency_headers(headers_b, "usage-summary-cross"),
            json={
                "user_id": me_a["id"],
                "period_start": (now - timedelta(days=30)).isoformat(),
                "period_end": now.isoformat(),
                "total_units": 10.0,
                "currency": "USD",
            },
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    assert (
        client.post(
            "/api/v1/user-tracking/events",
            headers=_idempotency_headers(headers_b, "tracking-event-cross"),
            json={
                "user_id": me_a["id"],
                "event_type": "login",
                "units": 1.0,
                "unit_type": "event",
                "description": "seed",
                "status": "recorded",
            },
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    assert (
        client.post(
            "/api/v1/user-tracking/summaries",
            headers=_idempotency_headers(headers_b, "tracking-summary-cross"),
            json={
                "user_id": me_a["id"],
                "period_start": (now - timedelta(days=30)).isoformat(),
                "period_end": now.isoformat(),
                "total_units": 7.0,
                "currency": "USD",
            },
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    assert (
        client.post(
            "/api/v1/sessions",
            json={
                "user_id": me_a["id"],
                "session_token": f"sess_{uuid.uuid4().hex}",
                "status": "active",
            },
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    assert (
        client.post(
            f"/api/v1/sessions/{session_id}/end",
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    assert (
        client.post(
            "/api/v1/limit-tracking/limits",
            headers=_idempotency_headers(headers_b, "limit-cross"),
            json={
                "user_id": me_a["id"],
                "limit_type": "transactions",
                "limit_value": 100,
                "period": "monthly",
                "is_active": "true",
            },
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    assert (
        client.post(
            "/api/v1/limit-tracking/records",
            headers=_idempotency_headers(headers_b, "limit-record-cross"),
            json={
                "usage_limit_id": limit_id,
                "current_usage": 5.0,
                "period_start": (now - timedelta(days=30)).isoformat(),
                "period_end": now.isoformat(),
            },
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    billing_record_resp = client.post(
        "/api/v1/billing/records",
        headers=_idempotency_headers(headers_a, "record"),
        json={
            "user_id": me_a["id"],
            "organisation_id": me_a["organisation_id"],
            "usage_event_id": usage_event_id,
            "amount": 25.0,
            "currency": "USD",
            "status": "pending",
            "invoice_id": f"inv_{uuid.uuid4().hex[:8]}",
            "description": "Monthly fee",
            "billing_period_start": "2026-07-01T00:00:00Z",
            "billing_period_end": "2026-07-31T23:59:59Z",
        },
    )
    assert billing_record_resp.status_code == status.HTTP_201_CREATED
    billing_record_id = billing_record_resp.json()["id"]

    assert (
        client.post(
            "/api/v1/billing/records",
            headers=_idempotency_headers(headers_b, "record-cross"),
            json={
                "user_id": me_a["id"],
                "organisation_id": me_a["organisation_id"],
                "usage_event_id": usage_event_id,
                "amount": 25.0,
                "currency": "USD",
                "status": "pending",
                "invoice_id": f"inv_{uuid.uuid4().hex[:8]}",
                "description": "Monthly fee",
                "billing_period_start": "2026-07-01T00:00:00Z",
                "billing_period_end": "2026-07-31T23:59:59Z",
            },
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )


def test_cross_tenant_updates_and_deletes_are_rejected(client, db):
    (token_a, me_a), (token_b, me_b) = _two_org_contexts(client)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    db.query(OrganisationSettings).filter(
        OrganisationSettings.organisation_id.in_(
            [me_a["organisation_id"], me_b["organisation_id"]]
        )
    ).delete(synchronize_session=False)
    db.commit()

    settings_create = client.post(
        "/api/v1/settings",
        json={
            "organisation_id": me_a["organisation_id"],
            "currency": "USD",
            "timezone": "UTC",
            "review_threshold": 41,
            "decline_threshold": 72,
            "enable_billing": True,
            "enable_usage_tracking": True,
            "notification_email": "alerts@example.com",
            "notes": "tenant check",
        },
        headers=headers_b,
    )
    assert settings_create.status_code == status.HTTP_201_CREATED
    assert settings_create.json()["organisation_id"] == me_b["organisation_id"]

    assert (
        client.get(
            f"/api/v1/settings/{me_a['organisation_id']}",
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        client.put(
            f"/api/v1/settings/{me_a['organisation_id']}",
            json={"review_threshold": 35, "decline_threshold": 80},
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    fraud_rule_service.seed_default_fraud_rules(db)
    rule_resp = client.post(
        "/api/v1/fraud-rules",
        json={
            "name": "Tenant A Rule",
            "rule_code": f"tenant_a_{uuid.uuid4().hex[:8]}",
            "description": "Tenant A rule",
            "weight": 10,
            "field_name": "transactions_last_24h",
            "operator": "gte",
            "comparison_value": 3,
            "priority": 1,
            "reason_code": "velocity_spike",
        },
        headers=headers_a,
    )
    assert rule_resp.status_code == status.HTTP_201_CREATED
    rule_id = rule_resp.json()["id"]

    assert (
        client.put(
            f"/api/v1/fraud-rules/{rule_id}",
            json={"rule_code": "cross tenant", "organisation_id": me_b["organisation_id"]},
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        client.post(
            f"/api/v1/fraud-rules/{rule_id}/disable",
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    user_resp = client.post(
        "/api/v1/users",
        json={
            "email": f"user_{uuid.uuid4().hex[:8]}@example.com",
            "password": "StrongPass123!",
            "full_name": "Tenant A User",
            "is_active": True,
        },
        headers=headers_a,
    )
    assert user_resp.status_code == status.HTTP_201_CREATED
    user_id = user_resp.json()["id"]

    assert (
        client.put(
            f"/api/v1/users/{user_id}",
            json={"full_name": "Cross tenant"},
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        client.delete(
            f"/api/v1/users/{user_id}",
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    with patch("services.scoring_service.score_transaction") as mock_score:
        mock_score.return_value = {
            "risk_score": 50,
            "decision": FraudDecision.review,
            "reason_codes": ["high_amount"],
            "matched_rules": [],
        }
        check_resp = client.post(
            "/api/v1/check-fraud",
            headers=_idempotency_headers(headers_a, "fraud-check"),
            json={
                "user_id": me_a["id"],
                "organisation_id": me_a["organisation_id"],
                "amount": 1000,
                "currency": "USD",
                "payment_method": "cc",
                "channel": "web",
            },
        )
    assert check_resp.status_code == status.HTTP_200_OK

    review_cases_resp = client.get("/api/v1/review-cases", headers=headers_a)
    assert review_cases_resp.status_code == status.HTTP_200_OK
    review_cases_payload = review_cases_resp.json()
    review_cases_items = review_cases_payload.get("items", [])
    assert review_cases_items
    case_id = review_cases_items[0]["id"]
    assert (
        client.put(
            f"/api/v1/review-cases/{case_id}",
            json={"notes": "cross tenant"},
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        client.post(
            f"/api/v1/review-cases/{case_id}/resolve",
            json={"resolution_code": "approved_by_analyst"},
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        client.post(
            f"/api/v1/review-cases/{case_id}/reopen",
            json={"reason": "cross tenant"},
            headers=headers_b,
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )

    _make_admin(db, user_id=me_b["id"])
    plan_resp_b = client.post(
        "/api/v1/billing/plans",
        headers=_idempotency_headers(headers_b, "plan-b"),
        json={
            "organisation_id": me_b["organisation_id"],
            "name": "Growth",
            "plan_code": "growth",
            "price_per_unit": 1.5,
            "currency": "USD",
            "billing_interval": "monthly",
            "is_active": True,
        },
    )
    assert plan_resp_b.status_code == status.HTTP_201_CREATED

    plan_resp = client.post(
        "/api/v1/billing/plans",
        headers=_idempotency_headers(headers_a, "plan-a"),
        json={
            "organisation_id": me_a["organisation_id"],
            "name": "Starter",
            "price_per_unit": 1.5,
            "currency": "USD",
            "billing_interval": "monthly",
            "is_active": True,
        },
    )
    assert plan_resp.status_code == status.HTTP_201_CREATED

    paid_record = client.post(
        "/api/v1/billing/records",
        headers=_idempotency_headers(headers_a, "record-a"),
        json={
            "user_id": me_a["id"],
            "organisation_id": me_a["organisation_id"],
            "amount": 99.0,
            "currency": "USD",
            "status": "paid",
            "invoice_id": f"inv_{uuid.uuid4().hex[:8]}",
            "description": "Upgrade charge",
            "billing_period_start": "2026-07-01T00:00:00Z",
            "billing_period_end": "2026-07-31T23:59:59Z",
        },
    )
    assert paid_record.status_code == status.HTTP_201_CREATED

    graphql = client.post(
        "/api/v1/billing/graphql",
        headers=_idempotency_headers(headers_b, "graphql"),
        json={
            "query": "mutation Update($input: SubscriptionMutationInput!) { updateOrganisationSubscription(input: $input) { organisationId } }",
            "variables": {
                "input": {
                    "action": "upgrade",
                    "target_plan_code": "growth",
                    "billing_record_id": paid_record.json()["id"],
                }
            },
        },
    )
    assert graphql.status_code == status.HTTP_404_NOT_FOUND
