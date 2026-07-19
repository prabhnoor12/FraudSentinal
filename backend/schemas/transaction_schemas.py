from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TransactionBase(BaseModel):
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


class TransactionCreate(TransactionBase):
    pass


class TransactionOut(TransactionBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
