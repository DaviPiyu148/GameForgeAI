"""
B7-updated project API tests.

Changes from B6: POST /api/projects is removed from the public router.
Tests now create projects directly via ORM (as the build service would) and
test GET/PATCH with proper authentication.
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

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create fresh schema for each test and tear down afterward."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    """TestClient fixture overriding get_db dependency with isolated test session."""
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


def _register_and_token(client):
    """Register a test user and return (token, user_id)."""
    res = client.post("/api/auth/register", json={
        "email": "test@example.com",
        "username": "TestUser",
        "password": "securepass123",
    })
    assert res.status_code == 201
    return res.json()["access_token"], res.json()["user"]["id"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_project_in_db(user_id: str, **overrides) -> str:
    """Create a project directly via ORM (as build service would)."""
    db = TestingSessionLocal()
    try:
        project = Project(
            user_id=user_id,
            title=overrides.get("title", "Test Project"),
            genre=overrides.get("genre", "Generated Concept"),
            prompt=overrides.get("prompt", "Test prompt"),
            status="PLAYABLE",
            engine="Phaser",
            art_density=overrides.get("art_density", 70),
            physics=overrides.get("physics", 60),
            modules=overrides.get("modules", []),
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project.id
    finally:
        db.close()


def test_get_project_by_id(client):
    """Get a project by ID — authenticated owner."""
    token, user_id = _register_and_token(client)
    proj_id = _create_project_in_db(user_id, title="Void Drift", genre="Racing")

    res = client.get(f"/api/projects/{proj_id}", headers=_auth(token))
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == proj_id
    assert data["title"] == "Void Drift"
    assert data["genre"] == "Racing"


def test_list_projects(client):
    """List returns only the authenticated user's projects, newest first."""
    token, user_id = _register_and_token(client)
    _create_project_in_db(user_id, title="Project Alpha")
    time.sleep(0.05)
    _create_project_in_db(user_id, title="Project Beta")

    res = client.get("/api/projects", headers=_auth(token))
    assert res.status_code == 200
    data = res.json()
    assert "projects" in data
    assert len(data["projects"]) == 2
    # Newest first
    assert data["projects"][0]["title"] == "Project Beta"
    assert data["projects"][1]["title"] == "Project Alpha"


def test_list_projects_requires_auth(client):
    """GET /api/projects without token returns 401."""
    res = client.get("/api/projects")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


def test_get_project_requires_auth(client):
    """GET /api/projects/{id} without token returns 401."""
    res = client.get("/api/projects/any-id")
    assert res.status_code == 401


def test_update_allowed_fields(client):
    """PATCH allowed fields (title, genre, parameters) — authenticated owner."""
    token, user_id = _register_and_token(client)
    proj_id = _create_project_in_db(user_id, title="Original Title", genre="RPG")

    time.sleep(0.05)

    res = client.patch(f"/api/projects/{proj_id}", headers=_auth(token), json={
        "title": "Updated Title",
        "genre": "Action RPG",
        "parameters": {
            "engine": "Phaser Custom",
            "artDensity": 85,
            "physics": 75,
            "modules": ["inventory"],
            "scale": "campaign",
            "worldMode": "open_world",
        }
    })
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Updated Title"
    assert data["genre"] == "Action RPG"
    assert data["parameters"]["artDensity"] == 85
    # Regression: PATCH .../parameters used to copy only engine/artDensity/
    # physics/modules onto the Project row, silently dropping scale/worldMode
    # (the Project model had no columns for them at all, so any value sent
    # here was discarded regardless).
    assert data["parameters"]["scale"] == "campaign"
    assert data["parameters"]["worldMode"] == "open_world"


def test_nonexistent_project_404(client):
    """Nonexistent project ID returns 404 with structured error envelope."""
    token, _ = _register_and_token(client)
    res = client.get("/api/projects/nonexistent-id-12345", headers=_auth(token))
    assert res.status_code == 404
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "PROJECT_NOT_FOUND"


def test_other_users_project_returns_404(client):
    """IDOR: accessing another user's project returns 404 (not 403)."""
    from app.models.user import User
    from app.auth.password import hash_password

    # Create a second user directly in DB
    db = TestingSessionLocal()
    try:
        other_user = User(
            email="other@example.com",
            username="OtherUser",
            password_hash=hash_password("securepass123"),
            level=1,
        )
        db.add(other_user)
        db.commit()
        db.refresh(other_user)
        other_user_id = other_user.id
    finally:
        db.close()

    other_proj_id = _create_project_in_db(other_user_id, title="Other User Project")

    # A tries to access other's project
    token, _ = _register_and_token(client)
    res = client.get(f"/api/projects/{other_proj_id}", headers=_auth(token))
    assert res.status_code == 404


