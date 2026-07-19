from __future__ import annotations

from sqlalchemy.orm import Session

from cruds import fraud_rule_crud, organisation_crud
from models.fraud_rule_models import FraudRule
from schemas.audit_schemas import AuditContext
from schemas.decision_schemas import ReasonCode
from schemas.fraud_rule_schemas import (
    FraudRuleCreate,
    FraudRuleField,
    FraudRuleOperator,
    FraudRuleUpdate,
)
from services.audit_service import AuditService
from utils.exception_handling_utils import ConflictError, NotFoundError, ValidationError


NUMERIC_FIELDS = {
    FraudRuleField.amount,
    FraudRuleField.account_age_days,
    FraudRuleField.transactions_last_24h,
    FraudRuleField.failed_attempts_last_24h,
}

STRING_FIELDS = {
    FraudRuleField.currency,
    FraudRuleField.payment_method,
    FraudRuleField.channel,
    FraudRuleField.customer_id,
    FraudRuleField.customer_email,
    FraudRuleField.billing_country,
    FraudRuleField.shipping_country,
    FraudRuleField.ip_address,
    FraudRuleField.device_id,
    FraudRuleField.external_transaction_id,
}

DEFAULT_FRAUD_RULES: list[dict] = [
    {
        "name": "High amount level 1",
        "rule_code": "high_amount_500",
        "description": "Adds risk for transactions at or above 500.",
        "reason_code": ReasonCode.high_amount,
        "weight": 10,
        "field_name": FraudRuleField.amount,
        "operator": FraudRuleOperator.gte,
        "comparison_value": 500,
        "priority": 10,
    },
    {
        "name": "High amount level 2",
        "rule_code": "high_amount_1000",
        "description": "Adds more risk for transactions at or above 1000.",
        "reason_code": ReasonCode.high_amount,
        "weight": 20,
        "field_name": FraudRuleField.amount,
        "operator": FraudRuleOperator.gte,
        "comparison_value": 1000,
        "priority": 20,
    },
    {
        "name": "High amount level 3",
        "rule_code": "high_amount_2000",
        "description": "Adds highest amount risk for transactions at or above 2000.",
        "reason_code": ReasonCode.high_amount,
        "weight": 35,
        "field_name": FraudRuleField.amount,
        "operator": FraudRuleOperator.gte,
        "comparison_value": 2000,
        "priority": 30,
    },
    {
        "name": "Velocity spike level 1",
        "rule_code": "velocity_spike_3",
        "description": "Adds risk when recent transaction count reaches 3.",
        "reason_code": ReasonCode.velocity_spike,
        "weight": 8,
        "field_name": FraudRuleField.transactions_last_24h,
        "operator": FraudRuleOperator.gte,
        "comparison_value": 3,
        "priority": 40,
    },
    {
        "name": "Velocity spike level 2",
        "rule_code": "velocity_spike_5",
        "description": "Adds more risk when recent transaction count reaches 5.",
        "reason_code": ReasonCode.velocity_spike,
        "weight": 15,
        "field_name": FraudRuleField.transactions_last_24h,
        "operator": FraudRuleOperator.gte,
        "comparison_value": 5,
        "priority": 50,
    },
    {
        "name": "Velocity spike level 3",
        "rule_code": "velocity_spike_10",
        "description": "Adds highest velocity risk when recent transaction count reaches 10.",
        "reason_code": ReasonCode.velocity_spike,
        "weight": 25,
        "field_name": FraudRuleField.transactions_last_24h,
        "operator": FraudRuleOperator.gte,
        "comparison_value": 10,
        "priority": 60,
    },
    {
        "name": "Repeated failed attempts level 1",
        "rule_code": "failed_attempts_1",
        "description": "Adds risk when there has been at least 1 failed attempt.",
        "reason_code": ReasonCode.repeated_failed_attempts,
        "weight": 8,
        "field_name": FraudRuleField.failed_attempts_last_24h,
        "operator": FraudRuleOperator.gte,
        "comparison_value": 1,
        "priority": 70,
    },
    {
        "name": "Repeated failed attempts level 2",
        "rule_code": "failed_attempts_2",
        "description": "Adds more risk when there have been at least 2 failed attempts.",
        "reason_code": ReasonCode.repeated_failed_attempts,
        "weight": 15,
        "field_name": FraudRuleField.failed_attempts_last_24h,
        "operator": FraudRuleOperator.gte,
        "comparison_value": 2,
        "priority": 80,
    },
    {
        "name": "Repeated failed attempts level 3",
        "rule_code": "failed_attempts_5",
        "description": "Adds highest failed-attempt risk when there have been at least 5 failed attempts.",
        "reason_code": ReasonCode.repeated_failed_attempts,
        "weight": 25,
        "field_name": FraudRuleField.failed_attempts_last_24h,
        "operator": FraudRuleOperator.gte,
        "comparison_value": 5,
        "priority": 90,
    },
    {
        "name": "New account level 1",
        "rule_code": "new_account_30",
        "description": "Adds risk when the account age is below 30 days.",
        "reason_code": ReasonCode.new_account,
        "weight": 8,
        "field_name": FraudRuleField.account_age_days,
        "operator": FraudRuleOperator.lt,
        "comparison_value": 30,
        "priority": 100,
    },
    {
        "name": "New account level 2",
        "rule_code": "new_account_14",
        "description": "Adds more risk when the account age is below 14 days.",
        "reason_code": ReasonCode.new_account,
        "weight": 15,
        "field_name": FraudRuleField.account_age_days,
        "operator": FraudRuleOperator.lt,
        "comparison_value": 14,
        "priority": 110,
    },
    {
        "name": "New account level 3",
        "rule_code": "new_account_3",
        "description": "Adds highest risk when the account age is below 3 days.",
        "reason_code": ReasonCode.new_account,
        "weight": 25,
        "field_name": FraudRuleField.account_age_days,
        "operator": FraudRuleOperator.lt,
        "comparison_value": 3,
        "priority": 120,
    },
    {
        "name": "Billing shipping mismatch",
        "rule_code": "cross_border_mismatch",
        "description": "Adds risk when billing and shipping countries do not match.",
        "reason_code": ReasonCode.cross_border_mismatch,
        "weight": 15,
        "field_name": FraudRuleField.billing_country,
        "operator": FraudRuleOperator.field_mismatch,
        "secondary_field_name": FraudRuleField.shipping_country,
        "priority": 130,
    },
    {
        "name": "Missing device",
        "rule_code": "missing_device",
        "description": "Adds risk when no device identifier is present.",
        "reason_code": ReasonCode.missing_device,
        "weight": 10,
        "field_name": FraudRuleField.device_id,
        "operator": FraudRuleOperator.is_missing,
        "priority": 140,
    },
    {
        "name": "Risky payment method",
        "rule_code": "risky_payment_method",
        "description": "Adds risk for payment methods commonly associated with fraud.",
        "reason_code": ReasonCode.risky_payment_method,
        "weight": 20,
        "field_name": FraudRuleField.payment_method,
        "operator": FraudRuleOperator.in_list,
        "comparison_value": ["crypto", "gift_card", "prepaid_card", "wire_transfer"],
        "priority": 150,
    },
    {
        "name": "Manual entry channel",
        "rule_code": "manual_entry",
        "description": "Adds risk for manually entered or call-center channels.",
        "reason_code": ReasonCode.manual_entry,
        "weight": 10,
        "field_name": FraudRuleField.channel,
        "operator": FraudRuleOperator.in_list,
        "comparison_value": ["manual", "call_center", "moto"],
        "priority": 160,
    },
]


