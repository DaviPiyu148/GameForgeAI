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
from unittest.mock import MagicMock, patch
import jwt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.auth.rate_limit import SlidingWindowRateLimiter
from app.auth.tokens import decode_access_token, create_access_token
from app.config import settings
from app.dependencies import get_optional_user
from app.main import app
from app.db.session import Base, get_db
from app.services.auth_service import (
    DuplicateEmailError,
    DuplicateUsernameError,
    auth_service,
)

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


# ─── ADV-CORR-002: TOCTOU INTEGRITY ERROR MAPPING ──────────────────────────────

def test_handle_user_integrity_error_unit():
    """
    Direct unit test for AuthService._handle_user_integrity_error:
    - Verifies db.rollback() is invoked.
    - Inspects error string matching for username and email uniqueness constraints across SQLite/PostgreSQL dialects.
    """
    mock_db = MagicMock()

    # 1. SQLite username uniqueness violation
    err_sqlite_username = IntegrityError("statement", {}, Exception("UNIQUE constraint failed: users.username"))
    with pytest.raises(DuplicateUsernameError) as exc_info:
        auth_service._handle_user_integrity_error(mock_db, err_sqlite_username)
    assert "This username is already taken." in str(exc_info.value)
    assert mock_db.rollback.call_count == 1

    # 2. SQLite email uniqueness violation
    mock_db.reset_mock()
    err_sqlite_email = IntegrityError("statement", {}, Exception("UNIQUE constraint failed: users.email"))
    with pytest.raises(DuplicateEmailError) as exc_info:
        auth_service._handle_user_integrity_error(mock_db, err_sqlite_email)
    assert "An account with this email address already exists." in str(exc_info.value)
    assert mock_db.rollback.call_count == 1

    # 3. PostgreSQL / Named constraint username violation
    mock_db.reset_mock()
    err_pg_username = IntegrityError("statement", {}, Exception('duplicate key value violates unique constraint "uq_users_username"'))
    with pytest.raises(DuplicateUsernameError):
        auth_service._handle_user_integrity_error(mock_db, err_pg_username)
    assert mock_db.rollback.call_count == 1

    # 4. PostgreSQL / Named constraint email violation
    mock_db.reset_mock()
    err_pg_email = IntegrityError("statement", {}, Exception('duplicate key value violates unique constraint "uq_users_email"'))
    with pytest.raises(DuplicateEmailError):
        auth_service._handle_user_integrity_error(mock_db, err_pg_email)
    assert mock_db.rollback.call_count == 1


def test_register_toctou_email_integrity_error_maps_to_409(client):
    """
    Simulates a TOCTOU race during registration where initial get_by_email / get_by_username
    pass, but concurrent insertion triggers an IntegrityError on users.email.
    Endpoint must return HTTP 409 EMAIL_ALREADY_EXISTS, NOT HTTP 500 REGISTRATION_FAILED.
    """
    def mock_create(db, user):
        raise IntegrityError("INSERT INTO users...", {}, Exception("UNIQUE constraint failed: users.email"))

    with patch.object(auth_service.repo, "create", side_effect=mock_create):
        res = client.post("/api/auth/register", json={
            "email": "toctou_email@example.com",
            "username": "UniqueUser1",
            "password": "Password123!",
        })
        assert res.status_code == 409
        data = res.json()
        assert data["error"]["code"] == "EMAIL_ALREADY_EXISTS"
        assert "email address already exists" in data["error"]["message"]


def test_register_toctou_username_integrity_error_maps_to_409(client):
    """
    Simulates a TOCTOU race during registration where initial get_by_username passes,
    but concurrent insertion triggers an IntegrityError on users.username.
    Endpoint must return HTTP 409 USERNAME_TAKEN, NOT HTTP 500 REGISTRATION_FAILED.
    """
    def mock_create(db, user):
        raise IntegrityError("INSERT INTO users...", {}, Exception("UNIQUE constraint failed: users.username"))

    with patch.object(auth_service.repo, "create", side_effect=mock_create):
        res = client.post("/api/auth/register", json={
            "email": "toctou_user@example.com",
            "username": "ConflictUser",
            "password": "Password123!",
        })
        assert res.status_code == 409
        data = res.json()
        assert data["error"]["code"] == "USERNAME_TAKEN"
        assert "username is already taken" in data["error"]["message"]


