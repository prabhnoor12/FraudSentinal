from __future__ import annotations

from datetime import datetime
from typing import Any

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
    rule_score: float = Field(ge=0, le=100)
    ml_score: float | None = Field(default=None, ge=0, le=100)
    decision: FraudDecision
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    matched_rule_codes: list[str] = Field(default_factory=list)
    rules_version: str
    rules_hash: str
    model_version: str | None = None
    thresholds: dict[str, Any]
    processing_time_ms: float = Field(ge=0)
    degradation_reasons: list[str] = Field(default_factory=list)
    checked_at: datetime
    score_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    scoring_snapshot: dict[str, Any] | None = None