def _normalize_rule_code(rule_code: str) -> str:
    return rule_code.strip().lower().replace(" ", "_")


def _normalize_comparison_value(field_name: FraudRuleField, comparison_value):
    if comparison_value is None:
        return None

    if field_name == FraudRuleField.currency and isinstance(comparison_value, str):
        return comparison_value.strip().upper()
    if field_name in {
        FraudRuleField.billing_country,
        FraudRuleField.shipping_country,
    } and isinstance(comparison_value, str):
        return comparison_value.strip().upper()
    if field_name in {
        FraudRuleField.payment_method,
        FraudRuleField.channel,
        FraudRuleField.customer_email,
    } and isinstance(comparison_value, str):
        return comparison_value.strip().lower()
    if isinstance(comparison_value, list):
        return [
            _normalize_comparison_value(field_name, value) for value in comparison_value
        ]
    return comparison_value


def _validate_rule_data(data: dict) -> dict:
    data = dict(data)

    if data.get("field_name") is not None and not isinstance(
        data["field_name"], FraudRuleField
    ):
        data["field_name"] = FraudRuleField(data["field_name"])
    if data.get("operator") is not None and not isinstance(
        data["operator"], FraudRuleOperator
    ):
        data["operator"] = FraudRuleOperator(data["operator"])
    if data.get("secondary_field_name") is not None and not isinstance(
        data["secondary_field_name"], FraudRuleField
    ):
        data["secondary_field_name"] = FraudRuleField(data["secondary_field_name"])

    field_name = data.get("field_name")
    operator = data.get("operator")
    comparison_value = data.get("comparison_value")
    secondary_field_name = data.get("secondary_field_name")

    if "rule_code" in data and data["rule_code"] is not None:
        data["rule_code"] = _normalize_rule_code(data["rule_code"])

    if field_name is not None and comparison_value is not None:
        data["comparison_value"] = _normalize_comparison_value(
            field_name, comparison_value
        )

    if operator in {
        FraudRuleOperator.gte,
        FraudRuleOperator.gt,
        FraudRuleOperator.lte,
        FraudRuleOperator.lt,
    }:
        if field_name not in NUMERIC_FIELDS:
            raise ValidationError(
                "Numeric comparison operators require a numeric field"
            )
        if not isinstance(data.get("comparison_value"), (int, float)):
            raise ValidationError(
                "Numeric comparison operators require a numeric comparison value"
            )

    if operator in {FraudRuleOperator.eq, FraudRuleOperator.neq}:
        if data.get("comparison_value") is None:
            raise ValidationError("Equality operators require a comparison value")

    if operator in {FraudRuleOperator.in_list, FraudRuleOperator.not_in}:
        if (
            not isinstance(data.get("comparison_value"), list)
            or not data["comparison_value"]
        ):
            raise ValidationError(
                "List operators require a non-empty comparison value list"
            )

    if (
        operator == FraudRuleOperator.is_missing
        and data.get("secondary_field_name") is not None
    ):
        raise ValidationError("The is_missing operator does not use a secondary field")

    if operator == FraudRuleOperator.field_mismatch:
        if field_name is None or secondary_field_name is None:
            raise ValidationError(
                "The field_mismatch operator requires both primary and secondary fields"
            )
        if field_name == secondary_field_name:
            raise ValidationError(
                "Primary and secondary fields must be different for field mismatch checks"
            )

    if operator == FraudRuleOperator.field_mismatch and field_name not in STRING_FIELDS:
        raise ValidationError(
            "The field_mismatch operator is only supported for comparable string fields"
        )

    return data