def test_update_username_toctou_integrity_error_maps_to_409(client):
    """
    Simulates a TOCTOU race during username update:
    Initial check passes, but concurrent update raises IntegrityError on commit.
    Endpoint must return HTTP 409 USERNAME_TAKEN, NOT HTTP 500.
    """
    reg_res = register_user(client, email="updater@example.com", username="UpdaterUser")
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with patch("sqlalchemy.orm.Session.commit", side_effect=IntegrityError("UPDATE users...", {}, Exception("UNIQUE constraint failed: users.username"))):
        res = client.patch("/api/auth/profile", json={"username": "NewName"}, headers=headers)
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "USERNAME_TAKEN"


# ─── ADV-SEC-003: JWT TOKEN REVOCATION VIA TOKEN_VERSION ───────────────────────

def test_token_version_embedded_and_validated(client):
    """
    Verify access tokens embed the 'tv' claim matching user.token_version,
    and missing or outdated 'tv' tokens are rejected with 401.
    """
    reg_res = register_user(client, email="tv_user@example.com", username="TVUser")
    token = reg_res.json()["access_token"]

    # 1. Inspect decoded payload
    payload = decode_access_token(token)
    assert "tv" in payload
    assert payload["tv"] == 1

    # 2. Valid token authenticates successfully
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "TVUser"

    # 3. Token lacking 'tv' claim (legacy / pre-migration / forged) is rejected
    payload_no_tv = {
        "sub": payload["sub"],
        "exp": payload["exp"],
        "type": "access",
    }
    token_no_tv = jwt.encode(payload_no_tv, settings.AUTH_JWT_SECRET, algorithm="HS256")
    res_no_tv = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_no_tv}"})
    assert res_no_tv.status_code == 401
    assert res_no_tv.json()["error"]["code"] == "UNAUTHORIZED"

    # 4. Token with mismatched 'tv' claim is rejected
    payload_wrong_tv = {
        "sub": payload["sub"],
        "exp": payload["exp"],
        "type": "access",
        "tv": 999,
    }
    token_wrong_tv = jwt.encode(payload_wrong_tv, settings.AUTH_JWT_SECRET, algorithm="HS256")
    res_wrong_tv = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_wrong_tv}"})
    assert res_wrong_tv.status_code == 401
    assert res_wrong_tv.json()["error"]["code"] == "UNAUTHORIZED"


def test_password_change_revokes_previous_access_tokens(client):
    """
    Changing password increments token_version:
    - Previous access token becomes invalid (401).
    - New login yields a fresh token that works (200).
    """
    email = "passchange@example.com"
    old_pass = "securepass123"
    new_pass = "brandNewPass789!"

    reg_res = register_user(client, email=email, username="PassChanger", password=old_pass)
    old_token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {old_token}"}

    # Verify old token works initially
    assert client.get("/api/auth/me", headers=headers).status_code == 200

    # Change password
    change_res = client.post(
        "/api/auth/change-password",
        json={"current_password": old_pass, "new_password": new_pass},
        headers=headers,
    )
    assert change_res.status_code == 200
    assert change_res.json()["success"] is True

    # Old token MUST NOW BE REJECTED with 401
    revoked_res = client.get("/api/auth/me", headers=headers)
    assert revoked_res.status_code == 401
    assert revoked_res.json()["error"]["code"] == "UNAUTHORIZED"

    # Login with new password gives a new working token
    login_res = client.post("/api/auth/login", json={"email": email, "password": new_pass})
    assert login_res.status_code == 200
    new_token = login_res.json()["access_token"]
    assert new_token != old_token

    new_payload = decode_access_token(new_token)
    assert new_payload["tv"] == 2

    # New token works
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"}).status_code == 200


