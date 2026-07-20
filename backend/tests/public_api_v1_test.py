from fastapi import status
from cruds import user_crud


def _register_and_login(client, email: str, password: str, organisation_name: str):
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


def test_v1_service_account_api_key_flow(client):
    token, me = _register_and_login(
        client,
        email="svc-owner@example.com",
        password="StrongPass123!",
        organisation_name="Svc Org",
    )
    headers = {"Authorization": f"Bearer {token}"}

    service_account = client.post(
        "/api/v1/auth/service-accounts",
        headers=headers,
        json={
            "organisation_id": me["organisation_id"],
            "name": "fraud-ingestor",
            "description": "production pipeline",
            "scopes": ["transactions:write", "transactions:read", "fraud:check"],
        },
    )
    assert service_account.status_code == status.HTTP_201_CREATED
    service_account_id = service_account.json()["id"]

    api_key_response = client.post(
        f"/api/v1/auth/service-accounts/{service_account_id}/keys",
        headers=headers,
        json={"name": "primary", "scopes": ["transactions:write", "transactions:read"]},
    )
    assert api_key_response.status_code == status.HTTP_201_CREATED
    api_key = api_key_response.json()["raw_key"]
    assert api_key.startswith("fs_live_")

    tx_response = client.post(
        "/api/v1/transactions",
        headers={
            "X-API-Key": api_key,
            "Idempotency-Key": "txn-v1-svc-001",
        },
        json={
            "user_id": me["id"],
            "organisation_id": me["organisation_id"],
            "amount": 42.5,
            "currency": "USD",
            "payment_method": "card",
            "channel": "api",
            "customer_id": "cust_123",
            "metadata": {"source": "service-account"},
        },
    )
    assert tx_response.status_code == status.HTTP_201_CREATED
    transaction_id = tx_response.json()["id"]

    get_response = client.get(
        f"/api/v1/transactions/{transaction_id}",
        headers={"X-API-Key": api_key},
    )
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["id"] == transaction_id


def test_v1_idempotency_replays_same_response(client):
    token, me = _register_and_login(
        client,
        email="idem@example.com",
        password="StrongPass123!",
        organisation_name="Idem Org",
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": "txn-v1-idem-001",
    }
    payload = {
        "user_id": me["id"],
        "organisation_id": me["organisation_id"],
        "amount": 99.99,
        "currency": "USD",
        "payment_method": "card",
        "channel": "api",
        "customer_id": "idem-customer",
        "metadata": {"mode": "idem"},
    }

    first = client.post("/api/v1/transactions", headers=headers, json=payload)
    second = client.post("/api/v1/transactions", headers=headers, json=payload)

    assert first.status_code == status.HTTP_201_CREATED
    assert second.status_code == status.HTTP_201_CREATED
    assert first.json() == second.json()


