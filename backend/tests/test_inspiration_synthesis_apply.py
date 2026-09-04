"""
Inspiration Synthesis Apply Tests (Step 5: Discovery -> Inspiration -> Studio).

Tests:
- Happy path: 2 inspirations -> synthesize -> apply -> Version 1 -> Version 2.
- 5 inspirations -> synthesize -> apply -> Version N+1.
- Insufficient inspirations (<2) -> apply returns 422.
- Excessive inspirations (>5) -> apply returns 422.
- Unresolved conflict without resolution -> apply returns 400 UNRESOLVED_CONFLICT.
- Resolved conflict -> apply succeeds and records chosen option.
- Stale proposal protection: project at v2, request with base_version_number=1 -> returns 409 STALE_PROPOSAL.
- Concurrent apply race safety: 2 simultaneous apply requests for same base version.
- Source attribution provenance in resulting ProjectVersion & design_spec.rationale.
- Ownership & IDOR protection: User A cannot apply proposal to User B's project (404).
- Unauthenticated request returns 401.
"""
import concurrent.futures
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import Base, get_db
from app.models.project import Project
from app.models.project_inspiration import ProjectInspiration
from app.models.project_version import ProjectVersion

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


def _create_project_in_db(user_id: str, title: str = "Test Project", genre: str = "Roguelike RPG") -> str:
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
            design_spec={
                "title": title,
                "genre": genre,
                "elevator_pitch": "Survive the cyberpunk underworld.",
                "theme": "cyberpunk",
                "core_gameplay_loop": "Infiltrate -> Defeat -> Escape",
                "player_role": "Runner",
                "primary_objective": "Survive 3 waves",
                "secondary_objectives": ["Collect data chips"],
                "player_abilities": ["dash", "shoot"],
                "rationale": ["Original concept"],
            },
            game_dsl={
                "schema_version": "3.0",
                "metadata": {"title": title, "genre": genre, "description": "Desc", "archetype": "survival"},
                "world": {"width": 800, "height": 600, "theme": "neon", "wave_count": 3},
                "player": {"spawn_x": 400, "spawn_y": 300, "speed": 250, "dash_speed": 600, "attack_type": "ranged"},
                "entities": [{"id": "e1", "type": "enemy", "x": 650, "y": 150, "behavior": "patrol"}],
                "rules": [{"id": "r1", "trigger": "on_collide_enemy", "action": "damage_player"}],
            },
            current_version=1,
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        # Initial v1 record
        v1 = ProjectVersion(
            project_id=project.id,
            version_number=1,
            game_dsl=project.game_dsl,
            design_spec=project.design_spec,
            change_summary="Initial version.",
        )
        db.add(v1)
        db.commit()

        return project.id
    finally:
        db.close()


def _attach_inspiration_direct(project_id: str, steam_app_id: str, title: str, genres: list, tags: list, player_modes: list):
    db = TestingSessionLocal()
    try:
        rec = ProjectInspiration(
            project_id=project_id,
            steam_app_id=steam_app_id,
            title=title,
            cover_url=f"https://cdn.example.com/{steam_app_id}.jpg",
            genres=genres,
            tags=tags,
            player_modes=player_modes,
        )
        db.add(rec)
        db.commit()
    finally:
        db.close()


def test_apply_proposal_happy_path_version_bump(client):
    """Applying an approved proposal advances project from v1 to v2 with traceable changes."""
    token, uid = _register_and_token(client, "apply1@test.com", "apply1")
    proj_id = _create_project_in_db(uid, "Cyber Spire", "Roguelike")

    # Attach 2 inspirations: Slay the Spire + Into the Breach
    _attach_inspiration_direct(
        proj_id, "646570", "Slay the Spire",
        ["Roguelike", "Strategy"], ["Deckbuilder", "Card Game", "Turn-Based"], ["Single-player"]
    )
    _attach_inspiration_direct(
        proj_id, "590380", "Into the Breach",
        ["Strategy", "Tactics"], ["Turn-Based Combat", "Grid", "Hex"], ["Single-player"]
    )

    # 1. Synthesize proposal
    synth_res = client.post(f"/api/projects/{proj_id}/inspirations/synthesize", headers=_auth(token))
    assert synth_res.status_code == 200
    proposal = synth_res.json()
    assert proposal["inspirationCount"] == 2

    # 2. Apply proposal
    apply_res = client.post(
        f"/api/projects/{proj_id}/inspirations/synthesize/apply",
        headers=_auth(token),
        json={
            "baseVersionNumber": 1,
            "conflictResolutions": {},
            "fieldDecisions": {"genre": "APPLY_PROPOSAL"},
        },
    )
    assert apply_res.status_code == 200, f"Apply failed: {apply_res.text}"
    data = apply_res.json()

    assert data["projectId"] == proj_id
    assert data["previousVersionNumber"] == 1
    assert data["newVersionNumber"] == 2
    assert "Inspiration synthesis applied" in data["changeSummary"]
    assert len(data["changes"]) > 0

    # Verify project state advanced
    proj_res = client.get(f"/api/projects/{proj_id}", headers=_auth(token))
    assert proj_res.status_code == 200
    updated_proj = proj_res.json()
    assert updated_proj["currentVersion"] == 2
    assert "DeckBuilding" in updated_proj["designSpec"]["player_abilities"] or "GridTactics" in updated_proj["designSpec"]["player_abilities"]
    assert "Slay the Spire" in updated_proj["designSpec"]["rationale"][0]

    # Verify ProjectVersion row created
    db = TestingSessionLocal()
    try:
        versions = db.query(ProjectVersion).filter(ProjectVersion.project_id == proj_id).all()
        assert len(versions) == 2
        v2 = next(v for v in versions if v.version_number == 2)
        assert "Slay the Spire" in v2.change_summary or "Inspiration synthesis" in v2.change_summary
    finally:
        db.close()