def test_reset_password_and_revoke_all_sessions_service():
    """
    Verify AuthService.reset_password and AuthService.revoke_all_sessions increment token_version.
    """
    from app.models.user import User
    from app.dependencies import get_current_user
    from fastapi import HTTPException

    db = TestingSessionLocal()
    try:
        user = User(
            email="reset_test@example.com",
            username="ResetUser",
            password_hash="dummy_hash",
            level=1,
            token_version=1,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Issue token for version 1
        t1 = create_access_token(user.id, token_version=user.token_version)
        assert get_current_user(token=t1, db=db).id == user.id

        # 1. Reset password -> increments token_version to 2
        auth_service.reset_password(db, user, "new_reset_password_123")
        assert user.token_version == 2

        # Old token t1 must fail with HTTPException 401
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token=t1, db=db)
        assert exc_info.value.status_code == 401

        # Fresh token for version 2 succeeds
        t2 = create_access_token(user.id, token_version=user.token_version)
        assert get_current_user(token=t2, db=db).id == user.id

        # 2. Revoke all sessions -> increments token_version to 3
        auth_service.revoke_all_sessions(db, user)
        assert user.token_version == 3

        # Token t2 must now fail
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token=t2, db=db)
        assert exc_info.value.status_code == 401

        # Fresh token for version 3 succeeds
        t3 = create_access_token(user.id, token_version=user.token_version)
        assert get_current_user(token=t3, db=db).id == user.id
    finally:
        db.close()


# ─── ADV-CORR-004: GET_OPTIONAL_USER ERROR PRESERVATION MATRIX ─────────────────

def test_get_optional_user_four_case_matrix():
    """
    Test 4-case matrix for get_optional_user dependency:
    1. No token -> None (guest)
    2. Malformed / expired token -> None (guest)
    3. Valid token + healthy DB -> User (authenticated)
    4. Valid token + DB operational outage -> raises OperationalError (bubbles to 500)
    5. Valid token + outdated/missing token_version -> None (guest)
    """
    from app.models.user import User

    db = TestingSessionLocal()
    try:
        user = User(
            email="optional_user@example.com",
            username="OptUser",
            password_hash="dummy_hash",
            level=1,
            token_version=1,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        valid_token = create_access_token(user.id, token_version=1)

        # Case 1: No token
        assert get_optional_user(token=None, db=db) is None
        assert get_optional_user(token="", db=db) is None

        # Case 2: Malformed or expired token
        assert get_optional_user(token="not-a-valid-jwt-string", db=db) is None
        expired_payload = {
            "sub": user.id,
            "exp": time.time() - 3600,
            "type": "access",
            "tv": 1,
        }
        expired_token = jwt.encode(expired_payload, settings.AUTH_JWT_SECRET, algorithm="HS256")
        assert get_optional_user(token=expired_token, db=db) is None

        # Case 3: Valid token + healthy DB
        resolved = get_optional_user(token=valid_token, db=db)
        assert resolved is not None
        assert resolved.id == user.id
        assert resolved.username == "OptUser"

        # Case 4: Valid token + DB operational error (must NOT swallow as guest)
        mock_broken_db = MagicMock()
        with patch("app.repositories.user_repo.user_repository.get_by_id", side_effect=OperationalError("SELECT...", {}, Exception("database is locked"))):
            with pytest.raises(OperationalError) as exc_info:
                get_optional_user(token=valid_token, db=mock_broken_db)
            assert "database is locked" in str(exc_info.value)

        # Case 5: Valid token structure but outdated or missing token_version -> guest (None)
        mismatched_token = create_access_token(user.id, token_version=99)
        assert get_optional_user(token=mismatched_token, db=db) is None
    finally:
        db.close()
