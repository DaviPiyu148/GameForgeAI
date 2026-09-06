"""
Unit and integration tests for Game DNA preference reset and onboarding rate limiting (ADV-SEC-005).

Tests:
1. check_preference_mutate_rate unit tests:
   - Allows 20 mutations per hour.
   - Rejects 21st request within window.
   - User isolation: limits are partitioned by user_id.
2. Combined endpoint rate limiting integration tests:
   - 10 onboards + 10 resets = 20 allowed combined operations.
   - 21st operation (onboard or reset) rejected with HTTP 429 RATE_LIMITED.
   - Structured JSON error format validation (code, message, request_id).
   - User isolation via API: distinct authenticated user not blocked.
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.rate_limit import check_preference_mutate_rate, rate_limiter
from app.auth.tokens import create_access_token
from app.models.user import User


def test_check_preference_mutate_rate_unit():
    """Unit test for rate limiter helper function."""
    rate_limiter.clear()
    user_a = "user-uuid-aaa"
    user_b = "user-uuid-bbb"

    # User A: exactly 20 allowed
    for i in range(20):
        assert check_preference_mutate_rate(user_a) is True, f"Request {i+1} should be allowed"

    # 21st request rejected
    assert check_preference_mutate_rate(user_a) is False, "21st request must be rejected"

    # User B is completely independent
    assert check_preference_mutate_rate(user_b) is True, "User B must not be affected by User A"


def test_combined_preference_mutation_rate_limiting_api(client: TestClient, db_session: Session):
    """
    Integration test asserting combined 20 ops/hour threshold across reset and onboard.
    10 resets + 10 onboards = 20 allowed operations.
    The 21st operation must be rejected with 429 RATE_LIMITED.
    """
    rate_limiter.clear()

    # Create user 1
    user1 = User(
        id=str(uuid.uuid4()),
        email="pref_limit_user1@example.com",
        username="pref_limit_user1",
        password_hash="fakehash",
        level=1,
    )
    # Create user 2
    user2 = User(
        id=str(uuid.uuid4()),
        email="pref_limit_user2@example.com",
        username="pref_limit_user2",
        password_hash="fakehash",
        level=1,
    )
    db_session.add_all([user1, user2])
    db_session.commit()

    token1 = create_access_token(user1.id)
    headers1 = {"Authorization": f"Bearer {token1}"}

    token2 = create_access_token(user2.id)
    headers2 = {"Authorization": f"Bearer {token2}"}

    onboard_payload = {
        "genres": ["RPG", "Action"],
        "enjoyments": ["Story"],
        "avoidances": ["Horror"],
    }

    # 1. User 1 performs 10 onboard requests
    for i in range(10):
        res = client.post("/api/profile/preferences/onboard", json=onboard_payload, headers=headers1)
        assert res.status_code == 200, f"Onboard {i+1} failed: {res.text}"

    # 2. User 1 performs 10 reset requests (total: 20 operations)
    for i in range(10):
        res = client.post("/api/profile/preferences/reset", headers=headers1)
        assert res.status_code == 200, f"Reset {i+1} failed: {res.text}"

    # 3. 21st operation: POST /api/profile/preferences/onboard -> rejected with 429
    res_21_onboard = client.post("/api/profile/preferences/onboard", json=onboard_payload, headers=headers1)
    assert res_21_onboard.status_code == 429
    data_onboard = res_21_onboard.json()
    assert data_onboard["error"]["code"] == "RATE_LIMITED"
    assert "Preference mutation rate limit exceeded" in data_onboard["error"]["message"]
    assert "request_id" in data_onboard["error"]

    # 4. 22nd operation: POST /api/profile/preferences/reset -> also rejected with 429
    res_22_reset = client.post("/api/profile/preferences/reset", headers=headers1)
    assert res_22_reset.status_code == 429
    data_reset = res_22_reset.json()
    assert data_reset["error"]["code"] == "RATE_LIMITED"
    assert "Preference mutation rate limit exceeded" in data_reset["error"]["message"]

    # 5. User 2 is independent and must succeed
    res_user2 = client.post("/api/profile/preferences/onboard", json=onboard_payload, headers=headers2)
    assert res_user2.status_code == 200