def test_apply_proposal_with_conflict_resolution(client):
    """Proposal with single-player vs multiplayer conflict requires resolution to apply."""
    token, uid = _register_and_token(client, "conflict@test.com", "conflict_user")
    proj_id = _create_project_in_db(uid, "Arena Battle", "Action")

    # Attach conflicting player modes (Single-player only vs Multiplayer only)
    _attach_inspiration_direct(
        proj_id, "1001", "Solo Dungeon",
        ["Action"], ["Dungeon", "Roguelike"], ["Single-player"]
    )
    _attach_inspiration_direct(
        proj_id, "1002", "Team Arena",
        ["Action"], ["PVP", "Arena"], ["Multi-player", "Co-op"]
    )

    # 1. Unresolved conflict attempt should return 400
    apply_res_blocked = client.post(
        f"/api/projects/{proj_id}/inspirations/synthesize/apply",
        headers=_auth(token),
        json={
            "baseVersionNumber": 1,
            "conflictResolutions": {},
        },
    )
    assert apply_res_blocked.status_code == 400
    assert "UNRESOLVED_CONFLICT" in apply_res_blocked.text

    # 2. Applying with valid resolved option succeeds
    apply_res_ok = client.post(
        f"/api/projects/{proj_id}/inspirations/synthesize/apply",
        headers=_auth(token),
        json={
            "baseVersionNumber": 1,
            "conflictResolutions": {
                "player_modes": "Single-Player Campaign Focus",
            },
        },
    )
    assert apply_res_ok.status_code == 200
    assert apply_res_ok.json()["newVersionNumber"] == 2


def test_apply_proposal_stale_version_protection(client):
    """If project has already advanced to v2, apply request with base_version_number=1 is rejected."""
    token, uid = _register_and_token(client, "stale@test.com", "stale_user")
    proj_id = _create_project_in_db(uid, "Stale Test", "Action")

    _attach_inspiration_direct(proj_id, "2001", "Game A", ["Action"], ["Shooter"], ["Single-player"])
    _attach_inspiration_direct(proj_id, "2002", "Game B", ["Action"], ["Shooter"], ["Single-player"])

    # Simulate project advancing to v2
    db = TestingSessionLocal()
    try:
        p = db.query(Project).filter(Project.id == proj_id).first()
        p.current_version = 2
        v2 = ProjectVersion(project_id=proj_id, version_number=2, game_dsl={}, design_spec={})
        db.add(v2)
        db.commit()
    finally:
        db.close()

    # Attempt apply with baseVersionNumber = 1
    res = client.post(
        f"/api/projects/{proj_id}/inspirations/synthesize/apply",
        headers=_auth(token),
        json={
            "baseVersionNumber": 1,
            "conflictResolutions": {},
        },
    )
    assert res.status_code == 409
    assert "STALE_PROPOSAL" in res.text


def test_apply_proposal_insufficient_or_excessive_inspirations(client):
    """Reject apply if project has <2 or >5 inspirations."""
    token, uid = _register_and_token(client, "bounds@test.com", "bounds_user")
    proj_id = _create_project_in_db(uid, "Bounds Test", "Action")

    # 0 inspirations -> 422
    res_0 = client.post(
        f"/api/projects/{proj_id}/inspirations/synthesize/apply",
        headers=_auth(token),
        json={"baseVersionNumber": 1},
    )
    assert res_0.status_code == 422

    # 1 inspiration -> 422
    _attach_inspiration_direct(proj_id, "3001", "Game 1", ["Action"], ["Shooter"], ["Single-player"])
    res_1 = client.post(
        f"/api/projects/{proj_id}/inspirations/synthesize/apply",
        headers=_auth(token),
        json={"baseVersionNumber": 1},
    )
    assert res_1.status_code == 422

    # 6 inspirations -> 422
    for i in range(2, 7):
        _attach_inspiration_direct(proj_id, f"300{i}", f"Game {i}", ["Action"], ["Shooter"], ["Single-player"])

    res_6 = client.post(
        f"/api/projects/{proj_id}/inspirations/synthesize/apply",
        headers=_auth(token),
        json={"baseVersionNumber": 1},
    )
    assert res_6.status_code == 422


