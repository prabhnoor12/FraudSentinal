from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ORMStrictSchema(StrictSchema):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class APIErrorDetail(StrictSchema):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class APIErrorResponse(StrictSchema):
    success: bool = False
    error: APIErrorDetail


class PageMeta(StrictSchema):
    total: int
    limit: int
    offset: int
    next: Optional[str] = None
    previous: Optional[str] = None


T = TypeVar("T")


class PaginatedResponse(StrictSchema, Generic[T]):
    items: list[T]
    pagination: PageMeta
