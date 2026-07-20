from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply baseline security headers to all HTTP responses."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        csp: str | None = None,
        hsts_max_age: int = 31536000,
    ) -> None:
        super().__init__(app)
        self.csp = csp or (
            "default-src 'self'; frame-ancestors 'none'; object-src 'none'; "
            "base-uri 'self'; form-action 'self'"
        )
        self.hsts_max_age = max(0, hsts_max_age)

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", self.csp)
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if self.hsts_max_age > 0:
            response.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={self.hsts_max_age}; includeSubDomains",
            )
        return response


__all__ = ["SecurityHeadersMiddleware"]
