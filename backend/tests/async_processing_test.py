import uuid

from cruds import audit_crud
from services import fraud_rule_service


def _register_and_login(
    client, *, email: str, password: str, organisation_name: str | None
):
    payload = {"email": email, "password": password}
    if organisation_name is not None:
        payload["organisation_name"] = organisation_name

    register_response = client.post("/auth/register", json=payload)
    assert register_response.status_code in (200, 201)

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    return token, me_response.json()


def test_check_fraud_writes_background_audit_log(client, db):
    fraud_rule_service.seed_default_fraud_rules(db)
    suffix = uuid.uuid4().hex[:8]
    token, me = _register_and_login(
        client,
        email=f"async_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"AsyncOrg_{suffix}",
    )

    response = client.post(
        "/check-fraud",
        json={
            "user_id": me["id"],
            "organisation_id": me["organisation_id"],
            "amount": 50,
            "currency": "USD",
            "payment_method": "cc",
            "channel": "web",
            "customer_id": "cust-async",
            "device_id": "device-async",
            "metadata": {},
        },
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0 Chrome/126 Windows",
        },
    )

    assert response.status_code == 200
    body = response.json()

    logs = audit_crud.list_audit_logs(
        db,
        organisation_id=me["organisation_id"],
        resource_type="fraud_check",
        limit=10,
    )
    assert logs
    latest = logs[0]
    assert latest.action == "fraud_check_completed"
    assert latest.resource_id == str(body["transaction_id"])
    assert latest.details["decision_id"] == body["decision_id"]
