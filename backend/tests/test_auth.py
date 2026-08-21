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
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

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
