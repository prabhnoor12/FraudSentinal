import os
import sys
import warnings
from pathlib import Path
from unittest import mock

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

warnings.filterwarnings(
    "ignore",
    message=r"Using `httpx` with `starlette\.testclient` is deprecated; install `httpx2` instead\.",
)
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///D:/Trae_projects/FraudSentinal/backend/tests/test.db?check_same_thread=false"
os.environ["SECRET_KEY"] = "TestSecretKey123!TestSecretKey123!"
os.environ["JWT_ISSUER"] = "FraudSentinal"
os.environ["JWT_AUDIENCE"] = "fraudsentinel-api"
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "razorpay-test-webhook-secret"

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

load_dotenv(BACKEND_ROOT / ".env", override=False)

from app import app
from database import engine as app_engine
from database import get_db
from database import Base
from models import auth_models
from middleware.rate_limiting_middleware import MemoryRateLimitStore
from services.enrichment_service import reset_enrichment_lookup_cache
from services.fraud_rule_service import reset_effective_rule_cache
from services.fraud_metrics_service import fraud_metrics

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=app_engine)


@event.listens_for(app_engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        pass


@pytest.fixture(scope="session")
def db_engine():
    Base.metadata.create_all(bind=app_engine)
    yield app_engine


@pytest.fixture
def db(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def mock_mfa_service():
    """
    Mocks the MFAService to bypass actual MFA checks during tests.
    """
    with (
        mock.patch("services.mfa_service.MFAService.verify_code", return_value=True),
        mock.patch(
            "services.mfa_service.MFAService.verify_backup_code", return_value=True
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def reset_rate_limit_stores():
    for middleware in app.user_middleware:
        options = getattr(middleware, "options", {})
        store = options.get("rate_limit_store")
        if isinstance(store, MemoryRateLimitStore):
            store.reset()
    yield


@pytest.fixture(autouse=True)
def reset_service_caches():
    reset_effective_rule_cache()
    reset_enrichment_lookup_cache()
    fraud_metrics.reset()
    yield
    reset_effective_rule_cache()
    reset_enrichment_lookup_cache()
    fraud_metrics.reset()


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