def _ensure_organisation_exists(db: Session, organisation_id: int | None) -> None:
    if organisation_id is not None and not organisation_crud.get_organisation_by_id(
        db, organisation_id
    ):
        raise NotFoundError("Organisation not found")


def _rule_to_dict(rule: FraudRule) -> dict:
    """Serialize a FraudRule model to a dict for auditing."""
    return {
        "name": rule.name,
        "rule_code": rule.rule_code,
        "description": rule.description,
        "weight": rule.weight,
        "field_name": rule.field_name,
        "operator": rule.operator,
        "comparison_value": rule.comparison_value,
        "secondary_field_name": rule.secondary_field_name,
        "enabled": rule.enabled,
        "priority": rule.priority,
    }


def create_fraud_rule_service(
    db: Session, payload: FraudRuleCreate, audit_ctx: AuditContext | None = None
):
    _ensure_organisation_exists(db, payload.organisation_id)
    validated = _validate_rule_data(payload.model_dump())

    existing = fraud_rule_crud.get_fraud_rule_by_code(
        db,
        rule_code=validated["rule_code"],
        organisation_id=validated.get("organisation_id"),
    )
    if existing:
        raise ConflictError("Fraud rule code already exists for this scope")

    rule = fraud_rule_crud.create_fraud_rule(db, **validated)

    if audit_ctx:
        AuditService.log_rule_change(
            db,
            user_id=audit_ctx.user_id,
            organisation_id=audit_ctx.organisation_id,
            action="create",
            rule_id=rule.id,
            new_value=_rule_to_dict(rule),
            ip_address=audit_ctx.ip_address,
            user_agent=audit_ctx.user_agent,
        )

    return rule


