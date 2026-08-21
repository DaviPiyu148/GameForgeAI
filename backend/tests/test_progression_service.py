import pytest
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.progression import UserProgress, XPEvent
from app.services.progression_service import (
    ProgressionService,
    calculate_level_bounds,
    progression_service,
)


@pytest.fixture
def test_user(db_session: Session) -> User:
    user = User(
        email="progression_user@example.com",
        username="progression_user",
        password_hash="fakehash",
        level=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_calculate_level_bounds():
    """Verify progression thresholds curve."""
    # Level 1: 0 XP
    lvl, base, next_xp = calculate_level_bounds(0)
    assert lvl == 1
    assert base == 0
    assert next_xp == 100

    # Level 1 edge: 99 XP
    lvl, base, next_xp = calculate_level_bounds(99)
    assert lvl == 1
    assert next_xp == 100

    # Level 2 threshold: 100 XP
    lvl, base, next_xp = calculate_level_bounds(100)
    assert lvl == 2
    assert base == 100
    assert next_xp == 250

    # Level 3 threshold: 250 XP
    lvl, base, next_xp = calculate_level_bounds(250)
    assert lvl == 3
    assert base == 250
    assert next_xp == 450

    # Level 6 threshold: 1000 XP
    lvl, base, next_xp = calculate_level_bounds(1000)
    assert lvl == 6
    assert base == 1000
    assert next_xp == 1350


def test_grant_xp_and_level_up(db_session: Session, test_user: User):
    """Verify XP grants, level transitions, and User.level synchronization."""
    # Initial state
    resp = progression_service.get_progress_response(db_session, test_user.id)
    assert resp.total_xp == 0
    assert resp.current_level == 1

    # Grant 50 XP (Level 1 -> Level 1)
    progress, leveled_up, granted = progression_service.grant_xp(
        db=db_session,
        user_id=test_user.id,
        event_type="START_BUILD",
        xp_amount=50,
        source_ref="build-1",
    )
    assert granted == 50
    assert not leveled_up
    assert progress.total_xp == 50
    assert progress.current_level == 1

    # Grant 60 XP (Total: 110 XP -> Level 2 Level-Up!)
    progress, leveled_up, granted = progression_service.grant_xp(
        db=db_session,
        user_id=test_user.id,
        event_type="COMPLETE_BUILD",
        xp_amount=60,
        source_ref="build-1",
    )
    assert granted == 60
    assert leveled_up
    assert progress.total_xp == 110
    assert progress.current_level == 2

    # Check User.level in DB
    db_session.refresh(test_user)
    assert test_user.level == 2

    # Check progress response
    resp = progression_service.get_progress_response(db_session, test_user.id)
    assert resp.total_xp == 110
    assert resp.current_level == 2
    assert resp.current_level_base_xp == 100
    assert resp.next_level_xp == 250
    assert resp.xp_into_level == 10
    assert resp.xp_needed_for_next == 140
    assert len(resp.recent_events) == 2


def test_anti_spam_search_duplicate(db_session: Session, test_user: User):
    """Verify duplicate search query within 10 minutes is suppressed."""
    # First search awards 10 XP
    progress, leveled_up, granted = progression_service.grant_xp(
        db=db_session,
        user_id=test_user.id,
        event_type="SEARCH",
        xp_amount=10,
        source_ref="cyberpunk shooter",
    )
    assert granted == 10
    assert progress.total_xp == 10

    # Immediate identical search should grant 0 XP
    progress2, leveled_up2, granted2 = progression_service.grant_xp(
        db=db_session,
        user_id=test_user.id,
        event_type="SEARCH",
        xp_amount=10,
        source_ref="cyberpunk shooter",
    )
    assert granted2 == 0
    assert progress2.total_xp == 10

    # Different query awards XP
    progress3, leveled_up3, granted3 = progression_service.grant_xp(
        db=db_session,
        user_id=test_user.id,
        event_type="SEARCH",
        xp_amount=10,
        source_ref="pixel platformer",
    )
    assert granted3 == 10
    assert progress3.total_xp == 20
