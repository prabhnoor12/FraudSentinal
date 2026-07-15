from __future__ import annotations

import logging
import traceback
from typing import Any, Optional

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger("fraudsentinel.exceptions")


class AppException(Exception):
    """Base custom exception for application errors."""

    def __init__(self, message: str, *, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ValidationError(AppException):
    """Raised when request data is invalid."""

    def __init__(self, message: str = "Validation failed", *, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST, details=details)


class NotFoundError(AppException):
    """Raised when a resource cannot be found."""

    def __init__(self, message: str = "Resource not found", *, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND, details=details)


class UnauthorizedError(AppException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Unauthorized", *, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED, details=details)


class ForbiddenError(AppException):
    """Raised when access is denied."""

    def __init__(self, message: str = "Forbidden", *, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN, details=details)


class ConflictError(AppException):
    """Raised when a resource conflicts with an existing one."""

    def __init__(self, message: str = "Conflict", *, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=status.HTTP_409_CONFLICT, details=details)


class ExternalServiceError(AppException):
    """Raised when an upstream service fails."""

    def __init__(self, message: str = "External service error", *, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message, status_code=status.HTTP_502_BAD_GATEWAY, details=details)


async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
    """Convert application exceptions into JSON responses."""
    payload = {
        "success": False,
        "error": exc.message,
        "status_code": exc.status_code,
        "details": exc.details,
    }
    logger.warning("application_exception", extra={"path": request.url.path, "status_code": exc.status_code, "error": exc.message, "details": exc.details})
    return JSONResponse(status_code=exc.status_code, content=payload)


async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    """Convert FastAPI HTTP exceptions into JSON responses."""
    payload = {
        "success": False,
        "error": exc.detail if isinstance(exc.detail, str) else "Request failed",
        "status_code": exc.status_code,
        "details": {},
    }
    logger.warning("http_exception", extra={"path": request.url.path, "status_code": exc.status_code, "error": payload["error"]})
    return JSONResponse(status_code=exc.status_code, content=payload)


async def handle_validation_exception(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Convert request validation errors into a structured JSON response."""
    payload = {
        "success": False,
        "error": "Validation failed",
        "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "details": {
            "errors": exc.errors(),
        },
    }
    logger.warning("validation_exception", extra={"path": request.url.path, "errors": exc.errors()})
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload)


async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
    """Convert unexpected exceptions into a safe JSON response."""
    payload = {
        "success": False,
        "error": "Internal server error",
        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "details": {},
    }
    logger.exception("unexpected_exception", extra={"path": request.url.path, "error": str(exc)})
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)


def format_exception_for_logging(exc: Exception) -> str:
    """Return a readable traceback string for debugging logs."""
    return "\n".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


__all__ = [
    "AppException",
    "ValidationError",
    "NotFoundError",
    "UnauthorizedError",
    "ForbiddenError",
    "ConflictError",
    "ExternalServiceError",
    "handle_app_exception",
    "handle_http_exception",
    "handle_validation_exception",
    "handle_unexpected_exception",
    "format_exception_for_logging",
]
