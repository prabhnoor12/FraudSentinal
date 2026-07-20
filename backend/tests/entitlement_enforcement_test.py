from datetime import UTC, datetime
import uuid

from fastapi import status

from cruds import audit_crud, billing_crud, limit_tracking_crud, organisation_crud, usage_crud
from services import fraud_rule_service


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


def _current_month_bounds() -> tuple[datetime, datetime]:
    start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _promote_admin(db, user_id: int) -> None:
    from cruds import user_crud

    user = user_crud.get_user_by_id(db, user_id)
    user.role = "admin"
    db.commit()


def _graphql_subscription_mutation(client, headers: dict[str, str], input_payload: dict):
    return client.post(
        "/api/v1/billing/graphql",
        headers=headers,
        json={
            "query": """
                mutation UpdateOrganisationSubscription($input: SubscriptionMutationInput!) {
                    updateOrganisationSubscription(input: $input) {
                        organisationId
                        action
                        previousPlanCode
                        currentPlanCode
                        previousSubscriptionStatus
                        currentSubscriptionStatus
                        billingRecordId
                        changedAt
                    }
                }
            """,
            "variables": {"input": input_payload},
        },
    )


def test_inactive_subscription_blocks_billing_usage_and_limit_tracking(client, db):
    suffix = uuid.uuid4().hex[:8]
    token, me = _register_and_login(
        client,
        email=f"inactive_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"Inactive Org {suffix}",
    )
    headers = {"Authorization": f"Bearer {token}"}

    organisation = organisation_crud.get_organisation_by_id(db, me["organisation_id"])
    organisation_crud.update_organisation(db, organisation, subscription_status="past_due")

    for path in (
        "/api/v1/billing/plans",
        "/api/v1/usage/events",
        "/api/v1/limit-tracking/limits",
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["error"]["code"] == "subscription_inactive"


def test_starter_plan_blocks_premium_enrichment_lookup(client, db):
    from cruds.ip_geolocation_crud import create_ip_geolocation

    suffix = uuid.uuid4().hex[:8]
    token, _ = _register_and_login(
        client,
        email=f"enrichment_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"Starter Org {suffix}",
    )
    headers = {"Authorization": f"Bearer {token}"}

    create_ip_geolocation(
        db,
        ip_start="1.1.1.0",
        ip_end="1.1.1.255",
        country_code="US",
        region="CA",
        city="Los Angeles",
        latitude="34.0522",
        longitude="-118.2437",
        isp="Example ISP",
    )

    response = client.get(
        "/api/v1/enrichment/ip-geolocation/lookup?ip_address=1.1.1.1",
        headers=headers,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["error"]["code"] == "feature_not_available"


def test_fraud_check_quota_exceeded_returns_standard_error(client, db):
    fraud_rule_service.seed_default_fraud_rules(db)

    suffix = uuid.uuid4().hex[:8]
    token, me = _register_and_login(
        client,
        email=f"quota_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"Quota Org {suffix}",
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": f"quota-check-{suffix}",
    }
    period_start, period_end = _current_month_bounds()

    usage_limit = limit_tracking_crud.create_usage_limit(
        db,
        organisation_id=me["organisation_id"],
        user_id=None,
        limit_type="fraud_checks",
        limit_value=1,
        period="monthly",
        is_active="true",
    )
    limit_tracking_crud.create_limit_usage_record(
        db,
        usage_limit_id=usage_limit.id,
        current_usage=1,
        period_start=period_start,
        period_end=period_end,
    )

    response = client.post(
        "/api/v1/check-fraud",
        headers=headers,
        json={
            "user_id": me["id"],
            "organisation_id": me["organisation_id"],
            "amount": 42.5,
            "currency": "USD",
            "payment_method": "card",
            "channel": "api",
            "customer_id": "quota-customer",
            "metadata": {},
        },
    )

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    body = response.json()
    assert body["error"]["code"] == "quota_exceeded"
    assert body["error"]["details"]["quota_key"] == "fraud_checks"


def test_successful_fraud_check_records_usage_limit_and_billing(client, db):
    fraud_rule_service.seed_default_fraud_rules(db)

    suffix = uuid.uuid4().hex[:8]
    token, me = _register_and_login(
        client,
        email=f"metering_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"Metering Org {suffix}",
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": f"fraud-metering-{suffix}",
    }

    response = client.post(
        "/api/v1/check-fraud",
        headers=headers,
        json={
            "user_id": me["id"],
            "organisation_id": me["organisation_id"],
            "amount": 15.0,
            "currency": "USD",
            "payment_method": "card",
            "channel": "api",
            "customer_id": "metering-customer",
            "metadata": {},
        },
    )
    assert response.status_code == status.HTTP_200_OK

    usage_events = usage_crud.list_usage_events(
        db, organisation_id=me["organisation_id"], user_id=me["id"]
    )
    assert len(usage_events) == 1
    assert usage_events[0].event_type == "fraud_checks"
    assert usage_events[0].units == 1.0

    usage_summaries = usage_crud.list_usage_summaries(
        db, organisation_id=me["organisation_id"], user_id=me["id"]
    )
    assert len(usage_summaries) == 1
    assert usage_summaries[0].total_units == 1.0

    usage_limits = limit_tracking_crud.list_usage_limits(
        db, organisation_id=me["organisation_id"], limit_type="fraud_checks"
    )
    assert len(usage_limits) == 1
    assert usage_limits[0].limit_value == 1000.0

    usage_records = limit_tracking_crud.list_limit_usage_records(
        db, organisation_id=me["organisation_id"]
    )
    assert len(usage_records) == 1
    assert usage_records[0].current_usage == 1.0

    billing_records = billing_crud.list_billing_records(
        db, organisation_id=me["organisation_id"], user_id=me["id"]
    )
    assert len(billing_records) == 1
    assert billing_records[0].usage_event_id == usage_events[0].id
    assert billing_records[0].amount > 0


def test_subscription_graphql_mutation_updates_plan_and_audits(client, db):
    suffix = uuid.uuid4().hex[:8]
    token, me = _register_and_login(
        client,
        email=f"subscription_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"Subscription Org {suffix}",
    )
    _promote_admin(db, me["id"])
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": f"subscription-upgrade-{suffix}",
    }

    client.post(
        "/api/v1/billing/plans",
        headers={**headers, "Idempotency-Key": f"starter-plan-{suffix}"},
        json={
            "organisation_id": me["organisation_id"],
            "name": "Starter",
            "plan_code": "starter",
            "price_per_unit": 0.05,
            "currency": "USD",
            "billing_interval": "monthly",
            "is_active": True,
        },
    )
    client.post(
        "/api/v1/billing/plans",
        headers={**headers, "Idempotency-Key": f"growth-plan-{suffix}"},
        json={
            "organisation_id": me["organisation_id"],
            "name": "Growth",
            "plan_code": "growth",
            "price_per_unit": 0.03,
            "currency": "USD",
            "billing_interval": "monthly",
            "is_active": True,
        },
    )
    billing_record = client.post(
        "/api/v1/billing/records",
        headers={**headers, "Idempotency-Key": f"paid-record-{suffix}"},
        json={
            "user_id": me["id"],
            "organisation_id": me["organisation_id"],
            "amount": 99.0,
            "currency": "USD",
            "status": "paid",
            "invoice_id": f"inv_sub_{suffix}",
            "description": "Upgrade charge",
            "billing_period_start": "2026-07-01T00:00:00Z",
            "billing_period_end": "2026-07-31T23:59:59Z",
        },
    )
    assert billing_record.status_code == status.HTTP_201_CREATED

    response = _graphql_subscription_mutation(
        client,
        headers,
        {
            "action": "upgrade",
            "target_plan_code": "growth",
            "billing_record_id": billing_record.json()["id"],
        },
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()["data"]["updateOrganisationSubscription"]
    assert body["action"] == "upgrade"
    assert body["previousPlanCode"] == "starter"
    assert body["currentPlanCode"] == "growth"
    assert body["currentSubscriptionStatus"] == "active"

    organisation = organisation_crud.get_organisation_by_id(db, me["organisation_id"])
    assert organisation.plan_code == "growth"
    assert organisation.subscription_status == "active"

    audit_logs = audit_crud.list_audit_logs(
        db,
        organisation_id=me["organisation_id"],
        event_type="billing_subscription",
        resource_type="organisation_subscription",
    )
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "upgrade"
    assert audit_logs[0].new_value["plan_code"] == "growth"


def test_growth_enrichment_lookup_is_metered_and_visible_in_entitlements(client, db):
    from cruds.ip_geolocation_crud import create_ip_geolocation

    suffix = uuid.uuid4().hex[:8]
    token, me = _register_and_login(
        client,
        email=f"growth_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"Growth Org {suffix}",
    )
    _promote_admin(db, me["id"])
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/api/v1/billing/plans",
        headers={**headers, "Idempotency-Key": f"growth-plan-{suffix}"},
        json={
            "organisation_id": me["organisation_id"],
            "name": "Growth",
            "plan_code": "growth",
            "price_per_unit": 0.01,
            "currency": "USD",
            "billing_interval": "monthly",
            "is_active": True,
        },
    )
    billing_record = client.post(
        "/api/v1/billing/records",
        headers={**headers, "Idempotency-Key": f"growth-paid-{suffix}"},
        json={
            "user_id": me["id"],
            "organisation_id": me["organisation_id"],
            "amount": 49.0,
            "currency": "USD",
            "status": "paid",
            "invoice_id": f"inv_growth_{suffix}",
            "description": "Growth plan",
            "billing_period_start": "2026-07-01T00:00:00Z",
            "billing_period_end": "2026-07-31T23:59:59Z",
        },
    )
    assert billing_record.status_code == status.HTTP_201_CREATED

    update_response = _graphql_subscription_mutation(
        client,
        {**headers, "Idempotency-Key": f"growth-upgrade-{suffix}"},
        {
            "action": "upgrade",
            "target_plan_code": "growth",
            "billing_record_id": billing_record.json()["id"],
        },
    )
    assert update_response.status_code == status.HTTP_200_OK

    create_ip_geolocation(
        db,
        ip_start="1.1.1.0",
        ip_end="1.1.1.255",
        country_code="US",
        region="CA",
        city="Los Angeles",
        latitude="34.0522",
        longitude="-118.2437",
        isp="Example ISP",
    )

    lookup = client.get(
        "/api/v1/enrichment/ip-geolocation/lookup?ip_address=1.1.1.1",
        headers=headers,
    )
    assert lookup.status_code == status.HTTP_200_OK

    usage_events = usage_crud.list_usage_events(
        db, organisation_id=me["organisation_id"], user_id=me["id"]
    )
    assert any(event.event_type == "enrichment_lookups" for event in usage_events)

    entitlements = client.get("/api/v1/billing/entitlements", headers=headers)
    assert entitlements.status_code == status.HTTP_200_OK
    assert entitlements.headers["Cache-Control"] == "private, max-age=30"
    body = entitlements.json()
    assert body["plan"]["code"] == "growth"
    assert "enrichment" not in body["blocked_features"]
    quota_map = {item["quota_key"]: item for item in body["quotas"]}
    assert quota_map["enrichment_lookups"]["feature_enabled"] is True
    assert quota_map["enrichment_lookups"]["current_usage"] == 1.0
    usage_metric_map = {item["event_type"]: item for item in body["usage_metrics"]}
    assert usage_metric_map["enrichment_lookups"]["total_units"] == 1.0
    assert usage_metric_map["enrichment_lookups"]["pending_amount"] > 0


def test_payment_failed_mutation_marks_subscription_past_due(client, db):
    suffix = uuid.uuid4().hex[:8]
    token, me = _register_and_login(
        client,
        email=f"payment_failed_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"Past Due Org {suffix}",
    )
    _promote_admin(db, me["id"])
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": f"payment-failed-{suffix}",
    }

    failed_record = client.post(
        "/api/v1/billing/records",
        headers={**headers, "Idempotency-Key": f"failed-record-{suffix}"},
        json={
            "user_id": me["id"],
            "organisation_id": me["organisation_id"],
            "amount": 19.0,
            "currency": "USD",
            "status": "pending",
            "invoice_id": f"inv_failed_{suffix}",
            "description": "Renewal charge",
            "billing_period_start": "2026-07-01T00:00:00Z",
            "billing_period_end": "2026-07-31T23:59:59Z",
        },
    )
    assert failed_record.status_code == status.HTTP_201_CREATED

    mutation = _graphql_subscription_mutation(
        client,
        headers,
        {
            "action": "payment_failed",
            "billing_record_id": failed_record.json()["id"],
            "reason": "card_declined",
        },
    )
    assert mutation.status_code == status.HTTP_200_OK
    body = mutation.json()["data"]["updateOrganisationSubscription"]
    assert body["currentSubscriptionStatus"] == "past_due"

    organisation = organisation_crud.get_organisation_by_id(db, me["organisation_id"])
    assert organisation.subscription_status == "past_due"
    billing_record_db = billing_crud.get_billing_record_by_id(db, failed_record.json()["id"])
    assert billing_record_db.status == "failed"
