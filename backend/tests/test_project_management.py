"""
Tests for Sprint A project management endpoints:
  DELETE /api/projects/{id}   — permanent deletion (204 No Content)
  POST   /api/projects/{id}/duplicate — snapshot copy (201 Created)

Rename (PATCH /api/projects/{id} with title) is already covered by
the existing test_update_allowed_fields test in test_projects.py.
"""
import time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import Base, get_db
from app.models.project import Project
from app.models.project_version import ProjectVersion
from app.models.playtest import PlaytestSession

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# SQLite does not enforce FK constraints by default. Enable them per-connection
# so that ondelete=CASCADE relationships fire correctly in tests.
from sqlalchemy import event as sa_event

@sa_event.listens_for(test_engine, "connect")
def set_sqlite_pragma(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create fresh schema for each test."""
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
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _register_and_token(client, email="test@example.com", username="TestUser"):
    res = client.post("/api/auth/register", json={
        "email": email,
        "username": username,
        "password": "securepass123",
    })
    assert res.status_code == 201
    return res.json()["access_token"], res.json()["user"]["id"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_project_orm(user_id: str, **overrides) -> str:
    """Insert a project directly via ORM, returning its ID."""
    db = TestingSessionLocal()
    try:
        project = Project(
            user_id=user_id,
            title=overrides.get("title", "Test Project"),
            genre=overrides.get("genre", "Action"),
            prompt=overrides.get("prompt", "A test game"),
            status="PLAYABLE",
            engine=overrides.get("engine", "Top-Down Action"),
            art_density=overrides.get("art_density", 50),
            physics=overrides.get("physics", 80),
            modules=overrides.get("modules", []),
            scale=overrides.get("scale", "standard"),
            world_mode=overrides.get("world_mode", "linear"),
            design_spec=overrides.get("design_spec"),
            game_dsl=overrides.get("game_dsl"),
            current_version=overrides.get("current_version", 1),
        )
        db.add(project)
        db.flush()

        # Optionally add a ProjectVersion row
        if project.game_dsl:
            v1 = ProjectVersion(
                project_id=project.id,
                version_number=1,
                game_dsl=project.game_dsl,
                design_spec=project.design_spec,
                change_summary="Initial v1",
            )
            db.add(v1)

        db.commit()
        db.refresh(project)
        return project.id
    finally:
        db.close()


def _add_playtest(project_id: str, user_id: str):
    """Insert a PlaytestSession for cascade-deletion verification."""
    db = TestingSessionLocal()
    try:
        session = PlaytestSession(
            project_id=project_id,
            user_id=user_id,
            duration_seconds=60,
            score=100,
            outcome="PLAYED",
        )
        db.add(session)
        db.commit()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────
# DELETE /api/projects/{id} tests
# ─────────────────────────────────────────────────────────

class TestDeleteProject:

    def test_owner_can_delete_project(self, client):
        """Owner DELETE returns 204 and the project is gone."""
        token, user_id = _register_and_token(client)
        proj_id = _create_project_orm(user_id, title="To Delete")

        res = client.delete(f"/api/projects/{proj_id}", headers=_auth(token))
        assert res.status_code == 204

        # Confirm it's gone from the API
        get_res = client.get(f"/api/projects/{proj_id}", headers=_auth(token))
        assert get_res.status_code == 404

    def test_non_owner_delete_returns_404(self, client):
        """IDOR: non-owner DELETE returns 404, project not deleted."""
        from app.models.user import User
        from app.auth.password import hash_password

        db = TestingSessionLocal()
        try:
            other = User(
                email="other@example.com",
                username="OtherUser",
                password_hash=hash_password("securepass123"),
                level=1,
            )
            db.add(other)
            db.commit()
            db.refresh(other)
            other_id = other.id
        finally:
            db.close()

        other_proj_id = _create_project_orm(other_id, title="OtherProject")

        # Attacker cannot delete
        token, _ = _register_and_token(client)
        res = client.delete(f"/api/projects/{other_proj_id}", headers=_auth(token))
        assert res.status_code == 404

        # Project still exists for its real owner
        db = TestingSessionLocal()
        try:
            assert db.query(Project).filter(Project.id == other_proj_id).first() is not None
        finally:
            db.close()

    def test_delete_nonexistent_project_returns_404(self, client):
        """Deleting a project ID that does not exist returns 404."""
        token, _ = _register_and_token(client)
        res = client.delete("/api/projects/does-not-exist", headers=_auth(token))
        assert res.status_code == 404

    def test_delete_requires_auth(self, client):
        """DELETE without token returns 401."""
        res = client.delete("/api/projects/some-id")
        assert res.status_code == 401

    def test_delete_cascades_project_versions(self, client):
        """Deleting a project removes its ProjectVersion rows (CASCADE)."""
        token, user_id = _register_and_token(client)
        game_dsl = {"levels": [{"id": "l1"}]}
        proj_id = _create_project_orm(user_id, game_dsl=game_dsl)

        # Confirm version row exists pre-deletion
        db = TestingSessionLocal()
        try:
            count_before = db.query(ProjectVersion).filter(
                ProjectVersion.project_id == proj_id
            ).count()
            assert count_before == 1
        finally:
            db.close()

        client.delete(f"/api/projects/{proj_id}", headers=_auth(token))

        db = TestingSessionLocal()
        try:
            count_after = db.query(ProjectVersion).filter(
                ProjectVersion.project_id == proj_id
            ).count()
            assert count_after == 0
        finally:
            db.close()

    def test_delete_cascades_playtest_sessions(self, client):
        """Deleting a project removes its PlaytestSession rows (CASCADE)."""
        token, user_id = _register_and_token(client)
        proj_id = _create_project_orm(user_id)
        _add_playtest(proj_id, user_id)

        # Confirm playtest row pre-deletion
        db = TestingSessionLocal()
        try:
            count_before = db.query(PlaytestSession).filter(
                PlaytestSession.project_id == proj_id
            ).count()
            assert count_before == 1
        finally:
            db.close()

        client.delete(f"/api/projects/{proj_id}", headers=_auth(token))

        db = TestingSessionLocal()
        try:
            count_after = db.query(PlaytestSession).filter(
                PlaytestSession.project_id == proj_id
            ).count()
            assert count_after == 0
        finally:
            db.close()


# ─────────────────────────────────────────────────────────
# POST /api/projects/{id}/duplicate tests
# ─────────────────────────────────────────────────────────

class TestDuplicateProject:

    def test_duplicate_creates_new_project(self, client):
        """Duplicate returns 201 with a new project that has a different ID."""
        token, user_id = _register_and_token(client)
        proj_id = _create_project_orm(user_id, title="Original")

        res = client.post(f"/api/projects/{proj_id}/duplicate", headers=_auth(token))
        assert res.status_code == 201
        data = res.json()

        assert data["id"] != proj_id
        assert data["title"] == "Original (Copy)"

    def test_duplicate_owned_by_same_user(self, client):
        """Duplicate belongs to the same user as the original."""
        token, user_id = _register_and_token(client)
        proj_id = _create_project_orm(user_id, title="Original")

        res = client.post(f"/api/projects/{proj_id}/duplicate", headers=_auth(token))
        assert res.status_code == 201
        copy_id = res.json()["id"]

        # The copy should appear in the owner's project list
        list_res = client.get("/api/projects", headers=_auth(token))
        assert list_res.status_code == 200
        ids = [p["id"] for p in list_res.json()["projects"]]
        assert copy_id in ids

    def test_duplicate_inherits_configuration(self, client):
        """Duplicate copies configuration fields correctly."""
        token, user_id = _register_and_token(client)
        proj_id = _create_project_orm(
            user_id,
            title="Space Shooter",
            genre="Action",
            engine="Arena Survival",
            art_density=75,
            physics=90,
            modules=["Procedural Generation"],
            scale="campaign",
            world_mode="open_world",
            prompt="A space combat game",
        )

        res = client.post(f"/api/projects/{proj_id}/duplicate", headers=_auth(token))
        assert res.status_code == 201
        data = res.json()

        assert data["title"] == "Space Shooter (Copy)"
        assert data["genre"] == "Action"
        params = data["parameters"]
        assert params["engine"] == "Arena Survival"
        assert params["artDensity"] == 75
        assert params["physics"] == 90
        assert params["scale"] == "campaign"
        assert params["worldMode"] == "open_world"

    def test_duplicate_starts_at_version_1(self, client):
        """Duplicate always starts at current_version = 1."""
        token, user_id = _register_and_token(client)
        proj_id = _create_project_orm(user_id, current_version=3)

        res = client.post(f"/api/projects/{proj_id}/duplicate", headers=_auth(token))
        assert res.status_code == 201
        assert res.json()["currentVersion"] == 1

    def test_duplicate_creates_fresh_version_history(self, client):
        """Duplicate has exactly one ProjectVersion row (v1), not the original's history."""
        token, user_id = _register_and_token(client)
        game_dsl = {"levels": [{"id": "l1"}]}
        proj_id = _create_project_orm(user_id, game_dsl=game_dsl)

        # The original has 1 version row from _create_project_orm
        res = client.post(f"/api/projects/{proj_id}/duplicate", headers=_auth(token))
        assert res.status_code == 201
        copy_id = res.json()["id"]

        db = TestingSessionLocal()
        try:
            orig_versions = db.query(ProjectVersion).filter(
                ProjectVersion.project_id == proj_id
            ).count()
            copy_versions = db.query(ProjectVersion).filter(
                ProjectVersion.project_id == copy_id
            ).count()
            assert orig_versions == 1, "Original should still have its own version row"
            assert copy_versions == 1, "Duplicate should have exactly one fresh v1"

            copy_v1 = db.query(ProjectVersion).filter(
                ProjectVersion.project_id == copy_id
            ).first()
            assert copy_v1 is not None
            assert copy_v1.version_number == 1
        finally:
            db.close()

    def test_duplicate_does_not_inherit_playtest_sessions(self, client):
        """Duplicate has no playtest sessions from the original."""
        token, user_id = _register_and_token(client)
        proj_id = _create_project_orm(user_id)
        _add_playtest(proj_id, user_id)

        res = client.post(f"/api/projects/{proj_id}/duplicate", headers=_auth(token))
        assert res.status_code == 201
        copy_id = res.json()["id"]

        db = TestingSessionLocal()
        try:
            copy_playtest_count = db.query(PlaytestSession).filter(
                PlaytestSession.project_id == copy_id
            ).count()
            assert copy_playtest_count == 0
        finally:
            db.close()

    def test_duplicate_non_owner_returns_404(self, client):
        """IDOR: non-owner duplicate returns 404."""
        from app.models.user import User
        from app.auth.password import hash_password

        db = TestingSessionLocal()
        try:
            other = User(
                email="other2@example.com",
                username="OtherUser2",
                password_hash=hash_password("securepass123"),
                level=1,
            )
            db.add(other)
            db.commit()
            db.refresh(other)
            other_id = other.id
        finally:
            db.close()

        other_proj_id = _create_project_orm(other_id, title="Private Project")

        token, _ = _register_and_token(client)
        res = client.post(f"/api/projects/{other_proj_id}/duplicate", headers=_auth(token))
        assert res.status_code == 404

    def test_duplicate_requires_auth(self, client):
        """POST /duplicate without token returns 401."""
        res = client.post("/api/projects/some-id/duplicate")
        assert res.status_code == 401

    def test_duplicate_nonexistent_project_returns_404(self, client):
        """POST /duplicate for nonexistent project returns 404."""
        token, _ = _register_and_token(client)
        res = client.post("/api/projects/does-not-exist/duplicate", headers=_auth(token))
        assert res.status_code == 404
