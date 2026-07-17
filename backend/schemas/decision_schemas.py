from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class FraudDecision(str, Enum):
    approve = "approve"
    review = "review"
    decline = "decline"


class ReasonCode(str, Enum):
    high_amount = "high_amount"
    velocity_spike = "velocity_spike"
    repeated_failed_attempts = "repeated_failed_attempts"
    new_account = "new_account"
    cross_border_mismatch = "cross_border_mismatch"
    missing_device = "missing_device"
    risky_payment_method = "risky_payment_method"
    manual_entry = "manual_entry"
    email_mismatch = "email_mismatch"
    low_signal_profile = "low_signal_profile"


class DecisionBase(BaseModel):
    transaction_id: int
    user_id: int
    organisation_id: int
    risk_score: float = Field(ge=0, le=100)
    decision: FraudDecision
    reason_codes: list[ReasonCode] = Field(default_factory=list)


class DecisionCreate(DecisionBase):
    pass


class DecisionOut(DecisionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
