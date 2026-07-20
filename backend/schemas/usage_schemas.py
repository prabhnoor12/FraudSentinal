from datetime import datetime
from typing import Optional

from pydantic import ConfigDict

from schemas.api_schemas import ORMStrictSchema, StrictSchema


class UsageEventBase(StrictSchema):
    user_id: int
    organisation_id: int
    event_type: str
    units: float = 1.0
    unit_type: str = "request"
    description: Optional[str] = None
    status: str = "recorded"


class UsageEventCreate(UsageEventBase):
    pass


class UsageEventOut(ORMStrictSchema):
    id: int
    recorded_at: datetime
    billed_at: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class UsageSummaryBase(StrictSchema):
    user_id: int
    organisation_id: int
    period_start: datetime
    period_end: datetime
    total_units: float = 0.0
    currency: str = "USD"


class UsageSummaryCreate(UsageSummaryBase):
    pass


class UsageSummaryOut(ORMStrictSchema):
    id: int
    created_at: datetime

    model_config = ConfigDict(extra="forbid", from_attributes=True)
