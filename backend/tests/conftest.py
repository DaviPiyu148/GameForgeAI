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
from app.auth.rate_limit import rate_limiter

@pytest.fixture(autouse=True)
def reset_rate_limiter():
    rate_limiter.clear()
    yield
    rate_limiter.clear()
