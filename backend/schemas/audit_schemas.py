from typing import Optional
from pydantic import BaseModel


class AuditContext(BaseModel):
    user_id: Optional[int] = None
    organisation_id: int
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