def test_v1_requires_idempotency_key_for_write_endpoints(client):
    token, me = _register_and_login(
        client,
        email="missing-idem@example.com",
        password="StrongPass123!",
        organisation_name="Missing Idem Org",
    )
    response = client.post(
        "/api/v1/transactions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "user_id": me["id"],
            "organisation_id": me["organisation_id"],
            "amount": 12.34,
            "currency": "USD",
            "payment_method": "card",
            "channel": "api",
            "customer_id": "cust-missing-idem",
            "metadata": {},
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    body = response.json()
    assert body["error"]["code"] == "missing_idempotency_key"
    assert body["error"]["request_id"]
    assert response.headers["X-Request-ID"]


def test_openapi_and_docs_expose_v1_api(client):
    docs = client.get("/docs")
    assert docs.status_code == status.HTTP_200_OK

    openapi = client.get("/openapi.json")
    assert openapi.status_code == status.HTTP_200_OK
    paths = openapi.json()["paths"]
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/transactions" in paths


def test_v1_transactions_list_uses_paginated_contract(client):
    token, me = _register_and_login(
        client,
        email="paging@example.com",
        password="StrongPass123!",
        organisation_name="Paging Org",
    )
    headers = {"Authorization": f"Bearer {token}"}

    for index, amount in enumerate((10.0, 30.0, 20.0), start=1):
        response = client.post(
            "/api/v1/transactions",
            headers={**headers, "Idempotency-Key": f"paging-txn-{index}"},
            json={
                "user_id": me["id"],
                "organisation_id": me["organisation_id"],
                "amount": amount,
                "currency": "USD",
                "payment_method": "card",
                "channel": "api",
                "customer_id": f"paging-customer-{index}",
                "metadata": {},
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    list_response = client.get(
        "/api/v1/transactions?limit=2&offset=1&sort_by=amount&sort_dir=asc",
        headers=headers,
    )
    assert list_response.status_code == status.HTTP_200_OK

    body = list_response.json()
    assert len(body["items"]) == 2
    assert body["pagination"]["total"] == 3
    assert body["pagination"]["limit"] == 2
    assert body["pagination"]["offset"] == 1
    assert body["pagination"]["previous"].endswith("limit=2&offset=0&sort_by=amount&sort_dir=asc")
    assert body["items"][0]["amount"] == 20.0
    assert body["items"][1]["amount"] == 30.0


def test_v1_service_account_lists_use_paginated_contract(client):
    token, me = _register_and_login(
        client,
        email="svc-list@example.com",
        password="StrongPass123!",
        organisation_name="Svc List Org",
    )
    headers = {"Authorization": f"Bearer {token}"}

    created_ids = []
    for name in ("worker-a", "worker-b"):
        response = client.post(
            "/api/v1/auth/service-accounts",
            headers=headers,
            json={
                "organisation_id": me["organisation_id"],
                "name": name,
                "description": f"{name} description",
                "scopes": ["transactions:read"],
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        created_ids.append(response.json()["id"])

    list_response = client.get(
        "/api/v1/auth/service-accounts?limit=1&offset=0&sort_by=name&sort_dir=asc",
        headers=headers,
    )
    assert list_response.status_code == status.HTTP_200_OK
    body = list_response.json()
    assert body["pagination"]["total"] == 2
    assert len(body["items"]) == 1
    assert body["items"][0]["name"] == "worker-a"

    key_response = client.post(
        f"/api/v1/auth/service-accounts/{created_ids[0]}/keys",
        headers=headers,
        json={"name": "primary", "scopes": ["transactions:read"]},
    )
    assert key_response.status_code == status.HTTP_201_CREATED

    keys_list = client.get(
        f"/api/v1/auth/service-accounts/{created_ids[0]}/keys?limit=10&offset=0",
        headers=headers,
    )
    assert keys_list.status_code == status.HTTP_200_OK
    keys_body = keys_list.json()
    assert keys_body["pagination"]["total"] == 1
    assert keys_body["items"][0]["name"] == "primary"


def test_v1_usage_and_user_tracking_lists_use_paginated_contract(client):
    token, me = _register_and_login(
        client,
        email="usage-paging@example.com",
        password="StrongPass123!",
        organisation_name="Usage Paging Org",
    )
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/api/v1/usage/events",
        headers={**headers, "Idempotency-Key": "usage-event-001"},
        json={
            "user_id": me["id"],
            "organisation_id": me["organisation_id"],
            "event_type": "fraud_check",
            "units": 5,
            "unit_type": "request",
            "description": "Event one",
            "status": "recorded",
        },
    )
    client.post(
        "/api/v1/usage/events",
        headers={**headers, "Idempotency-Key": "usage-event-002"},
        json={
            "user_id": me["id"],
            "organisation_id": me["organisation_id"],
            "event_type": "billing",
            "units": 2,
            "unit_type": "request",
            "description": "Event two",
            "status": "recorded",
        },
    )
    client.post(
        "/api/v1/usage/summaries",
        headers={**headers, "Idempotency-Key": "usage-summary-001"},
        json={
            "user_id": me["id"],
            "organisation_id": me["organisation_id"],
            "period_start": "2026-07-01T00:00:00Z",
            "period_end": "2026-07-31T23:59:59Z",
            "total_units": 7,
            "currency": "USD",
        },
    )

    usage_events = client.get(
        "/api/v1/usage/events?limit=1&offset=0&sort_by=units&sort_dir=desc",
        headers=headers,
    )
    assert usage_events.status_code == status.HTTP_200_OK
    usage_events_body = usage_events.json()
    assert usage_events_body["pagination"]["total"] == 2
    assert len(usage_events_body["items"]) == 1
    assert usage_events_body["items"][0]["units"] == 5

    usage_summaries = client.get(
        "/api/v1/user-tracking/summaries?limit=10&offset=0",
        headers=headers,
    )
    assert usage_summaries.status_code == status.HTTP_200_OK
    usage_summaries_body = usage_summaries.json()
    assert usage_summaries_body["pagination"]["total"] == 1
    assert usage_summaries_body["items"][0]["total_units"] == 7


def test_v1_billing_lists_use_paginated_contract(client):
    token, me = _register_and_login(
        client,
        email="billing-paging@example.com",
        password="StrongPass123!",
        organisation_name="Billing Paging Org",
    )
    headers = {"Authorization": f"Bearer {token}"}

    plan_one = client.post(
        "/api/v1/billing/plans",
        headers={**headers, "Idempotency-Key": "billing-plan-001"},
        json={
            "organisation_id": me["organisation_id"],
            "name": "Starter",
            "price_per_unit": 1.5,
            "currency": "USD",
            "billing_interval": "monthly",
            "is_active": True,
        },
    )
    assert plan_one.status_code == status.HTTP_201_CREATED

    plan_two = client.post(
        "/api/v1/billing/plans",
        headers={**headers, "Idempotency-Key": "billing-plan-002"},
        json={
            "organisation_id": me["organisation_id"],
            "name": "Legacy",
            "price_per_unit": 2.5,
            "currency": "USD",
            "billing_interval": "monthly",
            "is_active": False,
        },
    )
    assert plan_two.status_code == status.HTTP_201_CREATED

    record = client.post(
        "/api/v1/billing/records",
        headers={**headers, "Idempotency-Key": "billing-record-001"},
        json={
            "user_id": me["id"],
            "organisation_id": me["organisation_id"],
            "amount": 25.0,
            "currency": "USD",
            "status": "pending",
            "invoice_id": "inv_test_001",
            "description": "Monthly fee",
            "billing_period_start": "2026-07-01T00:00:00Z",
            "billing_period_end": "2026-07-31T23:59:59Z",
        },
    )
    assert record.status_code == status.HTTP_201_CREATED

    plans_list = client.get(
        "/api/v1/billing/plans?is_active=true&limit=10&offset=0&sort_by=name&sort_dir=asc",
        headers=headers,
    )
    assert plans_list.status_code == status.HTTP_200_OK
    plans_body = plans_list.json()
    assert plans_body["pagination"]["total"] == 1
    assert plans_body["items"][0]["name"] == "Starter"

    records_list = client.get(
        "/api/v1/billing/records?status=pending&limit=10&offset=0",
        headers=headers,
    )
    assert records_list.status_code == status.HTTP_200_OK
    records_body = records_list.json()
    assert records_body["pagination"]["total"] == 1
    assert records_body["items"][0]["invoice_id"] == "inv_test_001"


def test_v1_audit_list_uses_paginated_contract(client, db):
    token, me = _register_and_login(
        client,
        email="audit-paging@example.com",
        password="StrongPass123!",
        organisation_name="Audit Paging Org",
    )
    user = user_crud.get_user_by_id(db, me["id"])
    user.role = "admin"
    db.commit()
    headers = {"Authorization": f"Bearer {token}"}

    audit_list = client.get(
        "/api/v1/audit?limit=5&offset=0&sort_by=created_at&sort_dir=desc",
        headers=headers,
    )
    assert audit_list.status_code == status.HTTP_200_OK
    body = audit_list.json()
    assert "items" in body
    assert "pagination" in body
    assert body["pagination"]["limit"] == 5
    assert body["pagination"]["offset"] == 0


def test_v1_limit_tracking_and_sessions_lists_use_paginated_contract(client):
    token, me = _register_and_login(
        client,
        email="ops-paging@example.com",
        password="StrongPass123!",
        organisation_name="Ops Paging Org",
    )
    headers = {"Authorization": f"Bearer {token}"}

    usage_limit = client.post(
        "/api/v1/limit-tracking/limits",
        headers={**headers, "Idempotency-Key": "limit-create-001"},
        json={
            "user_id": me["id"],
            "organisation_id": me["organisation_id"],
            "limit_type": "fraud_checks",
            "limit_value": 100,
            "period": "monthly",
            "is_active": "true",
        },
    )
    assert usage_limit.status_code == status.HTTP_201_CREATED
    usage_limit_id = usage_limit.json()["id"]

    usage_record = client.post(
        "/api/v1/limit-tracking/records",
        headers={**headers, "Idempotency-Key": "limit-record-001"},
        json={
            "usage_limit_id": usage_limit_id,
            "current_usage": 17,
            "period_start": "2026-07-01T00:00:00Z",
            "period_end": "2026-07-31T23:59:59Z",
        },
    )
    assert usage_record.status_code == status.HTTP_201_CREATED

    session_one = client.post(
        "/api/v1/sessions",
        headers={**headers, "Idempotency-Key": "session-create-001"},
        json={
            "user_id": me["id"],
            "session_token": "session-token-001",
            "ip_address": "127.0.0.1",
            "user_agent": "pytest-agent",
            "status": "active",
        },
    )
    assert session_one.status_code == status.HTTP_201_CREATED

    session_two = client.post(
        "/api/v1/sessions",
        headers={**headers, "Idempotency-Key": "session-create-002"},
        json={
            "user_id": me["id"],
            "session_token": "session-token-002",
            "ip_address": "127.0.0.2",
            "user_agent": "pytest-agent",
            "status": "active",
        },
    )
    assert session_two.status_code == status.HTTP_201_CREATED

    limits_list = client.get(
        "/api/v1/limit-tracking/limits?limit=10&offset=0&sort_by=limit_value&sort_dir=desc",
        headers=headers,
    )
    assert limits_list.status_code == status.HTTP_200_OK
    limits_body = limits_list.json()
    assert limits_body["pagination"]["total"] == 1
    assert limits_body["items"][0]["limit_type"] == "fraud_checks"

    records_list = client.get(
        f"/api/v1/limit-tracking/records?usage_limit_id={usage_limit_id}&limit=10&offset=0",
        headers=headers,
    )
    assert records_list.status_code == status.HTTP_200_OK
    records_body = records_list.json()
    assert records_body["pagination"]["total"] == 1
    assert records_body["items"][0]["current_usage"] == 17

    sessions_list = client.get(
        f"/api/v1/sessions?user_id={me['id']}&limit=1&offset=0&sort_by=started_at&sort_dir=desc",
        headers=headers,
    )
    assert sessions_list.status_code == status.HTTP_200_OK
    sessions_body = sessions_list.json()
    assert sessions_body["pagination"]["total"] == 2
    assert len(sessions_body["items"]) == 1


def test_v1_users_organisations_and_enrichment_lists_use_paginated_contract(client, db):
    from cruds.bin_lookup_crud import create_bin_lookup
    from cruds.ip_geolocation_crud import create_ip_geolocation

    token, me = _register_and_login(
        client,
        email="catalog-paging@example.com",
        password="StrongPass123!",
        organisation_name="Catalog Paging Org",
    )
    headers = {"Authorization": f"Bearer {token}"}

    created_user = client.post(
        "/api/v1/users",
        headers={**headers, "Idempotency-Key": "user-create-001"},
        json={
            "email": "member@example.com",
            "password": "StrongPass123!",
            "full_name": "Member User",
            "phone": "1234567890",
            "role": "investigator",
            "is_active": True,
        },
    )
    assert created_user.status_code == status.HTTP_201_CREATED

    users_list = client.get(
        "/api/v1/users?limit=10&offset=0&sort_by=email&sort_dir=asc",
        headers=headers,
    )
    assert users_list.status_code == status.HTTP_200_OK
    users_body = users_list.json()
    assert users_body["pagination"]["total"] == 2
    assert users_body["items"][0]["email"] == "catalog-paging@example.com"

    organisations_list = client.get(
        "/api/v1/organisations?limit=10&offset=0",
        headers=headers,
    )
    assert organisations_list.status_code == status.HTTP_200_OK
    organisations_body = organisations_list.json()
    assert organisations_body["pagination"]["total"] == 1
    assert organisations_body["items"][0]["id"] == me["organisation_id"]

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
    create_bin_lookup(
        db,
        bin_number="411111",
        card_brand="visa",
        card_type="credit",
        issuing_bank="Example Bank",
        issuing_country_code="US",
        is_prepaid=False,
        risk_score=75,
    )

    ip_list = client.get(
        "/api/v1/enrichment/ip-geolocation/list?limit=5&offset=0",
        headers=headers,
    )
    assert ip_list.status_code == status.HTTP_200_OK
    ip_body = ip_list.json()
    assert "items" in ip_body
    assert "pagination" in ip_body
    assert ip_body["pagination"]["limit"] == 5

    bin_list = client.get(
        "/api/v1/enrichment/bin-lookup/list?limit=5&offset=0&high_risk_only=true",
        headers=headers,
    )
    assert bin_list.status_code == status.HTTP_200_OK
    bin_body = bin_list.json()
    assert "items" in bin_body
    assert "pagination" in bin_body
    assert bin_body["pagination"]["limit"] == 5
