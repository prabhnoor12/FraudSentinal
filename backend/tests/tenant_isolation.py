import pytest
from fastapi import status


def test_tenant_isolation_fraud_rules(client):
    # Register Org A and User A
    client.post(
        "/auth/register",
        json={
            "email": "user_a@org_a.com",
            "password": "StrongPass123!",
            "organisation_name": "Org A"
        }
    )
    login_a = client.post(
        "/auth/login",
        json={"email": "user_a@org_a.com", "password": "StrongPass123!"}
    )
    token_a = login_a.json()["access_token"]

    # Register Org B and User B
    client.post(
        "/auth/register",
        json={
            "email": "user_b@org_b.com",
            "password": "StrongPass123!",
            "organisation_name": "Org B"
        }
    )
    login_b = client.post(
        "/auth/login",
        json={"email": "user_b@org_b.com", "password": "StrongPass123!"}
    )
    token_b = login_b.json()["access_token"]

    # User A creates a fraud rule
    rule_a_response = client.post(
        "/fraud-rules/",
        json={
            "name": "Rule A",
            "rule_code": "rule_a",
            "description": "Rule A",
            "weight": 10,
            "field_name": "amount",
            "operator": "gte",
            "comparison_value": 100,
            "priority": 1
        },
        headers={"Authorization": f"Bearer {token_a}"}
    )
    rule_a_id = rule_a_response.json()["id"]

    # User B should NOT be able to see Rule A
    response_b = client.get(
        f"/fraud-rules/{rule_a_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert response_b.status_code == status.HTTP_404_NOT_FOUND

    # User B should NOT see Rule A in their list
    response_list_b = client.get(
        "/fraud-rules/",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    rules_b = response_list_b.json()
    assert not any(r["id"] == rule_a_id for r in rules_b)


def test_tenant_isolation_transactions(client):
    # Use tokens from previous registration if possible, but simpler to just re-register
    # Org A
    client.post("/auth/register", json={"email": "tx_a@org_a.com", "password": "StrongPass123!", "organisation_name": "A"})
    token_a = client.post("/auth/login", json={"email": "tx_a@org_a.com", "password": "StrongPass123!"}).json()["access_token"]
    user_a_id = client.get("/auth/me", headers={"Authorization": f"Bearer {token_a}"}).json()["id"]
    org_a_id = client.get("/auth/me", headers={"Authorization": f"Bearer {token_a}"}).json()["organisation_id"]

    # Org B
    client.post("/auth/register", json={"email": "tx_b@org_b.com", "password": "StrongPass123!", "organisation_name": "B"})
    token_b = client.post("/auth/login", json={"email": "tx_b@org_b.com", "password": "StrongPass123!"}).json()["access_token"]

    # User A creates a transaction
    tx_a_response = client.post(
        "/transactions/",
        json={
            "user_id": user_a_id,
            "organisation_id": org_a_id,
            "amount": 50,
            "currency": "USD",
            "payment_method": "cc",
            "channel": "web"
        },
        headers={"Authorization": f"Bearer {token_a}"}
    )
    tx_a_id = tx_a_response.json()["id"]

    # User B should NOT be able to see Transaction A
    response_b = client.get(
        f"/transactions/{tx_a_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert response_b.status_code == status.HTTP_404_NOT_FOUND
