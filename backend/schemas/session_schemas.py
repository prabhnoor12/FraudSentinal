from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SessionCreate(BaseModel):
    user_id: int
    session_token: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str = "active"


class SessionOut(SessionCreate):
    id: int
    started_at: datetime
    ended_at: Optional[datetime] = None

    class Config:
        from_attributes = True