def test_project_persists_in_db(client):
    """Verify project persists in database and is retrievable."""
    token, user_id = _register_and_token(client)
    proj_id = _create_project_in_db(user_id, title="Persistence Test", genre="Simulation")

    direct_session = TestingSessionLocal()
    try:
        db_proj = direct_session.query(Project).filter(Project.id == proj_id).first()
        assert db_proj is not None
        assert db_proj.title == "Persistence Test"
        assert db_proj.user_id == user_id
    finally:
        direct_session.close()


def test_restore_project_version_creates_forward_version(client):
    """Verify restoring a historical version creates immutable vN+1 with clean provenance."""
    from app.models.project_version import ProjectVersion

    token, user_id = _register_and_token(client)
    proj_id = _create_project_in_db(user_id, title="Restore Test", genre="Action")

    v1_dsl = {"title": "V1 Game", "player": {"speed": 200}}
    v2_dsl = {"title": "V2 Game", "player": {"speed": 250}}
    v3_dsl = {"title": "V3 Game", "player": {"speed": 300}}

    # Set up historical versions in DB
    db = TestingSessionLocal()
    try:
        # Update project to v3
        proj = db.query(Project).filter(Project.id == proj_id).first()
        proj.game_dsl = v3_dsl
        proj.current_version = 3

        # Add v1, v2, v3 rows
        ver1 = ProjectVersion(
            project_id=proj_id,
            version_number=1,
            game_dsl=v1_dsl,
            change_summary="Initial generation",
            remix_intent=None,
        )
        ver2 = ProjectVersion(
            project_id=proj_id,
            version_number=2,
            game_dsl=v2_dsl,
            change_summary="Speed patch",
            remix_intent=None,
        )
        ver3 = ProjectVersion(
            project_id=proj_id,
            version_number=3,
            game_dsl=v3_dsl,
            change_summary="Remix applied: Fast & Agile",
            remix_intent=[{"type": "fast_and_agile"}],
        )
        db.add_all([ver1, ver2, ver3])
        db.commit()
    finally:
        db.close()

    # Restore v1
    res = client.post(
        f"/api/projects/{proj_id}/restore?target_version_number=1",
        headers=_auth(token),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["currentVersion"] == 4
    assert data["gameDsl"] == v1_dsl

    # Verify versions list endpoint
    ver_res = client.get(f"/api/projects/{proj_id}/versions", headers=_auth(token))
    assert ver_res.status_code == 200
    versions = ver_res.json()
    assert len(versions) == 4
    assert [v["version_number"] for v in versions] == [1, 2, 3, 4]

    # Verify v4 details: clean provenance and accurate change summary
    v4 = versions[3]
    assert v4["version_number"] == 4
    assert v4["game_dsl"] == v1_dsl
    assert v4["change_summary"] == "Restored from version 1."
    assert v4["remix_intent"] is None

    # Verify v1, v2, v3 remain completely untouched
    assert versions[0]["game_dsl"] == v1_dsl
    assert versions[2]["remix_intent"] == [{"type": "fast_and_agile"}]


def test_restore_nonexistent_version_returns_404(client):
    """Verify restoring a nonexistent version number returns 404."""
    token, user_id = _register_and_token(client)
    proj_id = _create_project_in_db(user_id, title="404 Restore Test")

    res = client.post(
        f"/api/projects/{proj_id}/restore?target_version_number=99",
        headers=_auth(token),
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "VERSION_NOT_FOUND"


def test_restore_unowned_project_returns_404(client):
    """Verify cannot restore another user's project (IDOR protection)."""
    from app.models.user import User
    from app.services.auth_service import hash_password

    # Create other user in DB
    db = TestingSessionLocal()
    try:
        other_user = User(
            email="other@example.com",
            username="OtherUser",
            password_hash=hash_password("securepass123"),
            level=1,
        )
        db.add(other_user)
        db.commit()
        db.refresh(other_user)
        other_user_id = other_user.id
    finally:
        db.close()

    other_proj_id = _create_project_in_db(other_user_id, title="Other User Project")

    # Current user attempts to restore other user's project
    token, _ = _register_and_token(client)
    res = client.post(
        f"/api/projects/{other_proj_id}/restore?target_version_number=1",
        headers=_auth(token),
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "PROJECT_NOT_FOUND"


