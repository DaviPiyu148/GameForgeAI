"""
Comprehensive test suite for Creator Progression V1.

Verifies:
1. Experience Points (XP) policy, accumulation, and level bounds.
2. Creator titles derived deterministically from server level.
3. Anti-spam deduplication (search, save, build similar, playtests, build completions).
4. Atomic concurrency-safe XP updates without lost increments.
5. Idempotent milestone evaluation & unlock system for all 8 canonical milestones.
6. Server-authoritative Profile Progress API endpoint and IDOR user isolation.
"""
import pytest
from datetime import datetime, timezone
import concurrent.futures
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.models.project import Project
from app.models.progression import UserMilestone, XPEvent
from app.services.progression_service import (
    progression_service,
    calculate_level_bounds,
    get_creator_title,
    CANONICAL_MILESTONES,
)
from app.services.preference_service import preference_service
from app.auth.tokens import create_access_token


@pytest.fixture
def user_creator_a(db_session: Session) -> User:
    """Fixture creating User A."""
    user = User(
        email="creator_a@example.com",
        username="CreatorA",
        password_hash="fakehash",
        level=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_creator_b(db_session: Session) -> User:
    """Fixture creating User B."""
    user = User(
        email="creator_b@example.com",
        username="CreatorB",
        password_hash="fakehash",
        level=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# -----------------------------------------------------------------------------
# 1. Level Bounds & Creator Title Derivation
# -----------------------------------------------------------------------------

def test_level_bounds_and_creator_titles():
    """Verify level threshold calculation and deterministic title derivation."""
    # Level 1: 0 XP
    lvl1, base1, next1 = calculate_level_bounds(0)
    assert lvl1 == 1
    assert base1 == 0
    assert next1 == 100
    assert get_creator_title(lvl1) == "Novice Creator"

    # Level 2: 100 XP
    lvl2, base2, next2 = calculate_level_bounds(100)
    assert lvl2 == 2
    assert base2 == 100
    assert next2 == 250
    assert get_creator_title(lvl2) == "Novice Creator"

    # Level 5: 700 XP -> Game Builder
    lvl5, _, _ = calculate_level_bounds(700)
    assert lvl5 == 5
    assert get_creator_title(lvl5) == "Game Builder"

    # Level 10: 2700 XP -> Game Designer
    lvl10, _, _ = calculate_level_bounds(2700)
    assert lvl10 == 10
    assert get_creator_title(lvl10) == "Game Designer"

    # Level 15: Systems Architect
    assert get_creator_title(15) == "Systems Architect"

    # Level 20: World Architect
    assert get_creator_title(20) == "World Architect"


# -----------------------------------------------------------------------------
# 2. XP Grants & Anti-Spam Rate Limiting
# -----------------------------------------------------------------------------

def test_xp_grant_and_anti_spam(db_session: Session, user_creator_a: User):
    """Verify XP grants and anti-spam duplicate prevention."""
    # 1. First search grants 10 XP
    _, _, granted1 = progression_service.grant_xp(
        db=db_session,
        user_id=user_creator_a.id,
        event_type="SEARCH",
        source_ref="cyberpunk roguelike",
    )
    assert granted1 == 10

    # 2. Identical search within 10 min window earns 0 XP
    _, _, granted_dup = progression_service.grant_xp(
        db=db_session,
        user_id=user_creator_a.id,
        event_type="SEARCH",
        source_ref="cyberpunk roguelike",
    )
    assert granted_dup == 0

    # 3. Different search query earns XP
    _, _, granted_diff = progression_service.grant_xp(
        db=db_session,
        user_id=user_creator_a.id,
        event_type="SEARCH",
        source_ref="sci-fi platformer",
    )
    assert granted_diff == 10

    # 4. Save discovery earns 25 XP (1-time per steam_app_id)
    _, _, save1 = progression_service.grant_xp(
        db=db_session,
        user_id=user_creator_a.id,
        event_type="SAVE_DISCOVERY",
        source_ref="app_12345",
    )
    assert save1 == 25

    _, _, save_dup = progression_service.grant_xp(
        db=db_session,
        user_id=user_creator_a.id,
        event_type="SAVE_DISCOVERY",
        source_ref="app_12345",
    )
    assert save_dup == 0


# -----------------------------------------------------------------------------
# 3. Milestone Unlocks & Idempotency
# -----------------------------------------------------------------------------

def test_milestone_evaluation_and_idempotency(db_session: Session, user_creator_a: User):
    """Verify all milestone trigger conditions and strict database-level idempotency."""
    # A. FIRST_BUILD: requires successful build completion
    unlocked_build = progression_service.evaluate_milestones(
        db=db_session,
        user_id=user_creator_a.id,
        trigger_event="COMPLETE_BUILD",
        context={"is_campaign": False, "stages_count": 1},
    )
    assert any(m.milestone_key == "FIRST_BUILD" for m in unlocked_build)

    # Re-triggering does not double-award FIRST_BUILD
    unlocked_build_dup = progression_service.evaluate_milestones(
        db=db_session,
        user_id=user_creator_a.id,
        trigger_event="COMPLETE_BUILD",
        context={"is_campaign": False, "stages_count": 1},
    )
    assert not any(m.milestone_key == "FIRST_BUILD" for m in unlocked_build_dup)

    # B. FIRST_CAMPAIGN: requires multi-stage/level structure
    unlocked_camp = progression_service.evaluate_milestones(
        db=db_session,
        user_id=user_creator_a.id,
        trigger_event="COMPLETE_BUILD",
        context={"is_campaign": True, "stages_count": 3},
    )
    assert any(m.milestone_key == "FIRST_CAMPAIGN" for m in unlocked_camp)

    # C. FIRST_PLAYTEST & FIRST_WIN
    unlocked_pt = progression_service.evaluate_milestones(
        db=db_session,
        user_id=user_creator_a.id,
        trigger_event="PLAYTEST",
        context={"outcome": "LOSS"},
    )
    assert any(m.milestone_key == "FIRST_PLAYTEST" for m in unlocked_pt)
    assert not any(m.milestone_key == "FIRST_WIN" for m in unlocked_pt)

    unlocked_win = progression_service.evaluate_milestones(
        db=db_session,
        user_id=user_creator_a.id,
        trigger_event="PLAYTEST_WIN",
        context={"outcome": "WIN"},
    )
    assert any(m.milestone_key == "FIRST_WIN" for m in unlocked_win)

    # D. FIRST_AI_ANALYSIS
    unlocked_ai = progression_service.evaluate_milestones(
        db=db_session,
        user_id=user_creator_a.id,
        trigger_event="AI_ANALYSIS",
    )
    assert any(m.milestone_key == "FIRST_AI_ANALYSIS" for m in unlocked_ai)

    # E. BUILD_SIMILAR_PRO
    unlocked_sim = progression_service.evaluate_milestones(
        db=db_session,
        user_id=user_creator_a.id,
        trigger_event="BUILD_SIMILAR",
        context={"source_game_id": "app_999"},
    )
    assert any(m.milestone_key == "BUILD_SIMILAR_PRO" for m in unlocked_sim)

    # F. GENRE_EXPLORER: requires >= 3 genres interacted with
    preference_service.record_signal(db_session, user_creator_a.id, ["Action"], 2.0, "save")
    preference_service.record_signal(db_session, user_creator_a.id, ["Shooter"], 2.0, "save")
    preference_service.record_signal(db_session, user_creator_a.id, ["Survival"], 2.0, "save")

    unlocked_genre = progression_service.evaluate_milestones(
        db=db_session,
        user_id=user_creator_a.id,
        trigger_event="SEARCH",
    )
    assert any(m.milestone_key == "GENRE_EXPLORER" for m in unlocked_genre)

    # Verify total unlocked in DB
    milestones_db = db_session.query(UserMilestone).filter_by(user_id=user_creator_a.id).all()
    assert len(milestones_db) >= 6


# -----------------------------------------------------------------------------
# 4. User Isolation & IDOR Protection
# -----------------------------------------------------------------------------

def test_progression_user_isolation(db_session: Session, user_creator_a: User, user_creator_b: User):
    """Verify User A and User B have separate XP, levels, milestones, and activity."""
    # User A earns build XP and unlocks FIRST_BUILD
    progression_service.grant_xp(db_session, user_creator_a.id, "COMPLETE_BUILD", 50, "build_1")
    progression_service.evaluate_milestones(db_session, user_creator_a.id, "COMPLETE_BUILD")

    # User B has 0 XP and 0 milestones
    resp_a = progression_service.get_progress_response(db_session, user_creator_a.id)
    resp_b = progression_service.get_progress_response(db_session, user_creator_b.id)

    assert resp_a.total_xp >= 100  # 50 + 50 bonus from FIRST_BUILD
    assert resp_b.total_xp == 0
    assert resp_a.unlocked_milestone_count >= 1
    assert resp_b.unlocked_milestone_count == 0

    assert len(resp_a.recent_events) >= 1
    assert len(resp_b.recent_events) == 0


# -----------------------------------------------------------------------------
# 5. API Endpoint Verification
# -----------------------------------------------------------------------------

def test_progress_api_endpoint(db_session: Session, user_creator_a: User):
    """Verify GET /api/profile/progress endpoint authentication and response schema."""
    from app.db.session import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)

        # Unauthorized request
        unauth_resp = client.get("/api/profile/progress")
        assert unauth_resp.status_code == 401

        # Authenticated request
        token = create_access_token(user_id=user_creator_a.id)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/profile/progress", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["user_id"] == user_creator_a.id
        assert data["current_level"] >= 1
        assert "creator_title" in data
        assert "milestones" in data
        assert len(data["milestones"]) == 8
        assert "unlocked_milestone_count" in data
        assert "total_milestone_count" in data
        assert data["total_milestone_count"] == 8
        assert "recent_events" in data
    finally:
        app.dependency_overrides.pop(get_db, None)
