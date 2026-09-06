"""
B7 Authentication tests.

Tests:
  - Register: valid, duplicate email, duplicate username, weak password
  - Login: valid, wrong password (same error as unknown), unknown email (same error)
  - /auth/me: valid token, expired token, missing token, malformed token
  - Response schema: password_hash never present

Security invariant verified:
  - Same error message and status code for wrong password vs unknown email.
"""
import time
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.auth.rate_limit import SlidingWindowRateLimiter
from app.main import app
from app.db.session import Base, get_db

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def register_user(client, email="test@example.com", username="TestUser", password="securepass123"):
    """Helper: register a user and return the full response JSON."""
    return client.post("/api/auth/register", json={
        "email": email,
        "username": username,
        "password": password,
    })


# ─── REGISTER ──────────────────────────────────────────────────────────────────

def test_register_success(client):
    res = register_user(client)
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    user = data["user"]
    assert user["email"] == "test@example.com"
    assert user["username"] == "TestUser"
    assert user["level"] == 1
    assert "id" in user
    assert "created_at" in user
    assert "updated_at" in user
    # password_hash must NEVER appear in response
    assert "password_hash" not in data
    assert "password_hash" not in user
    assert "password" not in user


def test_register_duplicate_email(client):
    register_user(client)
    res = register_user(client, username="OtherUser")  # same email
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"


def test_register_duplicate_username(client):
    register_user(client)
    res = register_user(client, email="other@example.com", username="TestUser")  # same username
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "USERNAME_TAKEN"


def test_register_weak_password(client):
    res = register_user(client, password="short")
    assert res.status_code == 422


def test_register_email_normalization(client):
    """Email should be normalized to lowercase."""
    res = client.post("/api/auth/register", json={
        "email": "UPPER@EXAMPLE.COM",
        "username": "UpperUser",
        "password": "securepass123",
    })
    assert res.status_code == 201
    assert res.json()["user"]["email"] == "upper@example.com"


def test_register_missing_fields(client):
    res = client.post("/api/auth/register", json={"email": "a@b.com"})
    assert res.status_code == 422


# ─── LOGIN ─────────────────────────────────────────────────────────────────────

def test_login_success(client):
    register_user(client)
    res = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "securepass123",
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "password_hash" not in str(data)


def test_login_wrong_password(client):
    register_user(client)
    res = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "wrongpassword",
    })
    assert res.status_code == 401
    body = res.json()
    assert body["error"]["code"] == "INVALID_CREDENTIALS"
    wrong_pass_message = body["error"]["message"]

    # Unknown email must return same error (enumeration prevention)
    res2 = client.post("/api/auth/login", json={
        "email": "unknown@example.com",
        "password": "securepass123",
    })
    assert res2.status_code == 401
    assert res2.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert res2.json()["error"]["message"] == wrong_pass_message  # Same message


def test_login_unknown_email_same_error_as_wrong_password(client):
    """Security invariant: unknown email and wrong password return identical responses."""
    register_user(client)
    res_wrong_pw = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "wrong",
    })
    res_unknown = client.post("/api/auth/login", json={
        "email": "nobody@example.com",
        "password": "securepass123",
    })
    assert res_wrong_pw.status_code == res_unknown.status_code == 401
    assert (
        res_wrong_pw.json()["error"]["code"]
        == res_unknown.json()["error"]["code"]
        == "INVALID_CREDENTIALS"
    )
    assert (
        res_wrong_pw.json()["error"]["message"]
        == res_unknown.json()["error"]["message"]
    )


def test_login_email_case_insensitive(client):
    """Login email normalized to lowercase."""
    register_user(client, email="myemail@example.com")
    res = client.post("/api/auth/login", json={
        "email": "MYEMAIL@EXAMPLE.COM",
        "password": "securepass123",
    })
    assert res.status_code == 200


# ─── /AUTH/ME ──────────────────────────────────────────────────────────────────

