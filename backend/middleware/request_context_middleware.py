from __future__ import annotations

import uuid
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from utils.request_context import set_request_id


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a stable request ID to each request and response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        set_request_id(request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


__all__ = ["RequestContextMiddleware"]
