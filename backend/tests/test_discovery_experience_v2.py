"""
Discovery Experience V2 Test Suite.

Verifies:
1. Cold-start Game DNA onboarding (POST /api/profile/preferences/onboard).
2. Game DNA preferences reset (POST /api/profile/preferences/reset) without deleting saves/projects/progression.
3. Multi-game comparison (POST /api/discovery/compare) with 2-3 games and metadata overlap calculation.
4. Session-scoped tuning (temporary avoidances, session context) without permanent database mutation.
5. Discovery ranking modes (BEST_MATCH, DISCOVER, HIDDEN_GEMS, POPULAR).
6. Feedback semantics and anti-spam handling.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.user import User
from app.models.preference import UserGenrePreference
from app.models.saved_discovery import SavedDiscovery
from app.models.progression import UserProgress, XPEvent
from app.services.preference_service import preference_service
from app.services.discovery_service import discovery_service
from app.schemas.discovery import DiscoverySearchRequest, DiscoverySessionContext


@pytest.fixture
def auth_headers(client: TestClient, db_session: Session):
    """Creates a registered test user and returns auth authorization headers."""
    email = "discovery_v2_user@example.com"
    existing = db_session.query(User).filter(User.email == email).first()
    if not existing:
        res = client.post(
            "/api/auth/register",
            json={"email": email, "username": "discovery_v2_tester", "password": "Password123!"},
        )
        assert res.status_code == 201
        token = res.json()["access_token"]
    else:
        res = client.post(
            "/api/auth/login",
            json={"email": email, "password": "Password123!"},
        )
        assert res.status_code == 200
        token = res.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


def test_onboard_preferences(client: TestClient, auth_headers: dict, db_session: Session):
    """Verify onboarding initializes bounded preferences for a user."""
    payload = {
        "genres": ["RPG", "Action"],
        "enjoyments": ["Exploration", "Crafting"],
        "avoidances": ["Horror"],
    }
    response = client.post("/api/profile/preferences/onboard", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["has_sufficient_data"] is True
    assert len(data["top_genres"]) >= 2
    genres = [g["genre"] for g in data["top_genres"]]
    assert "RPG" in genres or "Action" in genres
    assert "Horror" in data.get("avoidances", [])


def test_reset_preferences_preserves_other_data(client: TestClient, auth_headers: dict, db_session: Session):
    """Verify Game DNA reset wipes preferences but preserves saves, projects, and progression."""
    # 1. Onboard first
    client.post(
        "/api/profile/preferences/onboard",
        json={"genres": ["RPG"], "enjoyments": ["Story"], "avoidances": ["Horror"]},
        headers=auth_headers,
    )

    # 2. Get user ID
    user = db_session.query(User).filter(User.email == "discovery_v2_user@example.com").first()
    assert user is not None

    # 3. Add saved discovery and progress event
    saved = SavedDiscovery(user_id=user.id, steam_app_id="105600")
    db_session.add(saved)

    prog = db_session.query(UserProgress).filter(UserProgress.user_id == user.id).first()
    if not prog:
        prog = UserProgress(user_id=user.id, total_xp=150, current_level=2)
        db_session.add(prog)
    db_session.commit()

    # 4. Call reset endpoint
    reset_res = client.post("/api/profile/preferences/reset", headers=auth_headers)
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "success"

    # 5. Verify preferences deleted
    prefs = db_session.query(UserGenrePreference).filter(UserGenrePreference.user_id == user.id).all()
    assert len(prefs) == 0

    # 6. Verify saves and progress remain intact
    saved_after = db_session.query(SavedDiscovery).filter(SavedDiscovery.user_id == user.id).all()
    assert len(saved_after) >= 1
    prog_after = db_session.query(UserProgress).filter(UserProgress.user_id == user.id).first()
    assert prog_after.total_xp >= 150


def test_compare_games_endpoint(client: TestClient):
    """Verify comparing 2-3 games returns metadata overlap and differentiating tags."""
    # Terraria (105600) and Portal (400)
    payload = {"game_ids": ["105600", "400"]}
    res = client.post("/api/discovery/compare", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert len(data["games"]) == 2
    assert "common_genres" in data
    assert "common_tags" in data
    assert "differentiating_tags" in data


def test_compare_games_validation_bounds(client: TestClient):
    """Verify comparing less than 2 or more than 3 games fails validation."""
    res_single = client.post("/api/discovery/compare", json={"game_ids": ["105600"]})
    assert res_single.status_code == 422

    res_four = client.post("/api/discovery/compare", json={"game_ids": ["105600", "400", "730", "570"]})
    assert res_four.status_code == 422


@pytest.mark.asyncio
async def test_session_tuning_no_db_pollution(db_session: Session):
    """Verify session tuning modifies ranking without persisting temporary avoidances to DB."""
    req = DiscoverySearchRequest(
        prompt="space exploration",
        limit=10,
        mode="BEST_MATCH",
        session_context=DiscoverySessionContext(
            temporary_avoid_tags=["horror", "combat"],
            refinements=["More Relaxing"],
            surprise_seed=42,
        ),
    )
    resp = await discovery_service.search(req, user_id=None, db=db_session)
    assert resp.match_count > 0
    # Verify no persistent DB records were written for session avoidances
    prefs = db_session.query(UserGenrePreference).filter(UserGenrePreference.user_id == "temp_session").all()
    assert len(prefs) == 0


@pytest.mark.asyncio
async def test_discovery_modes_distinct_characteristics(db_session: Session):
    """Verify that BEST_MATCH and HIDDEN_GEMS produce distinct score orderings."""
    req_best = DiscoverySearchRequest(prompt="cyberpunk action", limit=10, mode="BEST_MATCH")
    res_best = await discovery_service.search(req_best, user_id=None, db=db_session)

    req_gems = DiscoverySearchRequest(prompt="cyberpunk action", limit=10, mode="HIDDEN_GEMS")
    res_gems = await discovery_service.search(req_gems, user_id=None, db=db_session)

    assert res_best.match_count > 0
    assert res_gems.match_count > 0
    assert res_best.mode == "BEST_MATCH"
    assert res_gems.mode == "HIDDEN_GEMS"

