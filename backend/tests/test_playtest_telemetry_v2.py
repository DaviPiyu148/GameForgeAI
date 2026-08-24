"""
Unit and integration tests for Playtest Telemetry & AI Analysis V1.

Verifies:
- Allowlisted telemetry event vocabulary and schema bounds
- Deterministic summary engine aggregation
- Session recording, retrieval, and listing
- Strict ownership isolation / IDOR protection
- Read-only AI analysis invariant (no auto-mutation of Game DSL)
"""
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.password import hash_password
from app.auth.tokens import create_access_token
from app.db.session import Base, get_db
from app.main import app
from app.models.project import Project
from app.models.user import User
from app.schemas.playtest import (
    ALLOWLISTED_TELEMETRY_EVENTS,
    PlaytestCreate,
    TelemetryEventSchema,
)
from app.services.playtest_summary import PlaytestSummaryEngine


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
def test_context():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    db = TestingSessionLocal()
    try:
        # Create User A & Project A
        user_a = User(
            email="telemetry_user_a@example.com",
            username="telemetry_user_a",
            password_hash=hash_password("ValidPass123!"),
        )
        db.add(user_a)
        db.commit()
        db.refresh(user_a)

        token_a = create_access_token(user_a.id)

        proj_a = Project(
            user_id=user_a.id,
            title="User A Game",
            prompt="Survival arena prototype",
            status="PLAYABLE",
            game_dsl={
                "schema_version": "2.0",
                "metadata": {"title": "User A Game", "genre": "Action", "description": "Survival", "archetype": "survival"},
                "player": {"spawn_x": 400, "spawn_y": 300, "speed": 250, "max_health": 100},
                "entities": [],
                "rules": [],
            },
            current_version=1,
        )
        db.add(proj_a)
        db.commit()
        db.refresh(proj_a)

        # Create User B & Project B
        user_b = User(
            email="telemetry_user_b@example.com",
            username="telemetry_user_b",
            password_hash=hash_password("ValidPass123!"),
        )
        db.add(user_b)
        db.commit()
        db.refresh(user_b)

        token_b = create_access_token(user_b.id)

        proj_b = Project(
            user_id=user_b.id,
            title="User B Game",
            prompt="Platformer prototype",
            status="PLAYABLE",
            game_dsl={
                "schema_version": "2.0",
                "metadata": {"title": "User B Game", "genre": "Platformer", "description": "Jump", "archetype": "platformer"},
                "player": {"spawn_x": 100, "spawn_y": 400, "speed": 200},
                "entities": [],
                "rules": [],
            },
            current_version=1,
        )
        db.add(proj_b)
        db.commit()
        db.refresh(proj_b)

        with TestClient(app) as client:
            yield client, user_a, token_a, proj_a, user_b, token_b, proj_b
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 1. Telemetry Event Schema & Allowlist Validation
# -----------------------------------------------------------------------------

def test_allowlisted_telemetry_events_pass_validation():
    """Verify all allowlisted telemetry events are parsed cleanly."""
    for ev_type in ALLOWLISTED_TELEMETRY_EVENTS:
        ev = TelemetryEventSchema(type=ev_type, timestamp=1000, data={"test": 123})
        assert ev.type == ev_type.upper()


def test_unallowlisted_event_type_rejected():
    """Verify arbitrary unallowlisted event strings are rejected."""
    with pytest.raises(ValidationError):
        TelemetryEventSchema(type="ARBITRARY_UNTRUSTED_EVENT", timestamp=1000)


def test_script_injection_in_telemetry_payload_blocked():
    """Verify script injection in telemetry payload dictionary is blocked."""
    with pytest.raises(ValidationError):
        TelemetryEventSchema(
            type="PLAYER_DAMAGE",
            timestamp=1000,
            data={"attacker": "<script>alert(1)</script>"},
        )


def test_telemetry_event_count_capped():
    """Verify playtest payload caps events at 150 items."""
    events = [
        {"type": "PLAYER_DAMAGE", "timestamp": i * 100, "data": {"damage": 5}}
        for i in range(200)
    ]
    payload = PlaytestCreate(
        duration_seconds=30,
        score=100,
        outcome="LOST",
        telemetry_events=events,
    )
    assert len(payload.telemetry_events) == 150


