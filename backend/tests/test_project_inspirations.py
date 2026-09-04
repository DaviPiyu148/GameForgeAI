"""
ProjectInspiration API & Persistence Tests (Step 2: Discovery -> Inspiration -> Studio).

Covers:
  - CREATE: valid attach, 409 on duplicate, 401 unauth, 404 wrong owner / missing project
  - LIST: lists only project's inspirations, ordered newest first, isolation between projects/users
  - DELETE: 204 detach, 404 not found / wrong owner
  - CASCADE: deleting project cascades and removes its inspirations
  - SNAPSHOT INTEGRITY: immutable historical snapshot even after catalog mutation
  - CONCURRENCY RACE: database unique constraint ensures exactly 1 row even under racing attaches
  - STRICT PAYLOAD: client-supplied extra metadata rejected (422 extra="forbid")
"""
import pytest
from unittest.mock import patch
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import Base, get_db
from app.models.project import Project
from app.models.project_inspiration import ProjectInspiration
from app.models.user import User

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


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
    res = client.post(
        "/api/auth/register",
        json={"email": email, "username": username, "password": "securepass123"},
    )
    assert res.status_code == 201
    return res.json()["access_token"], res.json()["user"]["id"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_project_in_db(user_id: str, title: str = "Test Project", genre: str = "RPG") -> str:
    db = TestingSessionLocal()
    try:
        project = Project(
            user_id=user_id,
            title=title,
            genre=genre,
            prompt="A test game idea",
            status="PLAYABLE",
            engine="Top-Down Action",
            art_density=50,
            physics=80,
            modules=[],
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project.id
    finally:
        db.close()


# ─── CREATE ───────────────────────────────────────────────────────────────────

def test_attach_inspiration_success(client):
    token_a, user_a_id = _register_and_token(client, "user_a@example.com", "UserA")
    project_id = _create_project_in_db(user_a_id)

    mock_game = {
        "id": "570",
        "title": "Dota 2",
        "display_title": "Dota 2",
        "hero_image_url": "https://cdn.steam.com/dota2.jpg",
        "genres": ["Action", "Strategy"],
        "display_genres": ["Action", "Strategy"],
        "tags": ["MOBA", "Multiplayer", "Competitive", "eSports"],
        "display_tags": ["MOBA", "Multiplayer", "Competitive", "eSports"],
        "player_modes": ["Multi-player", "Co-op"],
    }

    with patch("app.services.discovery_service.DiscoveryService.get_game_by_steam_id", return_value=mock_game):
        res = client.post(
            f"/api/projects/{project_id}/inspirations",
            json={"steam_app_id": "570"},
            headers=_auth(token_a),
        )

    assert res.status_code == 201
    data = res.json()
    assert data["projectId"] == project_id
    assert data["steamAppId"] == "570"
    assert data["title"] == "Dota 2"
    assert data["coverUrl"] == "https://cdn.steam.com/dota2.jpg"
    assert data["genres"] == ["Action", "Strategy"]
    assert data["tags"] == ["MOBA", "Multiplayer", "Competitive", "eSports"]
    assert data["playerModes"] == ["Multi-player", "Co-op"]
    assert "id" in data
    assert "createdAt" in data


def test_attach_inspiration_duplicate_returns_409(client):
    token_a, user_a_id = _register_and_token(client, "user_a@example.com", "UserA")
    project_id = _create_project_in_db(user_a_id)

    res1 = client.post(
        f"/api/projects/{project_id}/inspirations",
        json={"steam_app_id": "570"},
        headers=_auth(token_a),
    )
    assert res1.status_code == 201

    res2 = client.post(
        f"/api/projects/{project_id}/inspirations",
        json={"steam_app_id": "570"},
        headers=_auth(token_a),
    )
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "ALREADY_INSPIRED"


def test_attach_inspiration_unauthenticated(client):
    res = client.post("/api/projects/some-id/inspirations", json={"steam_app_id": "570"})
    assert res.status_code == 401


def test_attach_inspiration_wrong_owner_returns_404(client):
    token_a, user_a_id = _register_and_token(client, "user_a@example.com", "UserA")
    token_b, _ = _register_and_token(client, "user_b@example.com", "UserB")
    project_id = _create_project_in_db(user_a_id)

    # User B tries to attach inspiration to User A's project
    res = client.post(
        f"/api/projects/{project_id}/inspirations",
        json={"steam_app_id": "570"},
        headers=_auth(token_b),
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "PROJECT_NOT_FOUND"


def test_attach_inspiration_project_not_found(client):
    token_a, _ = _register_and_token(client, "user_a@example.com", "UserA")
    res = client.post(
        "/api/projects/00000000-0000-0000-0000-000000000000/inspirations",
        json={"steam_app_id": "570"},
        headers=_auth(token_a),
    )
    assert res.status_code == 404


def test_attach_extra_fields_forbidden(client):
    token_a, user_a_id = _register_and_token(client, "user_a@example.com", "UserA")
    project_id = _create_project_in_db(user_a_id)

    # Attempting to inject fake client metadata should be rejected with 422
    res = client.post(
        f"/api/projects/{project_id}/inspirations",
        json={"steam_app_id": "570", "title": "Fake Injected Title"},
        headers=_auth(token_a),
    )
    assert res.status_code == 422


# ─── LIST ─────────────────────────────────────────────────────────────────────

def test_list_inspirations_success_and_ordering(client):
    token_a, user_a_id = _register_and_token(client, "user_a@example.com", "UserA")
    project_id = _create_project_in_db(user_a_id)

    client.post(
        f"/api/projects/{project_id}/inspirations",
        json={"steam_app_id": "100"},
        headers=_auth(token_a),
    )
    client.post(
        f"/api/projects/{project_id}/inspirations",
        json={"steam_app_id": "200"},
        headers=_auth(token_a),
    )

    res = client.get(
        f"/api/projects/{project_id}/inspirations",
        headers=_auth(token_a),
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["inspirations"]) == 2
    # Newest first
    assert data["inspirations"][0]["steamAppId"] == "200"
    assert data["inspirations"][1]["steamAppId"] == "100"


def test_list_inspirations_isolation(client):
    token_a, user_a_id = _register_and_token(client, "user_a@example.com", "UserA")
    token_b, user_b_id = _register_and_token(client, "user_b@example.com", "UserB")

    project_a = _create_project_in_db(user_a_id, "Project A")
    project_b = _create_project_in_db(user_b_id, "Project B")

    client.post(
        f"/api/projects/{project_a}/inspirations",
        json={"steam_app_id": "111"},
        headers=_auth(token_a),
    )
    client.post(
        f"/api/projects/{project_b}/inspirations",
        json={"steam_app_id": "222"},
        headers=_auth(token_b),
    )

    # User A listing Project A
    res_a = client.get(f"/api/projects/{project_a}/inspirations", headers=_auth(token_a))
    assert res_a.status_code == 200
    assert len(res_a.json()["inspirations"]) == 1
    assert res_a.json()["inspirations"][0]["steamAppId"] == "111"

    # User A attempting to list Project B -> 404 (IDOR)
    res_a_on_b = client.get(f"/api/projects/{project_b}/inspirations", headers=_auth(token_a))
    assert res_a_on_b.status_code == 404


def test_list_inspirations_unauthenticated(client):
    res = client.get("/api/projects/some-id/inspirations")
    assert res.status_code == 401


# ─── DELETE ───────────────────────────────────────────────────────────────────

def test_detach_inspiration_success(client):
    token_a, user_a_id = _register_and_token(client, "user_a@example.com", "UserA")
    project_id = _create_project_in_db(user_a_id)

    client.post(
        f"/api/projects/{project_id}/inspirations",
        json={"steam_app_id": "570"},
        headers=_auth(token_a),
    )

    del_res = client.delete(
        f"/api/projects/{project_id}/inspirations/570",
        headers=_auth(token_a),
    )
    assert del_res.status_code == 204

    # Verify list is now empty
    list_res = client.get(
        f"/api/projects/{project_id}/inspirations",
        headers=_auth(token_a),
    )
    assert list_res.json()["inspirations"] == []


def test_detach_inspiration_not_found(client):
    token_a, user_a_id = _register_and_token(client, "user_a@example.com", "UserA")
    project_id = _create_project_in_db(user_a_id)

    res = client.delete(
        f"/api/projects/{project_id}/inspirations/99999",
        headers=_auth(token_a),
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "INSPIRATION_NOT_FOUND"


def test_detach_inspiration_wrong_owner_returns_404(client):
    token_a, user_a_id = _register_and_token(client, "user_a@example.com", "UserA")
    token_b, _ = _register_and_token(client, "user_b@example.com", "UserB")
    project_id = _create_project_in_db(user_a_id)

    client.post(
        f"/api/projects/{project_id}/inspirations",
        json={"steam_app_id": "570"},
        headers=_auth(token_a),
    )

    # User B tries to detach User A's inspiration
    res = client.delete(
        f"/api/projects/{project_id}/inspirations/570",
        headers=_auth(token_b),
    )
    assert res.status_code == 404


# ─── CASCADE ──────────────────────────────────────────────────────────────────

def test_project_delete_cascades_inspirations(client):
    token_a, user_a_id = _register_and_token(client, "user_a@example.com", "UserA")
    project_id = _create_project_in_db(user_a_id)

    client.post(
        f"/api/projects/{project_id}/inspirations",
        json={"steam_app_id": "570"},
        headers=_auth(token_a),
    )

    # Delete the project
    del_proj = client.delete(f"/api/projects/{project_id}", headers=_auth(token_a))
    assert del_proj.status_code == 204

    # Verify rows in DB for that project are 0
    db = TestingSessionLocal()
    try:
        count = db.query(ProjectInspiration).filter(ProjectInspiration.project_id == project_id).count()
        assert count == 0
    finally:
        db.close()


# ─── SNAPSHOT INTEGRITY ───────────────────────────────────────────────────────

def test_snapshot_immutable_after_catalog_mutation(client):
    token_a, user_a_id = _register_and_token(client, "user_a@example.com", "UserA")
    project_id = _create_project_in_db(user_a_id)

    initial_catalog_entry = {
        "id": "1091500",
        "title": "Cyberpunk 2077 - Original Release",
        "hero_image_url": "https://cdn.steam.com/cp2077_v1.jpg",
        "genres": ["RPG", "Action"],
        "tags": ["Open World", "Cyberpunk", "Sci-Fi"],
        "player_modes": ["Single-player"],
    }

    with patch("app.services.discovery_service.DiscoveryService.get_game_by_steam_id", return_value=initial_catalog_entry):
        client.post(
            f"/api/projects/{project_id}/inspirations",
            json={"steam_app_id": "1091500"},
            headers=_auth(token_a),
        )

    # Mutate the mock catalog to represent a future catalog update/re-indexing
    updated_catalog_entry = {
        "id": "1091500",
        "title": "Cyberpunk 2077: Phantom Liberty Edition (Updated)",
        "hero_image_url": "https://cdn.steam.com/cp2077_v2_phantom.jpg",
        "genres": ["Action", "Adventure", "RPG"],
        "tags": ["Story Rich", "Futuristic", "Updated Tags"],
        "player_modes": ["Single-player"],
    }

    with patch("app.services.discovery_service.DiscoveryService.get_game_by_steam_id", return_value=updated_catalog_entry):
        list_res = client.get(f"/api/projects/{project_id}/inspirations", headers=_auth(token_a))

    assert list_res.status_code == 200
    insp = list_res.json()["inspirations"][0]
    # Snapshot MUST retain the original attached metadata, not the mutated catalog
    assert insp["title"] == "Cyberpunk 2077 - Original Release"
    assert insp["coverUrl"] == "https://cdn.steam.com/cp2077_v1.jpg"
    assert insp["genres"] == ["RPG", "Action"]
    assert insp["tags"] == ["Open World", "Cyberpunk", "Sci-Fi"]


# ─── CONCURRENCY RACE SAFETY ──────────────────────────────────────────────────

def test_database_unique_constraint_enforces_single_row(client):
    """
    Directly tests that database unique constraint uq_project_inspirations_project_game
    enforces race safety and prevents duplicate records.
    """
    token_a, user_a_id = _register_and_token(client, "user_a@example.com", "UserA")
    project_id = _create_project_in_db(user_a_id)

    db1 = TestingSessionLocal()
    db2 = TestingSessionLocal()

    try:
        rec1 = ProjectInspiration(
            project_id=project_id,
            steam_app_id="570",
            title="Dota 2 - Thread 1",
            genres=["MOBA"],
            tags=[],
            player_modes=[],
        )
        rec2 = ProjectInspiration(
            project_id=project_id,
            steam_app_id="570",
            title="Dota 2 - Thread 2",
            genres=["MOBA"],
            tags=[],
            player_modes=[],
        )

        db1.add(rec1)
        db1.commit()

        db2.add(rec2)
        with pytest.raises(Exception):
            db2.commit()
        db2.rollback()

        # Database MUST contain exactly ONE row
        rows = db1.query(ProjectInspiration).filter(
            ProjectInspiration.project_id == project_id,
            ProjectInspiration.steam_app_id == "570",
        ).all()
        assert len(rows) == 1
        assert rows[0].title == "Dota 2 - Thread 1"
    finally:
        db1.close()
        db2.close()


def test_concurrent_api_duplicate_attachment_race(client):
    """
    API-level concurrent race test:
    Two simultaneous POST requests for the same (project_id, steam_app_id).
    Expected invariant:
      - exactly one 201 Created
      - exactly one 409 Conflict
      - exactly one persisted row in the database
    """
    from concurrent.futures import ThreadPoolExecutor

    token_a, user_a_id = _register_and_token(client, "user_a_race@example.com", "UserARace")
    project_id = _create_project_in_db(user_a_id)

    def make_post_request():
        res = client.post(
            f"/api/projects/{project_id}/inspirations",
            json={"steam_app_id": "570"},
            headers=_auth(token_a),
        )
        return res.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(make_post_request)
        f2 = executor.submit(make_post_request)
        results = [f1.result(), f2.result()]

    assert sorted(results) == [201, 409], f"Unexpected status codes: {results}"

    db = TestingSessionLocal()
    try:
        rows = db.query(ProjectInspiration).filter(
            ProjectInspiration.project_id == project_id,
            ProjectInspiration.steam_app_id == "570",
        ).all()
        assert len(rows) == 1
    finally:
        db.close()
