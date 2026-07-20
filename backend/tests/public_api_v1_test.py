from fastapi import status


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