def list_fraud_rules_service(
    db: Session,
    *,
    organisation_id: int | None = None,
    enabled: bool | None = None,
    limit: int = 100,
):
    if organisation_id is not None:
        _ensure_organisation_exists(db, organisation_id)
    return fraud_rule_crud.list_fraud_rules(
        db,
        organisation_id=organisation_id,
        enabled=enabled,
        limit=limit,
    )


def get_fraud_rule_service(
    db: Session, rule_id: int, organisation_id: int | None = None
):
    fraud_rule = fraud_rule_crud.get_fraud_rule_by_id(db, rule_id)
    if not fraud_rule:
        raise NotFoundError("Fraud rule not found")

    # If organisation_id is provided, ensure the rule belongs to that org or is global
    if organisation_id is not None and fraud_rule.organisation_id is not None:
        if fraud_rule.organisation_id != organisation_id:
            raise NotFoundError(
                "Fraud rule not found"
            )  # Use 404 to avoid leaking existence

    return fraud_rule


def get_fraud_rule_by_code_service(
    db: Session,
    rule_code: str,
    organisation_id: int | None = None,
) -> Any | None:
    """Get a fraud rule by its unique code.

    Args:
        db: Database session
        rule_code: Unique rule code (e.g., 'geolocation_billing_mismatch')
        organisation_id: Optional organization scope

    Returns:
        FraudRule if found, None otherwise
    """
    return fraud_rule_crud.get_fraud_rule_by_code(
        db,
        rule_code=rule_code,
        organisation_id=organisation_id,
    )


