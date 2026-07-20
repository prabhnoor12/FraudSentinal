from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict, deque
from threading import Lock
import time
from typing import Callable, Deque, DefaultDict, Optional, Protocol, Set, Tuple

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp
from utils.security_utils import get_request_client_ip


@dataclass
class RateLimitDecision:
    allowed: bool
    remaining: int
    reset_timestamp: int
    retry_after: int = 0


@dataclass(frozen=True)
class RateLimitOverride:
    path: str
    calls: int
    window_seconds: int
    block_duration_seconds: int
    match_mode: str = "exact"


class RateLimitStore(Protocol):
    async def register_request(
        self,
        *,
        key: str,
        calls: int,
        window_seconds: int,
        block_duration_seconds: int,
    ) -> RateLimitDecision: ...


class MemoryRateLimitStore:
    """Fallback in-process rate limit store for tests and local development."""

    def __init__(self) -> None:
        self._request_history: DefaultDict[str, Deque[float]] = defaultdict(deque)
        self._blocked_until: DefaultDict[str, float] = defaultdict(float)
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._request_history.clear()
            self._blocked_until.clear()

    async def register_request(
        self,
        *,
        key: str,
        calls: int,
        window_seconds: int,
        block_duration_seconds: int,
    ) -> RateLimitDecision:
        now = time.monotonic()
        with self._lock:
            self._prune_blocked(now)
            self._prune_history(key, now, window_seconds)

            if self._is_blocked(key, now):
                retry_after = max(1, int(self._blocked_until[key] - now))
                return RateLimitDecision(
                    allowed=False,
                    remaining=0,
                    reset_timestamp=int(time.time() + retry_after),
                    retry_after=retry_after,
                )

            history = self._request_history[key]
            history.append(now)
            remaining = max(0, calls - len(history))

            if len(history) > calls:
                self._blocked_until[key] = now + block_duration_seconds
                retry_after = block_duration_seconds
                return RateLimitDecision(
                    allowed=False,
                    remaining=0,
                    reset_timestamp=int(time.time() + retry_after),
                    retry_after=retry_after,
                )

            return RateLimitDecision(
                allowed=True,
                remaining=remaining,
                reset_timestamp=self._compute_reset_timestamp(history, now, window_seconds),
            )

    def _compute_reset_timestamp(
        self, history: Deque[float], now: float, window_seconds: int
    ) -> int:
        if not history:
            return int(time.time() + window_seconds)

        oldest = history[0]
        seconds_left = max(0.0, window_seconds - (now - oldest))
        return int(time.time() + seconds_left)

    def _prune_history(self, client_key: str, now: float, window_seconds: int) -> None:
        history = self._request_history.get(client_key)
        if history is None:
            return

        cutoff = now - window_seconds
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


class RateLimitMiddleware(BaseHTTPMiddleware):
    """A rate limiting middleware for FastAPI/Starlette.

    It tracks requests by client identifier (IP address by default), enforces a
    limit, and returns standard rate-limit headers plus a 429 response when the
    threshold is exceeded. It can use a shared Redis backend or an in-memory
    fallback store.
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
        rate_limit_store: Optional[RateLimitStore] = None,
        endpoint_overrides: Optional[tuple[RateLimitOverride, ...]] = None,
    ) -> None:
        super().__init__(app)
        self.calls = max(1, calls)
        self.window_seconds = max(1, window_seconds)
        self.block_duration_seconds = max(1, block_duration_seconds)
        self.exempt_paths = set(exempt_paths or ())
        self.exempt_prefixes = exempt_prefixes or ()
        self.key_func = key_func or self._default_key
        self.message = message
        self.rate_limit_store = rate_limit_store or MemoryRateLimitStore()
        self.endpoint_overrides = endpoint_overrides or ()

    async def dispatch(self, request: Request, call_next):
        if self._should_skip(request):
            return await call_next(request)

        limit_config = self._resolve_limit_config(request)
        client_key = self.key_func(request)
        decision = await self.rate_limit_store.register_request(
            key=client_key,
            calls=limit_config.calls,
            window_seconds=limit_config.window_seconds,
            block_duration_seconds=limit_config.block_duration_seconds,
        )
        if not decision.allowed:
            headers = {
                "Retry-After": str(decision.retry_after),
                "X-RateLimit-Limit": str(limit_config.calls),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(decision.reset_timestamp),
            }
            return JSONResponse(
                status_code=429,
                content={"detail": self.message, "retry_after": decision.retry_after},
                headers=headers,
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit_config.calls)
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
        response.headers["X-RateLimit-Reset"] = str(decision.reset_timestamp)
        return response

    def _should_skip(self, request: Request) -> bool:
        path = request.url.path
        if path in self.exempt_paths:
            return True
        return any(path.startswith(prefix) for prefix in self.exempt_prefixes)

    def _default_key(self, request: Request) -> str:
        return get_request_client_ip(request)

    def _resolve_limit_config(self, request: Request) -> RateLimitOverride:
        path = request.url.path
        for override in self.endpoint_overrides:
            if override.match_mode == "prefix" and path.startswith(override.path):
                return override
            if override.match_mode == "exact" and path == override.path:
                return override

        return RateLimitOverride(
            path="*",
            calls=self.calls,
            window_seconds=self.window_seconds,
            block_duration_seconds=self.block_duration_seconds,
        )


__all__ = [
    "RateLimitDecision",
    "RateLimitOverride",
    "RateLimitStore",
    "MemoryRateLimitStore",
    "RateLimitMiddleware",
]
