"""
Global pytest configuration for GameForge AI backend tests.

Sets AUTH_JWT_SECRET before any app module is imported so that the Settings
object can load it. This prevents "missing required secret" startup errors
during testing.

The test secret is intentionally a long, clearly test-only value.
It is NEVER used outside of the test suite.
"""
import os

# Must be set BEFORE any app imports so pydantic-settings picks it up.
os.environ.setdefault(
    "AUTH_JWT_SECRET",
    "test-only-secret-do-not-use-outside-tests-gameforge-ai-b7"
)
os.environ.setdefault(
    "DATABASE_URL",
    "sqlite:///:memory:"
)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.auth.rate_limit import rate_limiter
from app.db.session import Base, get_db
from app.main import app

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    rate_limiter.clear()
    yield
    rate_limiter.clear()


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite session with table creation and teardown."""
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.pop(get_db, None)

