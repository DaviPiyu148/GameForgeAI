"""
B7 Authorization / IDOR test matrix.

Mandatory B7 exit criterion: User A CANNOT access User B's resources.

Matrix:
  GET  /api/projects/{B_project_id}         → 404
  PATCH /api/projects/{B_project_id}        → 404
  GET  /api/builds/{B_build_id}             → 404
  GET  /api/builds/{B_build_id}/logs        → 404
  GET  /api/builds/{B_build_id}/events      → 404 (before stream starts)
  DELETE /api/saved-discoveries/{B_rec_id}  → 404

  GET /api/projects   → only A's projects (B's not in list)
  GET /api/saved-discoveries → only A's records
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import Base, get_db
from app.models.project import Project
from app.models.build import BuildJob
from app.models.saved_discovery import SavedDiscovery
from app.models.user import User
from app.auth.password import hash_password

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
    return res.json()["access_token"], res.json()["user"]["id"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_project_in_db(user_id: str) -> str:
    """Create a project directly in DB (since POST /api/projects is internal)."""
    from datetime import datetime, timezone
    db = TestingSessionLocal()
    try:
        project = Project(
            user_id=user_id,
            title="Test Project",
            genre="Test",
            prompt="Test prompt",
            status="PLAYABLE",
            engine="Phaser",
            art_density=50,
            physics=50,
            modules=[],
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project.id
    finally:
        db.close()


def _create_build_in_db(user_id: str) -> str:
    """Create a build job directly in DB."""
    db = TestingSessionLocal()
    try:
        build = BuildJob(
            user_id=user_id,
            prompt="Test build",
            engine="Phaser",
            art_density=50,
            physics=50,
            modules=[],
            status="SUCCESS",
        )
        db.add(build)
        db.commit()
        db.refresh(build)
        return build.id
    finally:
        db.close()


def _create_saved_discovery_in_db(user_id: str, steam_app_id: str = "99999") -> str:
    """Create a saved discovery directly in DB."""
    db = TestingSessionLocal()
    try:
        sd = SavedDiscovery(user_id=user_id, steam_app_id=steam_app_id)
        db.add(sd)
        db.commit()
        db.refresh(sd)
        return sd.id
    finally:
        db.close()


# ─── THE IDOR MATRIX ───────────────────────────────────────────────────────────

class TestIDORMatrix:
    """User A cannot access User B's resources. All cross-access returns 404."""

    def test_project_get_cross_user_404(self, client):
        token_a, user_a_id = _register_and_token(client, "a@x.com", "UserA")
        _, user_b_id = _register_and_token(client, "b@x.com", "UserB")

        b_project_id = _create_project_in_db(user_b_id)
        res = client.get(f"/api/projects/{b_project_id}", headers=_auth(token_a))
        assert res.status_code == 404, f"Expected 404, got {res.status_code}: {res.text}"

    def test_project_patch_cross_user_404(self, client):
        token_a, user_a_id = _register_and_token(client, "a@x.com", "UserA")
        _, user_b_id = _register_and_token(client, "b@x.com", "UserB")

        b_project_id = _create_project_in_db(user_b_id)
        res = client.patch(f"/api/projects/{b_project_id}",
                           json={"title": "Hijacked"},
                           headers=_auth(token_a))
        assert res.status_code == 404

    def test_build_get_cross_user_404(self, client):
        token_a, user_a_id = _register_and_token(client, "a@x.com", "UserA")
        _, user_b_id = _register_and_token(client, "b@x.com", "UserB")

        b_build_id = _create_build_in_db(user_b_id)
        res = client.get(f"/api/builds/{b_build_id}", headers=_auth(token_a))
        assert res.status_code == 404

    def test_build_logs_cross_user_404(self, client):
        token_a, user_a_id = _register_and_token(client, "a@x.com", "UserA")
        _, user_b_id = _register_and_token(client, "b@x.com", "UserB")

        b_build_id = _create_build_in_db(user_b_id)
        res = client.get(f"/api/builds/{b_build_id}/logs", headers=_auth(token_a))
        assert res.status_code == 404

    def test_build_events_cross_user_404(self, client):
        token_a, user_a_id = _register_and_token(client, "a@x.com", "UserA")
        _, user_b_id = _register_and_token(client, "b@x.com", "UserB")

        b_build_id = _create_build_in_db(user_b_id)
        res = client.get(f"/api/builds/{b_build_id}/events", headers=_auth(token_a))
        # SSE endpoint — ownership check returns 404 before stream starts
        assert res.status_code == 404

    def test_saved_discovery_delete_cross_user_404(self, client):
        token_a, user_a_id = _register_and_token(client, "a@x.com", "UserA")
        _, user_b_id = _register_and_token(client, "b@x.com", "UserB")

        b_record_id = _create_saved_discovery_in_db(user_b_id)
        res = client.delete(f"/api/saved-discoveries/{b_record_id}",
                            headers=_auth(token_a))
        assert res.status_code == 404

    def test_projects_list_only_own(self, client):
        token_a, user_a_id = _register_and_token(client, "a@x.com", "UserA")
        _, user_b_id = _register_and_token(client, "b@x.com", "UserB")

        _create_project_in_db(user_a_id)
        _create_project_in_db(user_b_id)

        res = client.get("/api/projects", headers=_auth(token_a))
        assert res.status_code == 200
        project_ids = [p["id"] for p in res.json()["projects"]]
        # A should only see 1 project — their own
        assert len(project_ids) == 1

    def test_saved_discoveries_list_only_own(self, client):
        token_a, user_a_id = _register_and_token(client, "a@x.com", "UserA")
        _, user_b_id = _register_and_token(client, "b@x.com", "UserB")

        _create_saved_discovery_in_db(user_a_id, "111")
        _create_saved_discovery_in_db(user_b_id, "222")

        res = client.get("/api/saved-discoveries", headers=_auth(token_a))
        assert res.status_code == 200
        steam_ids = {d["steam_app_id"] for d in res.json()["discoveries"]}
        assert steam_ids == {"111"}
        assert "222" not in steam_ids

    def test_unauthenticated_projects_returns_401(self, client):
        res = client.get("/api/projects")
        assert res.status_code == 401

    def test_unauthenticated_builds_returns_401(self, client):
        res = client.post("/api/builds", json={
            "prompt": "Test",
            "parameters": {"artDensity": 50, "physics": 50}
        })
        assert res.status_code == 401
