from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ReviewCaseStatus(str, Enum):
    open = "open"
    resolved = "resolved"


class ReviewCaseResolution(str, Enum):
    approve = "approve"
    decline = "decline"
    false_positive = "false_positive"
    fraud_confirmed = "fraud_confirmed"


class ReviewCaseBase(BaseModel):
    transaction_id: int
    decision_id: int
    organisation_id: int
    user_id: int
    status: ReviewCaseStatus = ReviewCaseStatus.open
    resolution: ReviewCaseResolution | None = None
    notes: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReviewCaseCreate(ReviewCaseBase):
    pass


class ReviewCaseUpdate(BaseModel):
    status: ReviewCaseStatus | None = None
    resolution: ReviewCaseResolution | None = None
    notes: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, Any] | None = None


class ReviewCaseOut(ReviewCaseBase):
    id: int
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None

    class Config:
        from_attributes = True
