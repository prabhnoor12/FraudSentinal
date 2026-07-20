from datetime import datetime
from typing import Optional

from pydantic import ConfigDict

from schemas.api_schemas import ORMStrictSchema, StrictSchema


class UsageLimitBase(StrictSchema):
    user_id: Optional[int] = None
    organisation_id: Optional[int] = None
    limit_type: str
    limit_value: float = 0.0
    period: str = "monthly"
    is_active: str = "true"


class UsageLimitCreate(UsageLimitBase):
    pass


class UsageLimitOut(ORMStrictSchema):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class LimitUsageRecordBase(StrictSchema):
    usage_limit_id: int
    current_usage: float = 0.0
    period_start: datetime
    period_end: datetime


class LimitUsageRecordCreate(LimitUsageRecordBase):
    pass


class LimitUsageRecordOut(ORMStrictSchema):
    id: int
    updated_at: datetime

    model_config = ConfigDict(extra="forbid", from_attributes=True)
