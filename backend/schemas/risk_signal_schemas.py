from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from schemas.api_schemas import PaginatedResponse
from schemas.decision_schemas import ReasonCode


class RiskSignalBase(BaseModel):
    transaction_id: int
    decision_id: int
    organisation_id: int
    user_id: int
    rule_id: int | None = None
    rule_code: str = Field(min_length=3, max_length=100)
    reason_code: ReasonCode
    weight: float = Field(ge=0, le=100)
    details: dict[str, Any] = Field(default_factory=dict)


class RiskSignalCreate(RiskSignalBase):
    pass


class RiskSignalOut(RiskSignalBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RiskSignalListResponse(PaginatedResponse[RiskSignalOut]):
    pass
