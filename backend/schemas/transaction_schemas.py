from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, field_validator

from schemas.api_schemas import PaginatedResponse, StrictSchema
from utils.security_utils import (
    normalize_country_code,
    normalize_ip_address,
    sanitize_input,
)


class TransactionBase(StrictSchema):
    user_id: int
    organisation_id: int
    external_transaction_id: str | None = Field(default=None, max_length=100)
    amount: float = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    payment_method: str = Field(min_length=2, max_length=50)
    channel: str = Field(default="api", min_length=2, max_length=50)
    customer_id: str | None = Field(default=None, max_length=100)
    customer_email: str | None = Field(default=None, max_length=255)
    billing_country: str | None = Field(default=None, max_length=2)
    shipping_country: str | None = Field(default=None, max_length=2)
    ip_address: str | None = Field(default=None, max_length=64)
    device_id: str | None = Field(default=None, max_length=255)
    account_age_days: int | None = Field(default=None, ge=0)
    transactions_last_24h: int = Field(default=0, ge=0)
    failed_attempts_last_24h: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "external_transaction_id",
        "payment_method",
        "channel",
        "customer_id",
        "device_id",
        mode="before",
    )
    @classmethod
    def sanitize_strings(cls, value: Any):
        if value is None:
            return None
        return sanitize_input(value)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Any) -> str:
        return sanitize_input(value, max_length=3).upper()

    @field_validator("billing_country", "shipping_country", mode="before")
    @classmethod
    def validate_country_codes(cls, value: Any):
        if value in (None, ""):
            return None
        return normalize_country_code(str(value))

    @field_validator("ip_address", mode="before")
    @classmethod
    def validate_ip(cls, value: Any):
        if value in (None, ""):
            return None
        return normalize_ip_address(str(value))


class TransactionCreate(TransactionBase):
    pass


class TransactionOut(TransactionBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class TransactionListResponse(PaginatedResponse[TransactionOut]):
    pass
