import uuid

import pytest
from fastapi import status

from cruds import fraud_rule_crud
from schemas.decision_schemas import ReasonCode
from schemas.fraud_rule_schemas import FraudRuleField, FraudRuleOperator
from services import fraud_rule_service


def _register_and_login(client, *, email: str, password: str, organisation_name: str | None):
    payload = {"email": email, "password": password}
    if organisation_name is not None:
        payload["organisation_name"] = organisation_name

    r = client.post("/auth/register", json=payload)
    assert r.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == status.HTTP_200_OK
    token = login.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == status.HTTP_200_OK
    return token, me.json()


def _rule_payload(*, rule_code: str, reason_code: ReasonCode, **overrides):
    payload = {
        "name": "Rule Name",
        "rule_code": rule_code,
        "description": "Test rule",
        "weight": 10,
        "field_name": FraudRuleField.transactions_last_24h.value,
        "operator": FraudRuleOperator.gte.value,
        "comparison_value": 3,
        "priority": 10,
        "reason_code": reason_code.value,
    }
    payload.update(overrides)
    return payload


def test_fraud_rules_requires_auth(client):
    r = client.get("/fraud-rules")
    assert r.status_code == status.HTTP_401_UNAUTHORIZED


def test_create_fraud_rule_enforces_org_id_from_token(client):
    suffix_a = uuid.uuid4().hex[:10]
    token_a, me_a = _register_and_login(
        client,
        email=f"usera_{suffix_a}@example.com",
        password="StrongPass123!",
        organisation_name=f"OrgA_{suffix_a}",
    )

    suffix_b = uuid.uuid4().hex[:10]
    _, me_b = _register_and_login(
        client,
        email=f"userb_{suffix_b}@example.com",
        password="StrongPass123!",
        organisation_name=f"OrgB_{suffix_b}",
    )

    r = client.post(
        "/fraud-rules",
        json=_rule_payload(
            rule_code="tenant_override_test",
            reason_code=ReasonCode.velocity_spike,
            organisation_id=me_b["organisation_id"],
        ),
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r.status_code == status.HTTP_201_CREATED
    body = r.json()
    assert body["organisation_id"] == me_a["organisation_id"]


def test_create_fraud_rule_normalizes_rule_code(client):
    suffix = uuid.uuid4().hex[:10]
    token, me = _register_and_login(
        client,
        email=f"norm_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"Org_{suffix}",
    )

    r = client.post(
        "/fraud-rules",
        json=_rule_payload(
            rule_code="My Rule Code",
            reason_code=ReasonCode.high_amount,
        ),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == status.HTTP_201_CREATED
    body = r.json()
    assert body["organisation_id"] == me["organisation_id"]
    assert body["rule_code"] == "my_rule_code"


def test_create_fraud_rule_duplicate_rule_code_conflict(client):
    suffix = uuid.uuid4().hex[:10]
    token, _ = _register_and_login(
        client,
        email=f"dupe_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"Org_{suffix}",
    )

    r1 = client.post(
        "/fraud-rules",
        json=_rule_payload(rule_code="dupe_code", reason_code=ReasonCode.velocity_spike),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == status.HTTP_201_CREATED

    r2 = client.post(
        "/fraud-rules",
        json=_rule_payload(rule_code="dupe_code", reason_code=ReasonCode.velocity_spike),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == status.HTTP_409_CONFLICT


def test_tenant_isolation_get_and_list(client):
    suffix_a = uuid.uuid4().hex[:10]
    token_a, _ = _register_and_login(
        client,
        email=f"ta_{suffix_a}@example.com",
        password="StrongPass123!",
        organisation_name=f"OrgA_{suffix_a}",
    )

    suffix_b = uuid.uuid4().hex[:10]
    token_b, _ = _register_and_login(
        client,
        email=f"tb_{suffix_b}@example.com",
        password="StrongPass123!",
        organisation_name=f"OrgB_{suffix_b}",
    )

    create = client.post(
        "/fraud-rules",
        json=_rule_payload(rule_code="only_org_a", reason_code=ReasonCode.velocity_spike),
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert create.status_code == status.HTTP_201_CREATED
    rule_id = create.json()["id"]

    get_b = client.get(
        f"/fraud-rules/{rule_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert get_b.status_code == status.HTTP_404_NOT_FOUND

    list_b = client.get(
        "/fraud-rules",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert list_b.status_code == status.HTTP_200_OK
    assert not any(r["id"] == rule_id for r in list_b.json())


def test_enable_disable_and_enabled_filter(client):
    suffix = uuid.uuid4().hex[:10]
    token, _ = _register_and_login(
        client,
        email=f"toggle_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"Org_{suffix}",
    )

    created = client.post(
        "/fraud-rules",
        json=_rule_payload(rule_code="toggle_rule", reason_code=ReasonCode.velocity_spike),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == status.HTTP_201_CREATED
    rule_id = created.json()["id"]

    disabled = client.post(
        f"/fraud-rules/{rule_id}/disable",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert disabled.status_code == status.HTTP_200_OK
    assert disabled.json()["enabled"] is False

    enabled_list = client.get(
        "/fraud-rules",
        params={"enabled": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert enabled_list.status_code == status.HTTP_200_OK
    assert not any(r["id"] == rule_id for r in enabled_list.json())

    enabled = client.post(
        f"/fraud-rules/{rule_id}/enable",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert enabled.status_code == status.HTTP_200_OK
    assert enabled.json()["enabled"] is True


def test_update_rule_normalizes_rule_code_and_preserves_tenant(client):
    suffix = uuid.uuid4().hex[:10]
    token, me = _register_and_login(
        client,
        email=f"upd_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"Org_{suffix}",
    )

    created = client.post(
        "/fraud-rules",
        json=_rule_payload(rule_code="to_update", reason_code=ReasonCode.high_amount),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == status.HTTP_201_CREATED
    rule_id = created.json()["id"]

    updated = client.put(
        f"/fraud-rules/{rule_id}",
        json={"rule_code": "Updated Code", "organisation_id": 999999},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert updated.status_code == status.HTTP_200_OK
    body = updated.json()
    assert body["rule_code"] == "updated_code"
    assert body["organisation_id"] == me["organisation_id"]


def test_cannot_disable_global_rule_from_tenant(client, db):
    fraud_rule_service.seed_default_fraud_rules(db)
    global_rule = fraud_rule_crud.get_fraud_rule_by_code(db, rule_code="velocity_spike_3", organisation_id=None)
    assert global_rule is not None

    suffix = uuid.uuid4().hex[:10]
    token, _ = _register_and_login(
        client,
        email=f"global_{suffix}@example.com",
        password="StrongPass123!",
        organisation_name=f"Org_{suffix}",
    )

    r = client.post(
        f"/fraud-rules/{global_rule.id}/disable",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST


def test_effective_rules_prefer_org_override(db):
    fraud_rule_service.seed_default_fraud_rules(db)

    org_id = 1
    payload = {
        "name": "Velocity override",
        "rule_code": "velocity_spike_3",
        "description": "Override global rule for this org",
        "organisation_id": org_id,
        "reason_code": ReasonCode.velocity_spike,
        "weight": 99,
        "field_name": FraudRuleField.transactions_last_24h,
        "operator": FraudRuleOperator.gte,
        "comparison_value": 3,
        "priority": 1,
        "enabled": True,
        "secondary_field_name": None,
    }
    fraud_rule_crud.create_fraud_rule(db, **payload)

    effective = fraud_rule_service.list_effective_fraud_rules_service(db, organisation_id=org_id)
    by_code = {r.rule_code: r for r in effective}
    assert "velocity_spike_3" in by_code
    assert by_code["velocity_spike_3"].organisation_id == org_id
    assert float(by_code["velocity_spike_3"].weight) == 99.0