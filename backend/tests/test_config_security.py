"""
Regression tests for backend/app/config.py's AUTH_JWT_SECRET requirement.

AUTH_JWT_SECRET must have NO insecure hardcoded fallback: Settings() must fail to
construct (raise a validation error) when no secret is available from the environment
or .env file, and must succeed when a valid secret is explicitly configured.

Constructed directly against the Settings class with `_env_file=None` so these tests are
independent of the real backend/.env file (which legitimately has a secret configured for
local development) and of the test-session-wide AUTH_JWT_SECRET conftest.py sets for the
rest of the suite.
"""
import pytest
from pydantic import ValidationError

from app.config import Settings


def test_missing_auth_jwt_secret_fails_to_construct(monkeypatch):
    """No insecure hardcoded fallback: constructing Settings without the secret must fail."""
    monkeypatch.delenv("AUTH_JWT_SECRET", raising=False)
    with pytest.raises(ValidationError, match="AUTH_JWT_SECRET"):
        Settings(_env_file=None)


def test_too_short_auth_jwt_secret_fails_to_construct(monkeypatch):
    """A trivially weak secret (below min_length) must also fail."""
    monkeypatch.setenv("AUTH_JWT_SECRET", "short")
    with pytest.raises(ValidationError, match="AUTH_JWT_SECRET"):
        Settings(_env_file=None)


def test_valid_auth_jwt_secret_constructs_successfully(monkeypatch):
    """A properly configured secret must construct cleanly."""
    monkeypatch.setenv("AUTH_JWT_SECRET", "a-valid-test-secret-that-is-long-enough-1234")
    settings = Settings(_env_file=None)
    assert settings.AUTH_JWT_SECRET == "a-valid-test-secret-that-is-long-enough-1234"
