from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UserBase(BaseModel):
    email: str
    full_name: Optional[str] = None
    is_active: bool = True


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None


class UserOut(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
