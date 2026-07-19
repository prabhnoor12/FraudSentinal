from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ReviewCaseStatus(str, Enum):
    open = "open"
    resolved = "resolved"


class ReviewCaseResolution(str, Enum):
    approved_by_analyst = "approved_by_analyst"
    declined_by_analyst = "declined_by_analyst"
    false_positive = "false_positive"
    fraud_confirmed = "fraud_confirmed"


class ReviewCaseBase(BaseModel):
    transaction_id: int
    decision_id: int
    organisation_id: int
    user_id: int
    status: ReviewCaseStatus = ReviewCaseStatus.open
    resolution: ReviewCaseResolution | None = Field(
        default=None,
        validation_alias=AliasChoices("resolution", "resolution_code"),
        serialization_alias="resolution_code",
    )
    notes: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("metadata", "case_metadata"),
    )


class ReviewCaseCreate(ReviewCaseBase):
    pass


class ReviewCaseUpdate(BaseModel):
    status: ReviewCaseStatus | None = None
    resolution: ReviewCaseResolution | None = Field(
        default=None,
        validation_alias=AliasChoices("resolution", "resolution_code"),
        serialization_alias="resolution_code",
    )
    notes: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("metadata", "case_metadata"),
    )


class ReviewCaseResolve(BaseModel):
    resolution: ReviewCaseResolution = Field(
        validation_alias=AliasChoices("resolution", "resolution_code"),
        serialization_alias="resolution_code",
    )
    notes: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("metadata", "case_metadata"),
    )


class ReviewCaseReopen(BaseModel):
    notes: str | None = Field(
        default=None,
        max_length=2000,
        validation_alias=AliasChoices("notes", "reason"),
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("metadata", "case_metadata"),
    )


class ReviewCaseOut(BaseModel):
    id: int
    transaction_id: int
    decision_id: int
    organisation_id: int
    user_id: int
    status: ReviewCaseStatus = ReviewCaseStatus.open
    resolution: ReviewCaseResolution | None = Field(
        default=None,
        validation_alias=AliasChoices("resolution", "resolution_code"),
        serialization_alias="resolution_code",
    )
    notes: str | None = Field(default=None, max_length=2000)
    case_metadata: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("case_metadata", "metadata"),
        serialization_alias="metadata",
    )
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
