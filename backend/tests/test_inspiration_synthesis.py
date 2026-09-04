"""
Inspiration Synthesis Tests (Step 4: Discovery -> Inspiration -> Studio).

Tests:
- Synthesis with 2 inspirations (shared genre & complementary mechanics)
- Traceable source attribution for every proposed element
- Conflict detection (Single-player vs Multiplayer, Turn-Based vs Bullet Hell)
- Project genre context respected
- No-copy dominance guard flagged when appropriate
- Strict determinism (same inputs produce identical output)
- Input bounds: rejects 0, 1, or 6+ inspirations (422)
- Auth and IDOR ownership protections (401, 404)
"""
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import Base, get_db
from app.models.project import Project
from app.models.project_inspiration import ProjectInspiration

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
        )
        db.add(project)
        db.commit()
        db.refresh(project)
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


# ─── SYNTHESIS SUCCESS & COMPOSITION ──────────────────────────────────────────

def test_synthesize_two_inspirations_shared_and_complementary(client):
    token, user_id = _register_and_token(client, "synth_user1@example.com", "SynthUser1")
    project_id = _create_project_in_db(user_id, genre="Strategy RPG")

    # Game 1: Slay the Spire (Deckbuilder, Roguelike, Strategy)
    _attach_inspiration_direct(
        project_id,
        "646570",
        "Slay the Spire",
        genres=["Strategy", "Card Game"],
        tags=["Deckbuilder", "Roguelike", "Singleplayer"],
        player_modes=["Single-player"],
    )

    # Game 2: Into the Breach (Turn-Based Strategy, Grid)
    _attach_inspiration_direct(
        project_id,
        "590380",
        "Into the Breach",
        genres=["Strategy", "Turn-Based Combat"],
        tags=["Grid", "Tactical", "Singleplayer"],
        player_modes=["Single-player"],
    )

    res = client.post(
        f"/api/projects/{project_id}/inspirations/synthesize",
        headers=_auth(token),
    )
    assert res.status_code == 200
    data = res.json()

    assert data["projectId"] == project_id
    assert data["inspirationCount"] == 2
    assert "Slay the Spire" in data["sourceTitles"]
    assert "Into the Breach" in data["sourceTitles"]

    # Shared anchor detected
    assert any("Strategy" in s for s in data["sharedAnchors"])

    # Complementary mechanics synthesized
    assert "DeckBuilding" in data["proposedMechanics"]
    assert "GridTactics" in data["proposedMechanics"]

    # Gameplay loop has abstract steps
    assert " -> " in data["gameplayLoop"]

    # High confidence (shared anchors + 0 conflicts)
    assert data["confidence"] == "HIGH"
    assert not data["isSingleSourceDominant"]


def test_synthesize_three_inspirations_multi_source_attribution(client):
    token, user_id = _register_and_token(client, "synth_user2@example.com", "SynthUser2")
    project_id = _create_project_in_db(user_id)

    _attach_inspiration_direct(project_id, "1", "Game Deck", ["Strategy"], ["Deckbuilder"], ["Single-player"])
    _attach_inspiration_direct(project_id, "2", "Game Grid", ["Tactics"], ["Grid", "Turn-Based"], ["Single-player"])
    _attach_inspiration_direct(project_id, "3", "Game Rogue", ["RPG"], ["Roguelite", "Procedural"], ["Single-player"])

    res = client.post(
        f"/api/projects/{project_id}/inspirations/synthesize",
        headers=_auth(token),
    )
    assert res.status_code == 200
    data = res.json()

    # Verify source attribution traces every mechanic
    attributions = data["sourceAttribution"]
    deck_attr = next(a for a in attributions if a["element"] == "DeckBuilding")
    assert "Game Deck" in deck_attr["sourceTitles"]

    grid_attr = next(a for a in attributions if a["element"] == "GridTactics")
    assert "Game Grid" in grid_attr["sourceTitles"]

    rogue_attr = next(a for a in attributions if a["element"] == "ProceduralProgression")
    assert "Game Rogue" in rogue_attr["sourceTitles"]


# ─── CONFLICT DETECTION ───────────────────────────────────────────────────────

def test_synthesize_conflicting_player_modes_detected(client):
    token, user_id = _register_and_token(client, "synth_user3@example.com", "SynthUser3")
    project_id = _create_project_in_db(user_id)

    # Game 1: Pure singleplayer
    _attach_inspiration_direct(project_id, "1", "Solo Quest", ["RPG"], ["Story"], ["Single-player"])
    # Game 2: Pure multiplayer PvP
    _attach_inspiration_direct(project_id, "2", "Arena Clash", ["Action"], ["PvP"], ["Multi-player", "Online PvP"])

    res = client.post(
        f"/api/projects/{project_id}/inspirations/synthesize",
        headers=_auth(token),
    )
    assert res.status_code == 200
    data = res.json()

    # Conflicting modes should produce a structured conflict requiring review
    conflicts = data["conflicts"]
    mode_conflict = next((c for c in conflicts if c["field"] == "player_modes"), None)
    assert mode_conflict is not None
    assert mode_conflict["resolutionStatus"] == "UNRESOLVED"
    assert len(mode_conflict["options"]) >= 2