# -----------------------------------------------------------------------------
# 2. Deterministic Playtest Summary Engine
# -----------------------------------------------------------------------------

def test_deterministic_summary_engine_aggregation():
    """Verify PlaytestSummaryEngine deterministically computes metrics from event stream."""
    events = [
        {"type": "SESSION_STARTED", "timestamp": 1000},
        {"type": "WAVE_STARTED", "timestamp": 2000, "data": {"wave": 1}},
        {"type": "PLAYER_DAMAGED", "timestamp": 3000, "data": {"damage": 15}},
        {"type": "ENEMY_DEFEATED", "timestamp": 4000, "data": {"damageDealt": 25}},
        {"type": "COLLECTIBLE_COLLECTED", "timestamp": 5000, "data": {"points": 50}},
        {"type": "WAVE_STARTED", "timestamp": 8000, "data": {"wave": 2}},
        {"type": "PHASE_STARTED", "timestamp": 8500, "data": {"phase": "MID"}},
        {"type": "OBJECTIVE_COMPLETED", "timestamp": 9000, "data": {"wave": 2}},
        {"type": "GAME_WON", "timestamp": 11000},
        {"type": "SESSION_ENDED", "timestamp": 11000, "data": {"outcome": "WON"}},
    ]

    summary = PlaytestSummaryEngine.aggregate(events=events)

    assert summary["duration_seconds"] == 10  # (11000 - 1000) / 1000
    assert summary["damage_taken"] == 15
    assert summary["damage_dealt"] == 25
    assert summary["enemies_defeated"] == 1
    assert summary["collectibles_gathered"] == 1
    assert summary["objectives_completed"] == 1
    assert summary["waves_reached"] == 2
    assert summary["phase_reached"] == "MID"
    assert summary["outcome"] == "WON"
    assert summary["score"] == 50


def test_client_declared_score_never_overrides_event_derived_score():
    """Security: a forged client-declared score must NOT alter the authoritative score."""
    events = [
        {"type": "SESSION_STARTED", "timestamp": 1000},
        {"type": "COLLECTIBLE_COLLECTED", "timestamp": 2000, "data": {"points": 50}},
        {"type": "SESSION_ENDED", "timestamp": 3000},
    ]
    summary = PlaytestSummaryEngine.aggregate(events=events, declared_score=999999)
    assert summary["score"] == 50  # purely event-derived, declared_score ignored


def test_score_changed_event_cannot_inflate_authoritative_score():
    """Security: a forged SCORE_CHANGED event must not override the derived score."""
    events = [
        {"type": "SESSION_STARTED", "timestamp": 1000},
        {"type": "COLLECTIBLE_COLLECTED", "timestamp": 2000, "data": {"points": 50}},
        {"type": "SCORE_CHANGED", "timestamp": 2500, "data": {"score": 999999}},
        {"type": "SESSION_ENDED", "timestamp": 3000},
    ]
    summary = PlaytestSummaryEngine.aggregate(events=events)
    assert summary["score"] == 50


def test_empty_event_stream_never_trusts_declared_score():
    """Security: with zero events, there is no evidence to support a nonzero score."""
    summary = PlaytestSummaryEngine.aggregate(events=[], declared_score=500)
    assert summary["score"] == 0


def test_per_event_damage_and_points_are_clamped():
    """Security: a single forged event cannot contribute unbounded damage/points."""
    events = [
        {"type": "SESSION_STARTED", "timestamp": 1000},
        {"type": "PLAYER_DAMAGED", "timestamp": 1500, "data": {"damage": 10_000_000}},
        {"type": "COLLECTIBLE_COLLECTED", "timestamp": 2000, "data": {"points": 10_000_000}},
        {"type": "SESSION_ENDED", "timestamp": 3000},
    ]
    summary = PlaytestSummaryEngine.aggregate(events=events)
    assert summary["damage_taken"] <= 500
    assert summary["score"] <= 1000


