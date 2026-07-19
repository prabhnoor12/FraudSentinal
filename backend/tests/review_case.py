import pytest


@pytest.fixture
def auth_header(client):
    client.post(
        "/auth/register",
        json={
            "email": "case@test.com",
            "password": "StrongPass123!",
            "organisation_name": "Case",
        },
    )
    token = client.post(
        "/auth/login", json={"email": "case@test.com", "password": "StrongPass123!"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def setup_data(client, auth_header):
    # Get user and org IDs
    me = client.get("/auth/me", headers=auth_header).json()
    user_id = me["id"]
    org_id = me["organisation_id"]

    # Create a transaction that triggers a review
    # We'll mock the scoring service to return 'review'
    from unittest.mock import patch
    from schemas.decision_schemas import FraudDecision

    mock_score = {
        "risk_score": 50,
        "decision": FraudDecision.review,
        "reason_codes": ["high_amount"],
        "matched_rules": [],
    }

    with patch("services.scoring_service.score_transaction", return_value=mock_score):
        response = client.post(
            "/check-fraud",
            json={
                "user_id": user_id,
                "organisation_id": org_id,
                "amount": 1000,
                "currency": "USD",
                "payment_method": "cc",
                "channel": "web",
            },
            headers=auth_header,
        )

    # The check-fraud endpoint should have created a decision and a review case
    return response.json()


def test_list_review_cases(client, auth_header, setup_data):
    response = client.get("/review-cases", headers=auth_header)
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert data[0]["status"] == "open"


def test_resolve_review_case(client, auth_header, setup_data):
    # Get the case ID
    cases = client.get("/review-cases", headers=auth_header).json()
    case_id = cases[0]["id"]

    # Resolve it
    response = client.post(
        f"/review-cases/{case_id}/resolve",
        json={"resolution_code": "approved_by_analyst", "notes": "Looks fine"},
        headers=auth_header,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "resolved"
    assert data["resolution_code"] == "approved_by_analyst"


def test_reopen_review_case(client, auth_header, setup_data):
    # Get the case ID and resolve it first
    cases = client.get("/review-cases", headers=auth_header).json()
    case_id = cases[0]["id"]
    client.post(
        f"/review-cases/{case_id}/resolve",
        json={"resolution_code": "approved_by_analyst", "notes": "ok"},
        headers=auth_header,
    )

    # Reopen it
    response = client.post(
        f"/review-cases/{case_id}/reopen",
        json={"reason": "Need more info"},
        headers=auth_header,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "open"
