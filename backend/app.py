from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

from auth import SECRET_KEY
from database import SessionLocal
from middleware.ip_limiting_middleware import IPLimitMiddleware
from middleware.idempotency_middleware import IdempotencyMiddleware
from middleware.logging_middleware import LoggingMiddleware
from middleware.rate_limiting_middleware import RateLimitMiddleware, RateLimitOverride
from middleware.request_context_middleware import RequestContextMiddleware
from middleware.security_headers_middleware import SecurityHeadersMiddleware
from redis import build_rate_limit_store
from routes.auth_routes import router as auth_router
from routes.audit_routes import router as audit_router
from routes.billing_routes import router as billing_router
from routes.decision_routes import router as decision_router
from routes.enrichment_routes import router as enrichment_router
from routes.fraud_check_routes import router as fraud_check_router
from routes.fraud_rule_routes import router as fraud_rule_router
from routes.limit_tracking_routes import router as limit_tracking_router
from routes.mfa_routes import router as mfa_router
from routes.organisation_routes import router as organisation_router
from routes.review_case_routes import router as review_case_router
from routes.risk_signal_routes import router as risk_signal_router
from routes.session_routes import router as session_router
from routes.settings_routes import router as settings_router
from routes.transaction_routes import router as transaction_router
from routes.usage_routes import router as usage_router
from routes.user_routes import router as user_router
from routes.user_tracking_routes import router as user_tracking_router
from routes.webhook_routes import router as webhook_router
from services import fraud_rule_service
from services.fraud_metrics_service import fraud_metrics
from services.mfa_service import get_mfa_cipher
from utils.security_utils import validate_production_hardening, validate_secret_key
from utils.exception_handling_utils import (
    AppException,
    handle_app_exception,
    handle_http_exception,
    handle_unexpected_exception,
    handle_validation_exception,
)
import models  # noqa: F401


def is_testing() -> bool:
    return os.getenv("TESTING", "").lower() in {"1", "true", "yes"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if is_testing():
        yield
        return

    # 1. Validate Security Configuration
    try:
        validate_secret_key(SECRET_KEY)
        validate_production_hardening()
        get_mfa_cipher()
    except ValueError as e:
        logger.critical(f"CRITICAL SECURITY CONFIGURATION ERROR: {str(e)}")
        logger.critical(
            "Application startup aborted due to invalid security configuration."
        )
        sys.exit(1)

    db = SessionLocal()
    try:
        fraud_rule_service.seed_default_fraud_rules(db)
    finally:
        db.close()

    yield


app = FastAPI(
    title="FraudSentinal Public API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(LoggingMiddleware, exclude_paths={"/health"})
if not is_testing():
    app.add_middleware(
        RateLimitMiddleware,
        calls=120,
        window_seconds=60,
        exempt_paths={"/health"},
        rate_limit_store=build_rate_limit_store("fraudsentinel:rate_limit"),
        endpoint_overrides=(
            RateLimitOverride(
                path="/api/v1/auth/login",
                calls=10,
                window_seconds=60,
                block_duration_seconds=300,
            ),
            RateLimitOverride(
                path="/api/v1/auth/password-reset/request",
                calls=5,
                window_seconds=300,
                block_duration_seconds=600,
            ),
            RateLimitOverride(
                path="/api/v1/auth/password-reset/confirm",
                calls=8,
                window_seconds=300,
                block_duration_seconds=600,
            ),
            RateLimitOverride(
                path="/api/v1/check-fraud",
                calls=30,
                window_seconds=60,
                block_duration_seconds=180,
            ),
            RateLimitOverride(
                path="/api/v1/enrichment/seed",
                calls=3,
                window_seconds=300,
                block_duration_seconds=900,
            ),
            RateLimitOverride(
                path="/api/v1/enrichment/signals/test",
                calls=20,
                window_seconds=60,
                block_duration_seconds=180,
            ),
        ),
    )
    app.add_middleware(
        IPLimitMiddleware,
        calls=300,
        window_seconds=60,
        exempt_paths={"/health"},
        rate_limit_store=build_rate_limit_store("fraudsentinel:ip_limit"),
    )
app.add_middleware(
    IdempotencyMiddleware,
    enforced_prefixes=(
        "/api/v1/check-fraud",
        "/api/v1/transactions",
        "/api/v1/usage",
        "/api/v1/user-tracking",
        "/api/v1/limit-tracking",
        "/api/v1/billing",
    ),
)
app.add_middleware(RequestContextMiddleware)

app.add_exception_handler(AppException, handle_app_exception)
app.add_exception_handler(HTTPException, handle_http_exception)
app.add_exception_handler(RequestValidationError, handle_validation_exception)
app.add_exception_handler(Exception, handle_unexpected_exception)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth_router)
api_v1.include_router(audit_router)
api_v1.include_router(mfa_router)
api_v1.include_router(user_router)
api_v1.include_router(organisation_router)
api_v1.include_router(session_router)
api_v1.include_router(settings_router)
api_v1.include_router(usage_router)
api_v1.include_router(limit_tracking_router)
api_v1.include_router(user_tracking_router)
api_v1.include_router(transaction_router)
api_v1.include_router(decision_router)
api_v1.include_router(enrichment_router)
api_v1.include_router(fraud_check_router)
api_v1.include_router(fraud_rule_router)
api_v1.include_router(risk_signal_router)
api_v1.include_router(review_case_router)
api_v1.include_router(billing_router)
api_v1.include_router(webhook_router)
app.include_router(api_v1)


import logging
import sys

logger = logging.getLogger("fraudsentinel.app")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/health")
def v1_health_check() -> dict[str, str]:
    return {"status": "ok", "version": "v1"}


@app.get("/metrics")
def metrics() -> dict[str, object]:
    return {
        "status": "ok",
        "fraud_detection": fraud_metrics.snapshot(),
    }


@app.get("/api/v1/metrics")
def v1_metrics() -> dict[str, object]:
    return metrics()