def test_legitimate_event_sequence_produces_expected_score():
    """A normal, non-adversarial event sequence still aggregates deterministically."""
    events = [
        {"type": "SESSION_STARTED", "timestamp": 0},
        {"type": "COLLECTIBLE_COLLECTED", "timestamp": 1000, "data": {"points": 50}},
        {"type": "COLLECTIBLE_COLLECTED", "timestamp": 2000, "data": {"points": 50}},
        {"type": "ENEMY_DEFEATED", "timestamp": 3000, "data": {"damageDealt": 25}},
        {"type": "SESSION_ENDED", "timestamp": 4000},
    ]
    summary = PlaytestSummaryEngine.aggregate(events=events)
    assert summary["score"] == 100
    assert summary["collectibles_gathered"] == 2
    assert summary["enemies_defeated"] == 1


# -----------------------------------------------------------------------------
# 3. Session Recording, Retrieval, and IDOR Ownership Isolation
# -----------------------------------------------------------------------------

def test_record_and_retrieve_playtest_session(test_context):
    """Verify recording and retrieving playtest sessions for authenticated project owner."""
    client, user_a, token_a, proj_a, _, _, _ = test_context
    headers = {"Authorization": f"Bearer {token_a}"}

    playtest_payload = {
        "duration_seconds": 45,
        "score": 300,
        "damage_taken": 20,
        "enemies_defeated": 4,
        "outcome": "WON",
        "telemetry_events": [
            {"type": "SESSION_STARTED", "timestamp": 1000},
            {"type": "ENEMY_DEFEATED", "timestamp": 5000, "data": {"damageDealt": 30}},
            {"type": "GAME_WON", "timestamp": 46000},
        ],
    }

    # 1. Record session
    create_res = client.post(
        f"/api/projects/{proj_a.id}/playtests",
        json=playtest_payload,
        headers=headers,
    )
    assert create_res.status_code == 201
    session_data = create_res.json()
    session_id = session_data["id"]
    assert session_data["project_id"] == proj_a.id
    assert session_data["outcome"] == "WON"

    # 2. Retrieve single session by ID
    get_res = client.get(
        f"/api/projects/{proj_a.id}/playtests/{session_id}",
        headers=headers,
    )
    assert get_res.status_code == 200
    assert get_res.json()["id"] == session_id

    # 3. List sessions
    list_res = client.get(
        f"/api/projects/{proj_a.id}/playtests",
        headers=headers,
    )
    assert list_res.status_code == 200
    sessions = list_res.json()
    assert len(sessions) == 1
    assert sessions[0]["id"] == session_id


def test_idor_protection_on_playtest_sessions(test_context):
    """Verify User B cannot access or record playtest sessions on User A's project."""
    client, user_a, token_a, proj_a, user_b, token_b, proj_b = test_context

    # 1. User A records a session on Project A
    headers_a = {"Authorization": f"Bearer {token_a}"}
    create_res = client.post(
        f"/api/projects/{proj_a.id}/playtests",
        json={"duration_seconds": 30, "score": 100, "outcome": "LOST"},
        headers=headers_a,
    )
    assert create_res.status_code == 201
    session_a_id = create_res.json()["id"]

    # 2. User B attempts to access User A's session -> 404
    headers_b = {"Authorization": f"Bearer {token_b}"}
    unauthorized_get = client.get(
        f"/api/projects/{proj_a.id}/playtests/{session_a_id}",
        headers=headers_b,
    )
    assert unauthorized_get.status_code == 404

    # 3. User B attempts to list User A's playtests -> 404
    unauthorized_list = client.get(
        f"/api/projects/{proj_a.id}/playtests",
        headers=headers_b,
    )
    assert unauthorized_list.status_code == 404

    # 4. User B attempts to record playtest on User A's project -> 404
    unauthorized_create = client.post(
        f"/api/projects/{proj_a.id}/playtests",
        json={"duration_seconds": 10, "score": 0, "outcome": "ABANDONED"},
        headers=headers_b,
    )
    assert unauthorized_create.status_code == 404