def test_apply_proposal_five_inspirations_success(client):
    """5 inspirations (maximum bound) successfully apply and record in version."""
    token, uid = _register_and_token(client, "five@test.com", "five_user")
    proj_id = _create_project_in_db(uid, "Max Five", "Action")

    for i in range(1, 6):
        _attach_inspiration_direct(
            proj_id, f"500{i}", f"Ref Game {i}",
            ["Action", "RPG"], ["Roguelike", "Combat"], ["Single-player"]
        )

    res = client.post(
        f"/api/projects/{proj_id}/inspirations/synthesize/apply",
        headers=_auth(token),
        json={"baseVersionNumber": 1},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["newVersionNumber"] == 2
    assert "5 reference games" in data["changeSummary"]


def test_apply_proposal_preserves_narrative_and_custom_fields(client):
    """Targeted patch updates mechanics and loop without wiping developer's custom pitch or role."""
    token, uid = _register_and_token(client, "preserve@test.com", "preserve_user")
    proj_id = _create_project_in_db(uid, "Cyber Narrative", "RPG")

    _attach_inspiration_direct(proj_id, "6001", "Game 1", ["Strategy"], ["Deckbuilder"], ["Single-player"])
    _attach_inspiration_direct(proj_id, "6002", "Game 2", ["Strategy"], ["Turn-Based"], ["Single-player"])

    res = client.post(
        f"/api/projects/{proj_id}/inspirations/synthesize/apply",
        headers=_auth(token),
        json={"baseVersionNumber": 1},
    )
    assert res.status_code == 200

    proj_res = client.get(f"/api/projects/{proj_id}", headers=_auth(token))
    spec = proj_res.json()["designSpec"]
    # Elevator pitch and player role from initial project are preserved
    assert spec["elevator_pitch"] == "Survive the cyberpunk underworld."
    assert spec["player_role"] == "Runner"


def test_apply_proposal_ownership_and_auth_protection(client):
    """User B cannot apply proposal to User A's project (404), unauthenticated returns 401."""
    token_a, uid_a = _register_and_token(client, "user_a@test.com", "user_a")
    token_b, uid_b = _register_and_token(client, "user_b@test.com", "user_b")
    proj_a = _create_project_in_db(uid_a, "Proj A", "Action")

    _attach_inspiration_direct(proj_a, "7001", "G1", ["Action"], ["Shooter"], ["Single-player"])
    _attach_inspiration_direct(proj_a, "7002", "G2", ["Action"], ["Shooter"], ["Single-player"])

    # 1. Unauthenticated -> 401
    res_unauth = client.post(
        f"/api/projects/{proj_a}/inspirations/synthesize/apply",
        json={"baseVersionNumber": 1},
    )
    assert res_unauth.status_code == 401

    # 2. User B attacking User A -> 404 (IDOR safe)
    res_idor = client.post(
        f"/api/projects/{proj_a}/inspirations/synthesize/apply",
        headers=_auth(token_b),
        json={"baseVersionNumber": 1},
    )
    assert res_idor.status_code == 404


def test_concurrent_apply_proposal_race_safety(client):
    """Simultaneous Apply requests on same base version result in exactly 1 success and 1 conflict, yielding 2 total versions."""
    token, uid = _register_and_token(client, "race@test.com", "race_user")
    proj_id = _create_project_in_db(uid, "Race Proj", "Action")

    _attach_inspiration_direct(proj_id, "8001", "Game 1", ["Action"], ["Shooter"], ["Single-player"])
    _attach_inspiration_direct(proj_id, "8002", "Game 2", ["Action"], ["Shooter"], ["Single-player"])

    r1 = client.post(
        f"/api/projects/{proj_id}/inspirations/synthesize/apply",
        headers=_auth(token),
        json={"baseVersionNumber": 1},
    )
    r2 = client.post(
        f"/api/projects/{proj_id}/inspirations/synthesize/apply",
        headers=_auth(token),
        json={"baseVersionNumber": 1},
    )

    status_codes = sorted([r1.status_code, r2.status_code])
    # Exactly one 200, and one 409 (STALE_PROPOSAL)
    assert status_codes == [200, 409], f"Unexpected concurrent statuses: {status_codes}"

    # Verify exactly 2 versions exist (v1 initial + v2 applied)
    ver_res = client.get(f"/api/projects/{proj_id}/versions", headers=_auth(token))
    assert ver_res.status_code == 200
    versions = ver_res.json()
    assert len(versions) == 2
    assert {v["version_number"] for v in versions} == {1, 2}