def test_me_with_valid_token(client):
    reg = register_user(client)
    token = reg.json()["access_token"]
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "test@example.com"
    assert "password_hash" not in data


def test_me_without_token(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


def test_me_with_malformed_token(client):
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.real.token"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


def test_me_with_invalid_bearer_prefix(client):
    reg = register_user(client)
    token = reg.json()["access_token"]
    res = client.get("/api/auth/me", headers={"Authorization": f"Token {token}"})
    assert res.status_code == 401


def test_password_hash_never_in_any_response(client):
    """Scan all auth-related responses for password_hash leakage."""
    reg = register_user(client)
    token = reg.json()["access_token"]

    login_res = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "securepass123",
    })
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    for res in [reg, login_res, me_res]:
        body_str = res.text
        assert "password_hash" not in body_str, (
            f"password_hash found in response body: {body_str[:200]}"
        )
        assert "password" not in res.json().get("user", {}), (
            "password field leaked into user response"
        )


def test_form_urlencoded_payload_returns_422_without_crashing(client):
    """
    BUG-AUTH-01 regression test: Submitting application/x-www-form-urlencoded
    content causes Pydantic v2 to embed raw bytes in error['input'].
    Verify that _sanitize_validation_error_details decodes bytes so JSONResponse
    returns a clean 422 instead of crashing with a 500 TypeError.
    """
    res = client.post(
        "/api/auth/login",
        content=b"email=test%40example.com&password=secretpassword",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 422
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "AUTH_VALIDATION_FAILED"
    assert "details" in data["error"]


# ─── SlidingWindowRateLimiter Hardening (ADV-SEC-001) ──────────

def test_sliding_window_basic_rate_limiting():
    """Verify requests up to limit are allowed and requests exceeding limit are rejected."""
    limiter = SlidingWindowRateLimiter(max_keys=100)

    # Allow up to 3 requests in 10-second window
    assert limiter.is_allowed("user:1", limit=3, window_seconds=10) is True
    assert limiter.is_allowed("user:1", limit=3, window_seconds=10) is True
    assert limiter.is_allowed("user:1", limit=3, window_seconds=10) is True
    # 4th request must be rejected
    assert limiter.is_allowed("user:1", limit=3, window_seconds=10) is False

    # Different key is independent
    assert limiter.is_allowed("user:2", limit=3, window_seconds=10) is True


def test_empty_deque_cleanup_on_expiration():
    """Verify that when a key's window expires, subsequent evaluation cleans up the entry."""
    limiter = SlidingWindowRateLimiter(max_keys=100)

    limiter.is_allowed("ephemeral:1", limit=2, window_seconds=1)
    assert "ephemeral:1" in limiter._windows

    # Manually backdate timestamp to simulate expiration
    with limiter._lock:
        limiter._windows["ephemeral:1"][0] = time.monotonic() - 100.0

    # Next call with 10s window recognizes expired timestamp, prunes empty deque, and allows fresh request
    allowed = limiter.is_allowed("ephemeral:1", limit=2, window_seconds=10)
    assert allowed is True
    assert len(limiter._windows["ephemeral:1"]) == 1


def test_prune_expired_reclaims_inactive_ephemeral_keys():
    """
    Verify ADV-SEC-001 regression: Ephemeral keys that are never queried again
    are successfully reclaimed by prune_expired() instead of leaking indefinitely.
    """
    limiter = SlidingWindowRateLimiter(max_keys=5000, default_max_window=60)

    # Insert 500 ephemeral keys
    for i in range(500):
        limiter.is_allowed(f"ip:{i}", limit=5, window_seconds=60)

    assert len(limiter._windows) == 500

    # Backdate all timestamps to simulate time passing past 60s
    past = time.monotonic() - 120.0
    with limiter._lock:
        for k in limiter._windows:
            limiter._windows[k][0] = past

    # Run explicit sweep
    pruned_count = limiter.prune_expired(max_age_seconds=60)
    assert pruned_count == 500
    assert len(limiter._windows) == 0, "All expired keys and deques must be purged from memory"


def test_max_keys_capacity_cap_and_lru_eviction():
    """
    Verify ADV-SEC-001 regression: Memory is strictly bounded by max_keys cap.
    When max_keys is exceeded, oldest LRU keys are dropped.
    """
    max_cap = 20
    limiter = SlidingWindowRateLimiter(max_keys=max_cap)

    # Insert 50 keys
    for i in range(50):
        limiter.is_allowed(f"client:{i}", limit=5, window_seconds=3600)
        assert len(limiter._windows) <= max_cap, f"Windows size {len(limiter._windows)} exceeded cap {max_cap}"

    assert len(limiter._windows) == max_cap

    # The most recently added key must be present
    assert "client:49" in limiter._windows
    # The oldest key should have been evicted
    assert "client:0" not in limiter._windows


def test_concurrent_access_thread_safety():
    """Verify thread safety under concurrent requests from multiple threads."""
    limiter = SlidingWindowRateLimiter(max_keys=50)

    def worker(worker_id: int):
        for i in range(20):
            # Mix of shared keys and private keys
            limiter.is_allowed(f"shared:{i % 3}", limit=10, window_seconds=60)
            limiter.is_allowed(f"worker:{worker_id}:{i}", limit=5, window_seconds=60)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, w) for w in range(8)]
        for f in futures:
            f.result()

    assert len(limiter._windows) <= 50


