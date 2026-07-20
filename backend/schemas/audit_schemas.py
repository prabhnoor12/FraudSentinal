from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from schemas.api_schemas import PaginatedResponse


class AuditContext(BaseModel):
    user_id: Optional[int] = None
    organisation_id: int
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class AuditLogOut(BaseModel):
    id: int
    organisation_id: Optional[int] = None
    user_id: Optional[int] = None
    event_type: str
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    old_value: Optional[dict[str, Any]] = None
    new_value: Optional[dict[str, Any]] = None
    details: Optional[dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(PaginatedResponse[AuditLogOut]):
    pass
