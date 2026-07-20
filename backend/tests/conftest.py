import os
import warnings
from unittest import mock

import pytest
from fastapi.testclient import TestClient

warnings.filterwarnings(
    "ignore",
    message=r"Using `httpx` with `starlette\.testclient` is deprecated; install `httpx2` instead\.",
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///./test_app.db"
os.environ["SECRET_KEY"] = "TestSecretKey123!TestSecretKey123!"
os.environ["JWT_ISSUER"] = "FraudSentinal"
os.environ["JWT_AUDIENCE"] = "fraudsentinel-api"

from app import app
from database import get_db
from database import Base
from middleware.rate_limiting_middleware import MemoryRateLimitStore
from services.enrichment_service import reset_enrichment_lookup_cache
from services.fraud_rule_service import reset_effective_rule_cache

# Use an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def db_engine():
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


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
    yield
    reset_effective_rule_cache()
    reset_enrichment_lookup_cache()


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