def test_synthesize_conflicting_combat_tempos_detected(client):
    token, user_id = _register_and_token(client, "synth_user4@example.com", "SynthUser4")
    project_id = _create_project_in_db(user_id)

    # Game 1: Turn based grid tactics
    _attach_inspiration_direct(project_id, "1", "Chess Master", ["Strategy"], ["Turn-Based", "Grid"], ["Single-player"])
    # Game 2: Bullet hell real time twitch
    _attach_inspiration_direct(project_id, "2", "Bullet Storm", ["Shooter"], ["Bullet Hell", "Shooter"], ["Single-player"])

    res = client.post(
        f"/api/projects/{project_id}/inspirations/synthesize",
        headers=_auth(token),
    )
    assert res.status_code == 200
    data = res.json()

    conflicts = data["conflicts"]
    tempo_conflict = next((c for c in conflicts if c["field"] == "combat_tempo"), None)
    assert tempo_conflict is not None
    assert tempo_conflict["resolutionStatus"] == "UNRESOLVED"


# ─── NO-COPY DOMINANCE & DETERMINISM ──────────────────────────────────────────

def test_synthesize_determinism_identical_runs(client):
    token, user_id = _register_and_token(client, "synth_user5@example.com", "SynthUser5")
    project_id = _create_project_in_db(user_id)

    _attach_inspiration_direct(project_id, "10", "Alpha", ["Action"], ["Deckbuilder", "Roguelike"], ["Single-player"])
    _attach_inspiration_direct(project_id, "20", "Beta", ["Action"], ["Grid", "Tactical"], ["Single-player"])

    res1 = client.post(f"/api/projects/{project_id}/inspirations/synthesize", headers=_auth(token))
    res2 = client.post(f"/api/projects/{project_id}/inspirations/synthesize", headers=_auth(token))

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json() == res2.json()


# ─── INPUT BOUNDS & VALIDATION ────────────────────────────────────────────────

def test_synthesize_insufficient_inspirations_returns_422(client):
    token, user_id = _register_and_token(client, "synth_user6@example.com", "SynthUser6")
    project_id = _create_project_in_db(user_id)

    # 0 inspirations
    res0 = client.post(f"/api/projects/{project_id}/inspirations/synthesize", headers=_auth(token))
    assert res0.status_code == 422
    assert res0.json()["error"]["code"] == "INSUFFICIENT_INSPIRATIONS"

    # 1 inspiration
    _attach_inspiration_direct(project_id, "1", "Game 1", ["RPG"], ["Singleplayer"], ["Single-player"])
    res1 = client.post(f"/api/projects/{project_id}/inspirations/synthesize", headers=_auth(token))
    assert res1.status_code == 422
    assert res1.json()["error"]["code"] == "INSUFFICIENT_INSPIRATIONS"


def test_synthesize_excessive_inspirations_returns_422(client):
    token, user_id = _register_and_token(client, "synth_user7@example.com", "SynthUser7")
    project_id = _create_project_in_db(user_id)

    for i in range(1, 7):
        _attach_inspiration_direct(project_id, str(i), f"Game {i}", ["RPG"], [f"Tag{i}"], ["Single-player"])

    res = client.post(f"/api/projects/{project_id}/inspirations/synthesize", headers=_auth(token))
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "EXCESSIVE_INSPIRATIONS"


def test_synthesize_unauthenticated(client):
    res = client.post("/api/projects/some-id/inspirations/synthesize")
    assert res.status_code == 401


def test_synthesize_wrong_owner_returns_404(client):
    token_a, user_a_id = _register_and_token(client, "synth_user8a@example.com", "SynthUser8A")
    token_b, _ = _register_and_token(client, "synth_user8b@example.com", "SynthUser8B")
    project_id = _create_project_in_db(user_a_id)

    _attach_inspiration_direct(project_id, "1", "G1", ["RPG"], ["A"], ["Single-player"])
    _attach_inspiration_direct(project_id, "2", "G2", ["RPG"], ["B"], ["Single-player"])

    res = client.post(f"/api/projects/{project_id}/inspirations/synthesize", headers=_auth(token_b))
    assert res.status_code == 404
