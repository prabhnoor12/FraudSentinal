from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from schemas.decision_schemas import ReasonCode


class FraudRuleOperator(str, Enum):
    gte = "gte"
    gt = "gt"
    lte = "lte"
    lt = "lt"
    eq = "eq"
    neq = "neq"
    in_list = "in"
    not_in = "not_in"
    is_missing = "is_missing"
    field_mismatch = "field_mismatch"


class FraudRuleField(str, Enum):
    amount = "amount"
    currency = "currency"
    payment_method = "payment_method"
    channel = "channel"
    customer_id = "customer_id"
    customer_email = "customer_email"
    billing_country = "billing_country"
    shipping_country = "shipping_country"
    ip_address = "ip_address"
    device_id = "device_id"
    account_age_days = "account_age_days"
    transactions_last_24h = "transactions_last_24h"
    failed_attempts_last_24h = "failed_attempts_last_24h"
    external_transaction_id = "external_transaction_id"


class FraudRuleBase(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    rule_code: str = Field(min_length=3, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    organisation_id: int | None = None
    reason_code: ReasonCode
    weight: float = Field(ge=0, le=100)
    field_name: FraudRuleField
    operator: FraudRuleOperator
    comparison_value: Any = None
    secondary_field_name: FraudRuleField | None = None
    enabled: bool = True
    priority: int = Field(default=100, ge=0, le=10000)


class FraudRuleCreate(FraudRuleBase):
    pass


class FraudRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=100)
    rule_code: str | None = Field(default=None, min_length=3, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    organisation_id: int | None = None
    reason_code: ReasonCode | None = None
    weight: float | None = Field(default=None, ge=0, le=100)
    field_name: FraudRuleField | None = None
    operator: FraudRuleOperator | None = None
    comparison_value: Any = None
    secondary_field_name: FraudRuleField | None = None
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=10000)


class FraudRuleOut(FraudRuleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
