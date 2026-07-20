from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
import time
from typing import Callable, Deque, DefaultDict, Optional, Set, Tuple

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp
from utils.security_utils import get_request_client_ip


class RateLimitMiddleware(BaseHTTPMiddleware):
    """A memory-based rate limiting middleware for FastAPI/Starlette.

    It tracks requests by client identifier (IP address by default), enforces a
    sliding-window limit, and returns standard rate-limit headers plus a 429
    response when the threshold is exceeded.

    The X-RateLimit-Reset header is computed based on the oldest request in the
    current window so the client knows when the next slot becomes available.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        calls: int = 60,
        window_seconds: int = 60,
        block_duration_seconds: int = 60,
        exempt_paths: Optional[Set[str]] = None,
        exempt_prefixes: Optional[Tuple[str, ...]] = None,
        key_func: Optional[Callable[[Request], str]] = None,
        message: str = "Too many requests",
    ) -> None:
        super().__init__(app)
        self.calls = max(1, calls)
        self.window_seconds = max(1, window_seconds)
        self.block_duration_seconds = max(1, block_duration_seconds)
        self.exempt_paths = set(exempt_paths or ())
        self.exempt_prefixes = exempt_prefixes or ()
        self.key_func = key_func or self._default_key
        self.message = message
        self._request_history: DefaultDict[str, Deque[float]] = defaultdict(deque)
        self._blocked_until: DefaultDict[str, float] = defaultdict(float)
        self._lock = Lock()

    async def dispatch(self, request: Request, call_next):
        if self._should_skip(request):
            return await call_next(request)

        now = time.monotonic()
        client_key = self.key_func(request)

        with self._lock:
            self._prune_blocked(now)
            self._prune_history(client_key, now)

            if self._is_blocked(client_key, now):
                retry_after = max(1, int(self._blocked_until[client_key] - now))
                reset_timestamp = int(time.time() + retry_after)
                headers = {
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.calls),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_timestamp),
                }
                return JSONResponse(
                    status_code=429,
                    content={"detail": self.message, "retry_after": retry_after},
                    headers=headers,
                )

            history = self._request_history[client_key]
            history.append(now)
            remaining = max(0, self.calls - len(history))

            if len(history) > self.calls:
                self._blocked_until[client_key] = now + self.block_duration_seconds
                retry_after = self.block_duration_seconds
                reset_timestamp = int(time.time() + retry_after)
                headers = {
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.calls),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_timestamp),
                }
                return JSONResponse(
                    status_code=429,
                    content={"detail": self.message, "retry_after": retry_after},
                    headers=headers,
                )

            reset_timestamp = self._compute_reset_timestamp(history, now)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.calls)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_timestamp)
        return response

    def _compute_reset_timestamp(self, history: Deque[float], now: float) -> int:
        if not history:
            return int(time.time() + self.window_seconds)

        oldest = history[0]
        seconds_left = max(0.0, self.window_seconds - (now - oldest))
        return int(time.time() + seconds_left)

    def _should_skip(self, request: Request) -> bool:
        path = request.url.path
        if path in self.exempt_paths:
            return True
        return any(path.startswith(prefix) for prefix in self.exempt_prefixes)

    def _default_key(self, request: Request) -> str:
        return get_request_client_ip(request)

    def _prune_history(self, client_key: str, now: float) -> None:
        history = self._request_history.get(client_key)
        if history is None:
            return

        cutoff = now - self.window_seconds
        while history and history[0] <= cutoff:
            history.popleft()

        if not history:
            self._request_history.pop(client_key, None)

    def _prune_blocked(self, now: float) -> None:
        expired_keys = [
            key
            for key, blocked_until in self._blocked_until.items()
            if blocked_until <= now
        ]
        for key in expired_keys:
            self._blocked_until.pop(key, None)

    def _is_blocked(self, client_key: str, now: float) -> bool:
        blocked_until = self._blocked_until.get(client_key)
        if blocked_until is None:
            return False
        if blocked_until <= now:
            self._blocked_until.pop(client_key, None)
            return False
        return True


__all__ = ["RateLimitMiddleware"]
