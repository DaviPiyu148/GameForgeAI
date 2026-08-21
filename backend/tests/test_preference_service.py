import pytest
from sqlalchemy.orm import Session
from app.models.user import User
from app.services.preference_service import preference_service, CANONICAL_GENRES


@pytest.fixture
def pref_user(db_session: Session) -> User:
    user = User(
        email="pref_user@example.com",
        username="pref_user",
        password_hash="fakehash",
        level=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_map_to_canonical_genres():
    """Verify raw tags and synonym mapping into standardized canonical genres."""
    genres = preference_service.map_to_canonical_genres(["fps", "top-down shooter", "bullet hell"])
    assert "Shooter" in genres

    genres2 = preference_service.map_to_canonical_genres(["metroidvania", "side-scroller", "precision platformer"])
    assert "Platformer" in genres2

    genres3 = preference_service.map_to_canonical_genres(["action rpg", "hack and slash"])
    assert "RPG" in genres3
    assert "Action" in genres3


def test_record_preference_signals_and_distribution(db_session: Session, pref_user: User):
    """Verify incremental signal weighting and percentage affinity distribution."""
    # Empty initial state
    resp = preference_service.get_preferences(db_session, pref_user.id)
    assert not resp.has_sufficient_data
    assert len(resp.top_genres) == 0

    # Record search for Shooter (weight 1.0)
    preference_service.record_signal(
        db=db_session,
        user_id=pref_user.id,
        raw_genres_or_tags=["fps", "shooter"],
        weight=1.0,
        source="search",
    )

    # Record save for Shooter & Action (weight 3.0)
    preference_service.record_signal(
        db=db_session,
        user_id=pref_user.id,
        raw_genres_or_tags=["shooter", "action"],
        weight=3.0,
        source="save_discovery",
    )

    # Record playtest for Platformer (weight 8.0)
    preference_service.record_signal(
        db=db_session,
        user_id=pref_user.id,
        raw_genres_or_tags=["platformer"],
        weight=8.0,
        source="playtest",
    )

    resp2 = preference_service.get_preferences(db_session, pref_user.id)
    assert resp2.has_sufficient_data
    assert len(resp2.top_genres) >= 2
    # Platformer should be #1 with highest score (8.0)
    assert resp2.top_genres[0].genre == "Platformer"
    assert resp2.top_genres[0].score == 8.0
    assert resp2.top_genres[0].affinity_tier == "High"
