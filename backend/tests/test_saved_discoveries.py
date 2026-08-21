"""
B7 SavedDiscovery tests.

Tests:
  - Save: valid, duplicate (409), unauthenticated (401)
  - List: returns only requesting user's records
  - Delete: owner success, non-owner 404, unauthenticated 401
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


def _register_and_token(client, email, username):
    res = client.post("/api/auth/register", json={
        "email": email, "username": username, "password": "securepass123"
    })
    assert res.status_code == 201
    return res.json()["access_token"]


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ─── SAVE ──────────────────────────────────────────────────────────────────────

def test_save_discovery_success(client):
    token = _register_and_token(client, "a@example.com", "UserA")
    res = client.post("/api/saved-discoveries", json={"steam_app_id": "12345"},
                      headers=_auth_header(token))
    assert res.status_code == 201
    data = res.json()
    assert data["steam_app_id"] == "12345"
    assert "id" in data
    assert "user_id" in data
    assert "created_at" in data
    # Title and genres come from catalog (may be fallback if catalog not loaded in tests)
    assert "title" in data
    assert "genres" in data


def test_save_discovery_duplicate_returns_409(client):
    token = _register_and_token(client, "a@example.com", "UserA")
    client.post("/api/saved-discoveries", json={"steam_app_id": "12345"},
                headers=_auth_header(token))
    res = client.post("/api/saved-discoveries", json={"steam_app_id": "12345"},
                      headers=_auth_header(token))
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "ALREADY_SAVED"


def test_save_discovery_unauthenticated(client):
    res = client.post("/api/saved-discoveries", json={"steam_app_id": "12345"})
    assert res.status_code == 401


# ─── LIST ──────────────────────────────────────────────────────────────────────

def test_list_discoveries_only_own(client):
    token_a = _register_and_token(client, "a@example.com", "UserA")
    token_b = _register_and_token(client, "b@example.com", "UserB")

    # A saves two games
    client.post("/api/saved-discoveries", json={"steam_app_id": "111"},
                headers=_auth_header(token_a))
    client.post("/api/saved-discoveries", json={"steam_app_id": "222"},
                headers=_auth_header(token_a))
    # B saves one game
    client.post("/api/saved-discoveries", json={"steam_app_id": "333"},
                headers=_auth_header(token_b))

    # A sees only their own
    res_a = client.get("/api/saved-discoveries", headers=_auth_header(token_a))
    assert res_a.status_code == 200
    ids_a = {d["steam_app_id"] for d in res_a.json()["discoveries"]}
    assert ids_a == {"111", "222"}

    # B sees only their own
    res_b = client.get("/api/saved-discoveries", headers=_auth_header(token_b))
    assert res_b.status_code == 200
    ids_b = {d["steam_app_id"] for d in res_b.json()["discoveries"]}
    assert ids_b == {"333"}


def test_list_discoveries_unauthenticated(client):
    res = client.get("/api/saved-discoveries")
    assert res.status_code == 401


# ─── DELETE ────────────────────────────────────────────────────────────────────

def test_delete_discovery_owner_success(client):
    token = _register_and_token(client, "a@example.com", "UserA")
    save_res = client.post("/api/saved-discoveries", json={"steam_app_id": "12345"},
                           headers=_auth_header(token))
    record_id = save_res.json()["id"]

    del_res = client.delete(f"/api/saved-discoveries/{record_id}",
                            headers=_auth_header(token))
    assert del_res.status_code == 204

    # Confirm it's gone
    list_res = client.get("/api/saved-discoveries", headers=_auth_header(token))
    assert list_res.json()["discoveries"] == []


def test_delete_discovery_wrong_user_returns_404(client):
    """User B cannot delete User A's saved discovery — IDOR protection."""
    token_a = _register_and_token(client, "a@example.com", "UserA")
    token_b = _register_and_token(client, "b@example.com", "UserB")

    save_res = client.post("/api/saved-discoveries", json={"steam_app_id": "12345"},
                           headers=_auth_header(token_a))
    record_id = save_res.json()["id"]

    del_res = client.delete(f"/api/saved-discoveries/{record_id}",
                            headers=_auth_header(token_b))
    # Must return 404, not 403 — owner mismatch is indistinguishable from not-found
    assert del_res.status_code == 404


def test_delete_discovery_unauthenticated(client):
    res = client.delete("/api/saved-discoveries/some-id")
    assert res.status_code == 401


def test_delete_nonexistent_returns_404(client):
    token = _register_and_token(client, "a@example.com", "UserA")
    res = client.delete("/api/saved-discoveries/nonexistent-id",
                        headers=_auth_header(token))
    assert res.status_code == 404
