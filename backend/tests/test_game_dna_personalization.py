"""
Comprehensive test suite for Game DNA & Personalization V1.

Verifies:
1. Canonical genre taxonomy & synonym mapping.
2. Behavioral signal weighting & logarithmic diminishing returns scaling.
3. Low-data threshold handling (clean non-fabricated state for new users).
4. Full Game DNA formation (ranked percentages, affinity tiers, strongest match, recent interest, confidence).
5. User isolation & IDOR protection across preference profiles.
6. Structured LLM generation prompt context propagation.
7. End-to-end API integration for preference telemetry and profile retrieval.
"""
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.services.preference_service import preference_service, CANONICAL_GENRES
from app.ai.prompts import build_generation_prompt
from app.auth.tokens import create_access_token


@pytest.fixture
def user_dna_a(db_session: Session) -> User:
    """Fixture creating User A."""
    user = User(
        email="dna_user_a@example.com",
        username="dna_user_a",
        password_hash="fakehash",
        level=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_dna_b(db_session: Session) -> User:
    """Fixture creating User B."""
    user = User(
        email="dna_user_b@example.com",
        username="dna_user_b",
        password_hash="fakehash",
        level=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# -----------------------------------------------------------------------------
# 1. Canonical Taxonomy & Synonym Mapping
# -----------------------------------------------------------------------------

def test_canonical_genre_taxonomy_and_synonyms():
    """Verify all canonical genres and diverse keyword synonyms map accurately."""
    # Direct canonical
    assert "Shooter" in preference_service.map_to_canonical_genres(["Shooter"])
    assert "Survival" in preference_service.map_to_canonical_genres(["survival"])
    assert "Platformer" in preference_service.map_to_canonical_genres(["Platformer"])

    # Synonyms
    fps_mapped = preference_service.map_to_canonical_genres(["fps", "bullet hell", "top-down shooter"])
    assert fps_mapped == {"Shooter"}

    rogue_mapped = preference_service.map_to_canonical_genres(["roguelite", "permadeath"])
    assert rogue_mapped == {"Roguelike"}

    mixed_mapped = preference_service.map_to_canonical_genres(["hack and slash", "dungeon crawler", "wave survival"])
    assert "Action" in mixed_mapped
    assert "RPG" in mixed_mapped
    assert "Survival" in mixed_mapped


# -----------------------------------------------------------------------------
# 2. Diminishing Returns & Saturation Scaling
# -----------------------------------------------------------------------------

def test_diminishing_returns_scaling(db_session: Session, user_dna_a: User):
    """Verify repeated identical actions grow sublinearly and prevent single-genre runaway."""
    # First search signal (weight 1.0)
    preference_service.record_signal(
        db=db_session,
        user_id=user_dna_a.id,
        raw_genres_or_tags=["Action"],
        weight=1.0,
        source="search",
    )
    prefs1 = preference_service.get_preferences(db_session, user_dna_a.id)
    # Total score should equal initial weight 1.0
    from app.models.preference import UserGenrePreference
    p1 = db_session.query(UserGenrePreference).filter_by(user_id=user_dna_a.id, genre="Action").first()
    assert p1.score == 1.0

    # Rapid repeated signals on same genre
    for _ in range(10):
        preference_service.record_signal(
            db=db_session,
            user_id=user_dna_a.id,
            raw_genres_or_tags=["Action"],
            weight=1.0,
            source="search",
        )

    db_session.refresh(p1)
    # Score should be less than 11.0 due to diminishing returns scaling: gain = weight / (1.0 + 0.04 * score)
    assert p1.score < 10.0
    assert p1.score > 7.0
    assert p1.interaction_count == 11


# -----------------------------------------------------------------------------
# 3. Low-Data Threshold Handling (No Fabricated Defaults)
# -----------------------------------------------------------------------------

def test_low_data_state_new_user(db_session: Session, user_dna_a: User):
    """Verify new or low-interaction users receive clean forming state without fake percentages."""
    # Brand new user with 0 interactions
    resp = preference_service.get_preferences(db_session, user_dna_a.id)
    assert not resp.has_sufficient_data
    assert resp.confidence_level == "LOW"
    assert resp.top_genres == []
    assert resp.strongest_match is None
    assert resp.recent_interest is None

    # User with only 1 single low-weight search (below minimum threshold)
    preference_service.record_signal(
        db=db_session,
        user_id=user_dna_a.id,
        raw_genres_or_tags=["Action"],
        weight=1.0,
        source="search",
    )
    resp2 = preference_service.get_preferences(db_session, user_dna_a.id)
    assert not resp2.has_sufficient_data
    assert resp2.confidence_level == "LOW"
    assert resp2.top_genres == []


# -----------------------------------------------------------------------------
# 4. Formed Game DNA & Personalization Profile
# -----------------------------------------------------------------------------

def test_formed_game_dna_profile(db_session: Session, user_dna_a: User):
    """Verify user with sufficient activity receives calibrated Game DNA profile."""
    # 1. Save an Action / Shooter game (weight 3.0)
    preference_service.record_signal(
        db=db_session,
        user_id=user_dna_a.id,
        raw_genres_or_tags=["Action", "Shooter"],
        weight=3.0,
        source="save_discovery",
    )

    # 2. Build a Survival prototype (weight 4.5)
    preference_service.record_signal(
        db=db_session,
        user_id=user_dna_a.id,
        raw_genres_or_tags=["Survival"],
        weight=4.5,
        source="start_build",
    )

    resp = preference_service.get_preferences(db_session, user_dna_a.id)
    assert resp.has_sufficient_data is True
    assert resp.confidence_level in ("MODERATE", "HIGH")
    assert len(resp.top_genres) >= 3

    genres_present = [g.genre for g in resp.top_genres]
    assert "Survival" in genres_present
    assert "Action" in genres_present
    assert "Shooter" in genres_present

    # Percentages sum to approx 100%
    total_pct = sum(g.percentage for g in resp.top_genres)
    assert 99.0 <= total_pct <= 101.0

    # Recent interest must be Survival (most recent signal)
    assert resp.recent_interest == "Survival"
    assert resp.strongest_match is not None


# -----------------------------------------------------------------------------
# 5. User Isolation & IDOR Protection
# -----------------------------------------------------------------------------

def test_user_isolation(db_session: Session, user_dna_a: User, user_dna_b: User):
    """Verify User A and User B maintain completely isolated Game DNA profiles."""
    # User A loves Roguelike
    preference_service.record_signal(
        db=db_session,
        user_id=user_dna_a.id,
        raw_genres_or_tags=["Roguelike"],
        weight=6.0,
        source="playtest",
    )
    preference_service.record_signal(
        db=db_session,
        user_id=user_dna_a.id,
        raw_genres_or_tags=["Roguelike"],
        weight=4.0,
        source="start_build",
    )

    # User B loves Casual / Puzzle
    preference_service.record_signal(
        db=db_session,
        user_id=user_dna_b.id,
        raw_genres_or_tags=["Puzzle"],
        weight=5.0,
        source="start_build",
    )
    preference_service.record_signal(
        db=db_session,
        user_id=user_dna_b.id,
        raw_genres_or_tags=["Casual"],
        weight=4.0,
        source="save_discovery",
    )

    prefs_a = preference_service.get_preferences(db_session, user_dna_a.id)
    prefs_b = preference_service.get_preferences(db_session, user_dna_b.id)

    assert prefs_a.has_sufficient_data is True
    assert prefs_b.has_sufficient_data is True

    assert prefs_a.top_genres[0].genre == "Roguelike"
    assert prefs_b.top_genres[0].genre == "Puzzle"

    # User A has zero Puzzle or Casual
    assert not any(g.genre in ("Puzzle", "Casual") for g in prefs_a.top_genres)
    # User B has zero Roguelike
    assert not any(g.genre == "Roguelike" for g in prefs_b.top_genres)


# -----------------------------------------------------------------------------
# 6. Structured Generation Prompt Context Integration
# -----------------------------------------------------------------------------

def test_prompt_personalization_context_injection():
    """Verify build_generation_prompt formats structured Game DNA without overriding user prompt."""
    prompt = "Create a fast maze runner with neon obstacles"

    # Case A: User has formed Game DNA
    personalization_payload = {
        "preferred_genres": ["Shooter", "Survival", "Action"],
        "confidence": "high",
        "recent_interest": "Shooter",
        "has_sufficient_data": True,
    }

    prompt_with_dna = build_generation_prompt(
        prompt=prompt,
        engine="Top-Down Action",
        personalization=personalization_payload,
    )

    assert "PLAYER GAME DNA" in prompt_with_dna
    assert "Shooter, Survival, Action" in prompt_with_dna
    assert "HIGH" in prompt_with_dna
    assert "explicit concept prompt ALWAYS takes absolute precedence" in prompt_with_dna
    assert "<user_game_concept>" in prompt_with_dna
    assert prompt in prompt_with_dna

    # Case B: Low-data user (no personalization section injected)
    prompt_no_dna = build_generation_prompt(
        prompt=prompt,
        engine="Top-Down Action",
        personalization=None,
    )
    assert "PLAYER GAME DNA" not in prompt_no_dna

    prompt_low_data = build_generation_prompt(
        prompt=prompt,
        engine="Top-Down Action",
        personalization={"has_sufficient_data": False},
    )
    assert "PLAYER GAME DNA" not in prompt_low_data


# -----------------------------------------------------------------------------
# 7. Preferences API Endpoint Verification
# -----------------------------------------------------------------------------

def test_preferences_api_endpoint(db_session: Session, user_dna_a: User):
    """Verify GET /api/profile/preferences returns 200 with authenticated JWT and 401 when unauthorized."""
    from app.db.session import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)

        # 1. Unauthorized request
        unauth_resp = client.get("/api/profile/preferences")
        assert unauth_resp.status_code == 401

        # 2. Authenticated request for low-data user
        token = create_access_token(user_id=user_dna_a.id)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/profile/preferences", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == user_dna_a.id
        assert data["has_sufficient_data"] is False
        assert data["confidence_level"] == "LOW"

        # 3. Add activity and verify response updates
        preference_service.record_signal(
            db=db_session,
            user_id=user_dna_a.id,
            raw_genres_or_tags=["Strategy", "RPG"],
            weight=5.0,
            source="save_discovery",
        )
        preference_service.record_signal(
            db=db_session,
            user_id=user_dna_a.id,
            raw_genres_or_tags=["Strategy"],
            weight=4.0,
            source="start_build",
        )

        resp_after = client.get("/api/profile/preferences", headers=headers)
        assert resp_after.status_code == 200
        data_after = resp_after.json()
        assert data_after["has_sufficient_data"] is True
        assert len(data_after["top_genres"]) >= 2
        assert data_after["top_genres"][0]["genre"] == "Strategy"
        assert data_after["recent_interest"] == "Strategy"
    finally:
        app.dependency_overrides.pop(get_db, None)
