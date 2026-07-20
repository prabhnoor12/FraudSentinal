from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from fastapi import Request

from schemas.api_schemas import PageMeta


def build_page_meta(
    *,
    request: Request,
    total: int,
    limit: int,
    offset: int,
) -> PageMeta:
    next_offset = offset + limit
    previous_offset = max(offset - limit, 0)

    return PageMeta(
        total=total,
        limit=limit,
        offset=offset,
        next=_build_page_url(request, limit=limit, offset=next_offset)
        if next_offset < total
        else None,
        previous=_build_page_url(request, limit=limit, offset=previous_offset)
        if offset > 0
        else None,
    )


def build_paginated_payload(
    *,
    request: Request,
    items: list[Any],
    total: int,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    return {
        "items": items,
        "pagination": build_page_meta(
            request=request,
            total=total,
            limit=limit,
            offset=offset,
        ),
    }


def normalize_limit(limit: int, *, default: int = 50, maximum: int = 200) -> int:
    if limit <= 0:
        return default
    return min(limit, maximum)


def normalize_offset(offset: int) -> int:
    return max(0, offset)


def normalize_sort_dir(sort_dir: str | None) -> str:
    if (sort_dir or "").lower() == "asc":
        return "asc"
    return "desc"


def _build_page_url(request: Request, *, limit: int, offset: int) -> str:
    params = dict(request.query_params)
    params["limit"] = str(limit)
    params["offset"] = str(offset)
    return f"{request.url.path}?{urlencode(params)}"
