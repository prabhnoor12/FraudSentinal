from __future__ import annotations

import json
from datetime import datetime, timedelta, UTC
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from auth import decode_access_token
from cruds import auth_crud
from database import SessionLocal
from services import auth_service
from utils.security_utils import fingerprint_token


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Enforce replay-safe writes for public API mutation endpoints."""

    def __init__(
        self,
        app,
        *,
        enforced_prefixes: tuple[str, ...],
        retention_days: int = 7,
    ) -> None:
        super().__init__(app)
        self.enforced_prefixes = enforced_prefixes
        self.retention_days = retention_days

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
            return await call_next(request)
        if not any(request.url.path.startswith(prefix) for prefix in self.enforced_prefixes):
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key")
        request_id = getattr(request.state, "request_id", "")
        if not idempotency_key:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": {
                        "code": "missing_idempotency_key",
                        "message": "Idempotency-Key header is required for this endpoint",
                        "details": {
                            "header": "Idempotency-Key",
                            "retention_days": self.retention_days,
                        },
                        "request_id": request_id,
                    },
                },
                headers={"X-Request-ID": request_id} if request_id else None,
            )

        body = await request.body()
        request._body = body
        request_fingerprint = fingerprint_token(
            f"{request.method}:{request.url.path}:{body.decode('utf-8', errors='ignore')}"
        )

        db = SessionLocal()
        try:
            principal = self._resolve_principal(request, db)
            if principal is None:
                return await call_next(request)

            record = auth_crud.get_idempotency_record(
                db,
                key=idempotency_key,
                method=request.method,
                path=request.url.path,
                actor_type=principal.principal_type,
                actor_id=principal.subject_id,
            )
            if record:
                if record.request_fingerprint != request_fingerprint:
                    return JSONResponse(
                        status_code=409,
                        content={
                            "success": False,
                            "error": {
                                "code": "idempotency_key_reused",
                                "message": "Idempotency key was reused with a different payload",
                                "details": {"idempotency_key": idempotency_key},
                                "request_id": request_id,
                            },
                        },
                        headers={"X-Request-ID": request_id} if request_id else None,
                    )
                headers = dict(record.response_headers or {})
                if request_id:
                    headers["X-Request-ID"] = request_id
                return JSONResponse(
                    status_code=record.response_status_code,
                    content=record.response_body,
                    headers=headers,
                )

            response = await call_next(request)
            if response.status_code >= 500:
                return response

            response_body_bytes = b""
            async for chunk in response.body_iterator:
                response_body_bytes += chunk

            response_payload = self._decode_response_body(response_body_bytes)
            response_headers = self._select_response_headers(response.headers)
            auth_crud.create_idempotency_record(
                db,
                key=idempotency_key,
                method=request.method,
                path=request.url.path,
                actor_type=principal.principal_type,
                actor_id=principal.subject_id,
                organisation_id=principal.organisation_id,
                request_fingerprint=request_fingerprint,
                response_status_code=response.status_code,
                response_body=response_payload,
                response_headers=response_headers,
                expires_at=datetime.now(UTC) + timedelta(days=self.retention_days),
            )
            return Response(
                content=response_body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        finally:
            db.close()

    def _extract_bearer_token(self, request: Request) -> str | None:
        authorization = request.headers.get("Authorization")
        if not authorization:
            return None
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        return token

    def _resolve_principal(self, request: Request, db):
        from auth_dependencies import AuthenticatedPrincipal

        bearer_token = self._extract_bearer_token(request)
        if bearer_token:
            try:
                claims = decode_access_token(bearer_token)
            except Exception:
                return None
            return AuthenticatedPrincipal(
                principal_type="user",
                subject_id=str(claims["sub"]),
                organisation_id=claims.get("org_id"),
                scopes={"*"},
            )

        api_key = request.headers.get("X-API-Key")
        if api_key:
            return AuthenticatedPrincipal(
                principal_type="api_key",
                subject_id=fingerprint_token(api_key),
                organisation_id=None,
                scopes=set(),
            )

        return None

    def _decode_response_body(self, body: bytes):
        if not body:
            return {}
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return {"raw_body": body.decode("utf-8", errors="ignore")}

    def _select_response_headers(self, headers) -> dict[str, str]:
        selected: dict[str, str] = {}
        for key in ("content-type", "location", "x-request-id"):
            value = headers.get(key)
            if value:
                selected[key] = value
        return selected


__all__ = ["IdempotencyMiddleware"]
