from __future__ import annotations

from typing import Callable, Optional, Set, Tuple

from fastapi import Request
from middleware.rate_limiting_middleware import RateLimitMiddleware
from starlette.types import ASGIApp


class IPLimitMiddleware(RateLimitMiddleware):
    """Memory-based IP rate limiting middleware for FastAPI/Starlette.

    This middleware reuses the shared rate limiting implementation while
    preserving an IP-specific default error message and behavior.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        calls: int = 100,
        window_seconds: int = 60,
        block_duration_seconds: int = 300,
        exempt_paths: Optional[Set[str]] = None,
        exempt_prefixes: Optional[Tuple[str, ...]] = None,
        key_func: Optional[Callable[[Request], str]] = None,
        message: str = "Too many requests from this IP",
    ) -> None:
        super().__init__(
            app,
            calls=calls,
            window_seconds=window_seconds,
            block_duration_seconds=block_duration_seconds,
            exempt_paths=exempt_paths,
            exempt_prefixes=exempt_prefixes,
            key_func=key_func,
            message=message,
        )


__all__ = ["IPLimitMiddleware"]
