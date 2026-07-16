from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OrganisationSettingsBase(BaseModel):
    currency: str = "USD"
    timezone: str = "UTC"
    enable_billing: bool = True
    enable_usage_tracking: bool = True
    notification_email: Optional[str] = None
    notes: Optional[str] = None


class OrganisationSettingsCreate(OrganisationSettingsBase):
    organisation_id: int


class OrganisationSettingsUpdate(BaseModel):
    currency: Optional[str] = None
    timezone: Optional[str] = None
    enable_billing: Optional[bool] = None
    enable_usage_tracking: Optional[bool] = None
    notification_email: Optional[str] = None
    notes: Optional[str] = None


class OrganisationSettingsOut(OrganisationSettingsBase):
    id: int
    organisation_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
