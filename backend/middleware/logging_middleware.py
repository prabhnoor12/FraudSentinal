from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional, Set

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp
from utils.security_utils import get_request_client_ip


class LoggingMiddleware(BaseHTTPMiddleware):
    """Structured request/response logging middleware for FastAPI apps.

    Logs request start, completion, and failures in a consistent format so
    downstream handlers or log aggregators can process them reliably.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        logger: Optional[logging.Logger] = None,
        log_body: bool = False,
        log_headers: bool = False,
        exclude_paths: Optional[Set[str]] = None,
        exclude_prefixes: Optional[tuple[str, ...]] = None,
    ) -> None:
        super().__init__(app)
        self.logger = logger or logging.getLogger("fraudsentinel.api")
        self.log_body = log_body
        self.log_headers = log_headers
        self.exclude_paths = set(exclude_paths or ())
        self.exclude_prefixes = exclude_prefixes or ()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Any]
    ) -> Response:
        start_time = time.perf_counter()
        request_id = self._get_request_id(request)

        if self._should_skip(request):
            return await call_next(request)

        self.logger.info(
            "request_started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("user-agent"),
                "headers": self._sanitize_headers(request.headers)
                if self.log_headers
                else None,
            },
        )

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            self.logger.info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "client_ip": self._get_client_ip(request),
                    "response_headers": self._sanitize_headers(dict(response.headers))
                    if self.log_headers
                    else None,
                },
            )
            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            self.logger.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "client_ip": self._get_client_ip(request),
                    "duration_ms": duration_ms,
                    "error": str(exc),
                },
            )
            raise

    def _should_skip(self, request: Request) -> bool:
        path = request.url.path
        if path in self.exclude_paths:
            return True
        return any(path.startswith(prefix) for prefix in self.exclude_prefixes)

    def _get_request_id(self, request: Request) -> str:
        request_id = request.headers.get("x-request-id") or request.headers.get(
            "x-correlation-id"
        )
        if request_id:
            return request_id
        return f"req-{int(time.time() * 1000000)}"

    def _get_client_ip(self, request: Request) -> str:
        return get_request_client_ip(request)

    def _sanitize_headers(self, headers: Any) -> dict[str, str]:
        if isinstance(headers, dict):
            items = headers.items()
        else:
            items = headers

        result: dict[str, str] = {}
        for key, value in items:
            if not isinstance(value, str):
                value = str(value)
            result[key.lower()] = value
        return result


__all__ = ["LoggingMiddleware"]
