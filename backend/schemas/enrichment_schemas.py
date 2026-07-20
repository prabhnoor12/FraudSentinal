from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import ConfigDict

from schemas.api_schemas import PaginatedResponse, StrictSchema


class IPGeolocationListItem(StrictSchema):
    id: int
    ip_start: str
    ip_end: str
    country_code: str
    region: Optional[str] = None
    city: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class IPGeolocationListResponse(PaginatedResponse[IPGeolocationListItem]):
    pass


class BINLookupListItem(StrictSchema):
    id: int
    bin_number: str
    card_brand: Optional[str] = None
    card_type: Optional[str] = None
    issuing_bank: Optional[str] = None
    issuing_country_code: Optional[str] = None
    is_prepaid: bool
    risk_score: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class BINLookupListResponse(PaginatedResponse[BINLookupListItem]):
    pass