def update_fraud_rule_service(
    db: Session,
    rule_id: int,
    payload: FraudRuleUpdate,
    organisation_id: int | None = None,
    audit_ctx: AuditContext | None = None,
):
    fraud_rule = get_fraud_rule_service(db, rule_id, organisation_id=organisation_id)
    old_rule_data = _rule_to_dict(fraud_rule)

    # Only org owners can update their own rules
    if organisation_id is not None and fraud_rule.organisation_id != organisation_id:
        raise ValidationError(
            "Cannot update global rules or rules from other organisations"
        )

    validated = _validate_rule_data(payload.model_dump(exclude_unset=True))

    if "organisation_id" in validated:
        _ensure_organisation_exists(db, validated["organisation_id"])

    candidate_rule_code = validated.get("rule_code", fraud_rule.rule_code)
    candidate_organisation_id = validated.get(
        "organisation_id", fraud_rule.organisation_id
    )
    existing = fraud_rule_crud.get_fraud_rule_by_code(
        db,
        rule_code=candidate_rule_code,
        organisation_id=candidate_organisation_id,
    )
    if existing and existing.id != fraud_rule.id:
        raise ConflictError("Fraud rule code already exists for this scope")

    merged_operator = validated.get("operator", fraud_rule.operator)
    merged_field_name = validated.get("field_name", fraud_rule.field_name)
    merged_secondary = validated.get(
        "secondary_field_name", fraud_rule.secondary_field_name
    )
    merged_comparison = validated.get("comparison_value", fraud_rule.comparison_value)
    merged_data = {
        "field_name": merged_field_name,
        "operator": merged_operator,
        "secondary_field_name": merged_secondary,
        "comparison_value": merged_comparison,
    }

    _validate_rule_data(merged_data)

    updated_rule = fraud_rule_crud.update_fraud_rule(db, fraud_rule, **validated)

    if audit_ctx:
        AuditService.log_rule_change(
            db,
            user_id=audit_ctx.user_id,
            organisation_id=audit_ctx.organisation_id,
            action="update",
            rule_id=updated_rule.id,
            old_value=old_rule_data,
            new_value=_rule_to_dict(updated_rule),
            ip_address=audit_ctx.ip_address,
            user_agent=audit_ctx.user_agent,
        )

    return updated_rule


def enable_fraud_rule_service(
    db: Session,
    rule_id: int,
    organisation_id: int | None = None,
    audit_ctx: AuditContext | None = None,
):
    fraud_rule = get_fraud_rule_service(db, rule_id, organisation_id=organisation_id)
    if organisation_id is not None and fraud_rule.organisation_id != organisation_id:
        raise ValidationError(
            "Cannot enable global rules or rules from other organisations"
        )

    old_rule_data = _rule_to_dict(fraud_rule)
    updated_rule = fraud_rule_crud.update_fraud_rule(db, fraud_rule, enabled=True)

    if audit_ctx:
        AuditService.log_rule_change(
            db,
            user_id=audit_ctx.user_id,
            organisation_id=audit_ctx.organisation_id,
            action="enable",
            rule_id=updated_rule.id,
            old_value=old_rule_data,
            new_value=_rule_to_dict(updated_rule),
            ip_address=audit_ctx.ip_address,
            user_agent=audit_ctx.user_agent,
        )
    return updated_rule


def disable_fraud_rule_service(
    db: Session,
    rule_id: int,
    organisation_id: int | None = None,
    audit_ctx: AuditContext | None = None,
):
    fraud_rule = get_fraud_rule_service(db, rule_id, organisation_id=organisation_id)
    if organisation_id is not None and fraud_rule.organisation_id != organisation_id:
        raise ValidationError(
            "Cannot disable global rules or rules from other organisations"
        )

    old_rule_data = _rule_to_dict(fraud_rule)
    updated_rule = fraud_rule_crud.update_fraud_rule(db, fraud_rule, enabled=False)

    if audit_ctx:
        AuditService.log_rule_change(
            db,
            user_id=audit_ctx.user_id,
            organisation_id=audit_ctx.organisation_id,
            action="disable",
            rule_id=updated_rule.id,
            old_value=old_rule_data,
            new_value=_rule_to_dict(updated_rule),
            ip_address=audit_ctx.ip_address,
            user_agent=audit_ctx.user_agent,
        )
    return updated_rule


def list_effective_fraud_rules_service(
    db: Session, *, organisation_id: int | None = None
):
    return fraud_rule_crud.list_effective_fraud_rules(
        db, organisation_id=organisation_id
    )


def seed_default_fraud_rules(db: Session) -> None:
    for rule in DEFAULT_FRAUD_RULES:
        existing = fraud_rule_crud.get_fraud_rule_by_code(
            db,
            rule_code=rule["rule_code"],
            organisation_id=None,
        )
        if existing:
            continue
        fraud_rule_crud.create_fraud_rule(
            db, organisation_id=None, enabled=True, **rule
        )