def test_true_lru_eviction_access_order():
    """
    Verify strict LRU (Least Recently Used) semantics:
    capacity = 3
    touch A -> [A]
    touch B -> [A, B]
    touch C -> [A, B, C]
    touch A again -> [B, C, A] (A promoted to most recently used)
    insert D -> must evict B (least recently used), leaving [C, A, D]
    """
    limiter = SlidingWindowRateLimiter(max_keys=3)

    limiter.is_allowed("A", limit=5, window_seconds=60)
    limiter.is_allowed("B", limit=5, window_seconds=60)
    limiter.is_allowed("C", limit=5, window_seconds=60)

    # Touch A again to promote it in the LRU order
    limiter.is_allowed("A", limit=5, window_seconds=60)

    # Now insert D, which must trigger capacity eviction
    limiter.is_allowed("D", limit=5, window_seconds=60)

    # B must be the evicted key (A was accessed more recently than B)
    assert "B" not in limiter._windows, "B should have been evicted as least recently used"
    assert "A" in limiter._windows, "A must NOT be evicted because it was accessed recently"
    assert "C" in limiter._windows
    assert "D" in limiter._windows
    assert len(limiter._windows) == 3


def test_prune_expired_contract():
    """
    Verify prune_expired contract:
    - Default threshold uses default_max_window
    - Custom threshold filters by specified max_age_seconds
    - Returned integer is count of keys removed (not timestamps)
    """
    limiter = SlidingWindowRateLimiter(default_max_window=100)

    # Add key with 3 timestamps
    limiter.is_allowed("multi_ts_key", limit=10, window_seconds=60)
    limiter.is_allowed("multi_ts_key", limit=10, window_seconds=60)
    limiter.is_allowed("multi_ts_key", limit=10, window_seconds=60)

    # Backdate all timestamps to simulate expiration
    past = time.monotonic() - 150.0
    with limiter._lock:
        limiter._windows["multi_ts_key"][0] = past
        limiter._windows["multi_ts_key"][1] = past
        limiter._windows["multi_ts_key"][2] = past

    # Calling prune_expired should remove 1 key (even though it had 3 timestamps)
    pruned_keys = limiter.prune_expired()
    assert pruned_keys == 1, f"Expected 1 key removed, got {pruned_keys}"
    assert "multi_ts_key" not in limiter._windows