def test_analyze_playtest_rejects_session_from_a_different_project(test_context):
    """
    IDOR regression: a session belonging to Project A must not be analyzable through
    a DIFFERENT project the same user owns (Project C below), even though both are
    owned by the same authenticated user. analyze_playtest_session must scope the
    session lookup by project_id, not just user_id.
    """
    client, user_a, token_a, proj_a, _, _, _ = test_context
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # User A creates a second project, Project C, owned by the same user.
    from app.models.project import Project as ProjectModel
    db = TestingSessionLocal()
    try:
        proj_c = ProjectModel(
            user_id=user_a.id,
            title="User A Second Game",
            prompt="Another prototype",
            status="PLAYABLE",
            game_dsl={
                "schema_version": "2.0",
                "metadata": {"title": "User A Second Game", "genre": "Action", "description": "D", "archetype": "survival"},
                "player": {"spawn_x": 400, "spawn_y": 300, "speed": 250, "max_health": 100},
                "entities": [],
                "rules": [],
            },
            current_version=1,
        )
        db.add(proj_c)
        db.commit()
        db.refresh(proj_c)
        proj_c_id = proj_c.id
    finally:
        db.close()

    # A session is recorded against Project A.
    rec_res = client.post(
        f"/api/projects/{proj_a.id}/playtests",
        json={"duration_seconds": 30, "score": 10, "outcome": "LOST"},
        headers=headers_a,
    )
    assert rec_res.status_code == 201
    session_a_id = rec_res.json()["id"]

    # Analyzing that session through Project C (a different, but same-user, project)
    # must fail — session.project_id != requested project.id.
    cross_project_res = client.post(
        f"/api/projects/{proj_c_id}/analyze-playtest",
        json={"session_id": session_a_id},
        headers=headers_a,
    )
    assert cross_project_res.status_code == 404


# -----------------------------------------------------------------------------
# 4. Read-Only AI Playtest Critique Invariant
# -----------------------------------------------------------------------------

def test_ai_analysis_is_read_only(test_context):
    """Verify AI playtest analysis does NOT modify Project.game_dsl or bump version."""
    client, user_a, token_a, proj_a, _, _, _ = test_context
    headers = {"Authorization": f"Bearer {token_a}"}

    # Record playtest
    rec_res = client.post(
        f"/api/projects/{proj_a.id}/playtests",
        json={
            "duration_seconds": 25,
            "score": 50,
            "damage_taken": 80,
            "outcome": "LOST",
            "telemetry_events": [
                {"type": "SESSION_STARTED", "timestamp": 1000},
                {"type": "PLAYER_DAMAGED", "timestamp": 5000, "data": {"damage": 40}},
                {"type": "PLAYER_DAMAGED", "timestamp": 15000, "data": {"damage": 40}},
                {"type": "PLAYER_DIED", "timestamp": 26000},
            ],
        },
        headers=headers,
    )
    assert rec_res.status_code == 201
    session_id = rec_res.json()["id"]

    from unittest.mock import AsyncMock, patch
    from app.schemas.playtest import PlaytestAnalysisResponse

    mock_analysis = PlaytestAnalysisResponse(
        fun_rating=8,
        difficulty_rating=6,
        clarity_rating=9,
        strengths=["Responsive controls", "Engaging progression"],
        problems=[],
        recommendations=[
            {
                "id": "rec_1",
                "category": "mobility",
                "description": "Increase player speed",
                "dsl_change_type": "player_speed",
                "suggested_patch": {"player": {"speed": 280}},
            }
        ],
    )

    # Trigger AI critique (mocked for offline test hermeticity)
    with patch("app.services.project_service.project_service.analyze_playtest_session", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = mock_analysis
        critique_res = client.post(
            f"/api/projects/{proj_a.id}/analyze-playtest",
            json={"session_id": session_id},
            headers=headers,
        )
        assert critique_res.status_code == 200
        critique = critique_res.json()
        assert "fun_rating" in critique
        assert "recommendations" in critique
        assert len(critique["recommendations"]) >= 1

    # Invariant: Verify project.game_dsl is untouched and version is STILL 1
    proj_res = client.get(f"/api/projects/{proj_a.id}", headers=headers)
    assert proj_res.status_code == 200
    current_proj = proj_res.json()
    ver = current_proj.get("currentVersion", current_proj.get("current_version"))
    assert ver == 1
    dsl = current_proj.get("gameDsl") or current_proj.get("game_dsl")
    assert dsl["player"]["speed"] == 250
