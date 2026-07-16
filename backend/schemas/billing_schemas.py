from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BillingPlanBase(BaseModel):
    organisation_id: int
    name: str
    price_per_unit: float = 0.0
    currency: str = "USD"
    billing_interval: str = "monthly"
    is_active: bool = True


class BillingPlanCreate(BillingPlanBase):
    pass


class BillingPlanOut(BillingPlanBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BillingRecordBase(BaseModel):
    user_id: int
    organisation_id: int
    usage_event_id: Optional[int] = None
    amount: float = 0.0
    currency: str = "USD"
    status: str = "pending"
    invoice_id: Optional[str] = None
    description: Optional[str] = None
    billing_period_start: datetime
    billing_period_end: datetime


class BillingRecordCreate(BillingRecordBase):
    pass


class BillingRecordOut(BillingRecordBase):
    id: int
    created_at: datetime
    billed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
