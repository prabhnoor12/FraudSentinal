from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OrganisationBase(BaseModel):
    name: str
    slug: Optional[str] = None
    is_active: bool = True


class OrganisationCreate(OrganisationBase):
    pass


class OrganisationUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    is_active: Optional[bool] = None


class OrganisationOut(OrganisationBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
