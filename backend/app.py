from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

from auth import SECRET_KEY
from database import SessionLocal
from middleware.ip_limiting_middleware import IPLimitMiddleware
from middleware.logging_middleware import LoggingMiddleware
from middleware.rate_limiting_middleware import RateLimitMiddleware
from routes.auth_routes import router as auth_router
from routes.audit_routes import router as audit_router
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
from services import fraud_rule_service
from utils.security_utils import validate_secret_key
from utils.exception_handling_utils import (
    AppException,
    handle_app_exception,
    handle_http_exception,
    handle_unexpected_exception,
    handle_validation_exception,
)
import models  # noqa: F401


app = FastAPI(title="FraudSentinal Backend", version="0.1.0")

app.add_middleware(LoggingMiddleware, exclude_paths={"/health"})
app.add_middleware(RateLimitMiddleware, calls=120, window_seconds=60, exempt_paths={"/health"})
app.add_middleware(IPLimitMiddleware, calls=300, window_seconds=60, exempt_paths={"/health"})

app.add_exception_handler(AppException, handle_app_exception)
app.add_exception_handler(HTTPException, handle_http_exception)
app.add_exception_handler(RequestValidationError, handle_validation_exception)
app.add_exception_handler(Exception, handle_unexpected_exception)

app.include_router(auth_router)
app.include_router(audit_router)
app.include_router(mfa_router)
app.include_router(user_router)
app.include_router(organisation_router)
app.include_router(session_router)
app.include_router(settings_router)
app.include_router(usage_router)
app.include_router(limit_tracking_router)
app.include_router(user_tracking_router)
app.include_router(transaction_router)
app.include_router(decision_router)
app.include_router(enrichment_router)
app.include_router(fraud_check_router)
app.include_router(fraud_rule_router)
app.include_router(risk_signal_router)
app.include_router(review_case_router)


import logging
import sys

logger = logging.getLogger("fraudsentinel.app")


@app.on_event("startup")
def on_startup() -> None:
    # 1. Validate Security Configuration
    try:
        validate_secret_key(SECRET_KEY)
    except ValueError as e:
        logger.critical(f"CRITICAL SECURITY CONFIGURATION ERROR: {str(e)}")
        logger.critical("Application startup aborted due to missing or weak SECRET_KEY.")
        sys.exit(1)

    db = SessionLocal()
    try:
        fraud_rule_service.seed_default_fraud_rules(db)
    finally:
        db.close()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
