from __future__ import annotations

from datetime import datetime

from pydantic import Field

from schemas.api_schemas import StrictSchema
from schemas.decision_schemas import FraudDecision, ReasonCode
from schemas.transaction_schemas import TransactionCreate


class FraudCheckRequest(TransactionCreate):
    pass


class FraudCheckResponse(StrictSchema):
    transaction_id: int
    decision_id: int
    risk_score: float = Field(ge=0, le=100)
    decision: FraudDecision
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    checked_at: datetime
