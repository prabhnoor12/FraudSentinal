import uuid

from services import fraud_rule_service


def _register_and_login(
    client, *, email: str, password: str, organisation_name: str | None
):
    payload = {"email": email, "password": password}
    if organisation_name is not None:
        payload["organisation_name"] = organisation_name

    register_response = client.post("/api/v1/auth/register", json=payload)
    assert register_response.status_code in (200, 201)

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    return token, me_response.json()


def test_metrics_endpoint_reports_fraud_check_activity(client, db):
    fraud_rule_service.seed_default_fraud_rules(db)
    suffix = uuid.uuid4().hex[:8]
    token, me = _register_and_login(
        client,
        email=f"metrics_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"MetricsOrg_{suffix}",
    )

    response = client.post(
        "/api/v1/check-fraud",
        json={
            "user_id": me["id"],
            "organisation_id": me["organisation_id"],
            "amount": 50,
            "currency": "USD",
            "payment_method": "cc",
            "channel": "web",
            "customer_id": "cust-metrics",
            "device_id": "device-metrics",
            "metadata": {},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    metrics_response = client.get("/api/v1/metrics")
    assert metrics_response.status_code == 200
    payload = metrics_response.json()
    fraud_detection = payload["fraud_detection"]
    assert fraud_detection["fraud_checks_total"] == 1
    assert fraud_detection["decision_counts"]["approve"] == 1
    assert fraud_detection["recent_sample_size"] == 1
    assert fraud_detection["avg_duration_ms"] >= 0
    assert fraud_detection["duration_p95_ms"] >= 0
    assert fraud_detection["ml_enabled_checks"] in (0, 1)
    assert "error_counts" in fraud_detection

    prometheus_response = client.get("/api/v1/metrics/prometheus")
    assert prometheus_response.status_code == 200
    assert "fraudsentinel_fraud_checks_total" in prometheus_response.text
    assert "fraudsentinel_fraud_metrics_backend_info" in prometheus_response.text


def test_metrics_endpoint_tracks_validation_failures(client, db):
    fraud_rule_service.seed_default_fraud_rules(db)
    suffix = uuid.uuid4().hex[:8]
    token, me = _register_and_login(
        client,
        email=f"metrics_validation_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"MetricsValidationOrg_{suffix}",
    )

    response = client.post(
        "/api/v1/check-fraud",
        json={"user_id": me["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    metrics_response = client.get("/api/v1/metrics")
    assert metrics_response.status_code == 200
    payload = metrics_response.json()
    fraud_detection = payload["fraud_detection"]
    assert fraud_detection["error_counts"]["schema_validation_error"] >= 1
