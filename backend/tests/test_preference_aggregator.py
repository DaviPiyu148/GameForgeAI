"""
GameForge Personalization V1 — Preference Aggregator Unit Test Suite
====================================================================
Validates deterministic profile aggregation, provenance attribution,
cold-start behavior, avoidance separation, and vector normalization.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import numpy as np
import pytest
from sqlalchemy.orm import Session

from app.models.preference import UserGenrePreference
from app.models.project import Project
from app.models.saved_discovery import SavedDiscovery
from app.models.user import User
from app.schemas.developer_profile import DeveloperPreferenceProfile
from app.services.preference_aggregator import (
    PreferenceAggregator,
    preference_aggregator,
)
from app.services.preference_service import preference_service


# ============================================================================
# Test Fixtures & Mocks
# ============================================================================

@pytest.fixture
def agg_user(db_session: Session) -> User:
    """Create and commit a clean test user."""
    user = User(
        email="agg_user@example.com",
        username="agg_user",
        password_hash="fakehash",
        level=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class MockCatalogManager:
    """Mock in-memory catalog manager for deterministic game resolution."""

    def __init__(self, games: Optional[Dict[str, Dict[str, Any]]] = None):
        self._games = games or {}

    def get_game(self, game_id: str) -> Optional[Dict[str, Any]]:
        return self._games.get(str(game_id))


class MockIndexManager:
    """Mock FAISS index manager returning deterministic normalized vectors."""

    def __init__(self, vectors: Optional[Dict[str, np.ndarray]] = None):
        self._vectors = vectors or {}

    def is_ready(self) -> bool:
        return True

    def get_vector(self, game_id: str, pool: Any = None) -> Optional[np.ndarray]:
        return self._vectors.get(str(game_id))


class MockEmbedder:
    """Mock text embedder returning deterministic 384-dimensional vectors."""

    def embed_query(self, query: str) -> np.ndarray:
        vec = np.ones((1, 384), dtype=np.float32)
        return vec / np.linalg.norm(vec)


# ============================================================================
# 1. Cold Start Tests
# ============================================================================

def test_cold_start_profile_for_new_user(db_session: Session, agg_user: User):
    """Verify that a user with no interaction history receives an unpersonalized cold profile."""
    profile = preference_aggregator.build_profile(db=db_session, user_id=agg_user.id)

    assert profile.confidence_tier == "COLD"
    assert profile.total_signal_count == 0
    assert profile.genres == {}
    assert profile.mechanics == {}
    assert profile.themes == {}
    assert profile.modes == {}
    assert profile.explicit_avoidances == []
    assert profile.suppressed_game_ids == []
    assert profile.preference_vector is None
    assert profile.recent_focus_genre is None
    assert len(profile.evidence) == 0


def test_cold_start_profile_for_nonexistent_user(db_session: Session):
    """Verify safe fallback when user_id does not exist."""
    profile = preference_aggregator.build_profile(db=db_session, user_id="nonexistent-id")
    assert profile.confidence_tier == "COLD"
    assert profile.total_signal_count == 0
    assert profile.genres == {}


# ============================================================================
# 2. Onboarding Preferences Tests
# ============================================================================

def test_onboarding_preferences_aggregation(db_session: Session, agg_user: User):
    """Verify onboarding preferences populate normalized genres, mechanics, and avoidances."""
    preference_service.onboard_preferences(
        db=db_session,
        user_id=agg_user.id,
        genres=["Strategy", "RPG"],
        enjoyments=["Building"],
        avoidances=["Horror"],
    )

    profile = preference_aggregator.build_profile(db=db_session, user_id=agg_user.id)

    # Maturity tier should be EMERGING from onboarding
    assert profile.confidence_tier == "EMERGING"
    assert profile.total_signal_count >= 3

    # Genres normalized 0.0 - 1.0
    assert "Strategy" in profile.genres
    assert "RPG" in profile.genres
    assert profile.genres["Strategy"] == 1.0 or profile.genres["RPG"] == 1.0

    # Avoidance strictly captured in explicit_avoidances, NOT in genres
    assert "Horror" in profile.explicit_avoidances
    assert "Horror" not in profile.genres

    # Provenance attribution
    onboarding_evidence = [e for e in profile.evidence if e.source == "onboarding"]
    assert len(onboarding_evidence) >= 3
    assert any(e.dimension == "avoidance" and e.value == "Horror" for e in onboarding_evidence)


# ============================================================================
# 3. Saved Discovery Contribution Tests
# ============================================================================

def test_saved_discovery_contribution(db_session: Session, agg_user: User):
    """Verify saved bookmarks contribute genre, mechanic, theme, and mode evidence."""
    app_id = "99901"
    game_dict = {
        "id": app_id,
        "title": "Neon Grid Fortress",
        "genres": ["Strategy", "Roguelike"],
        "tags": ["deckbuilder", "cyberpunk", "automation"],
        "player_modes": ["singleplayer"],
    }
    dummy_vec = np.full((384,), 0.05, dtype=np.float32)
    dummy_vec = dummy_vec / np.linalg.norm(dummy_vec)

    mock_cat = MockCatalogManager({app_id: game_dict})
    mock_idx = MockIndexManager({app_id: dummy_vec})

    # Save discovery
    save = SavedDiscovery(user_id=agg_user.id, steam_app_id=app_id)
    db_session.add(save)
    db_session.commit()

    custom_aggregator = PreferenceAggregator(catalog_manager=mock_cat, index_manager=mock_idx)
    profile = custom_aggregator.build_profile(db=db_session, user_id=agg_user.id)

    # Affinities
    assert "Strategy" in profile.genres
    assert "Roguelike" in profile.genres
    assert "deckbuilding" in profile.mechanics
    assert "automation" in profile.mechanics
    assert "cyberpunk" in profile.themes
    assert "singleplayer" in profile.modes

    # Provenance
    saved_evidence = [e for e in profile.evidence if e.source == "saved_discovery"]
    assert len(saved_evidence) >= 4
    assert all(e.source_id == app_id for e in saved_evidence)

    # Vector
    assert profile.preference_vector is not None
    assert len(profile.preference_vector) == 384
    norm = np.linalg.norm(profile.preference_vector)
    assert abs(norm - 1.0) < 1e-4


# ============================================================================
# 4. Project DNA Contribution Tests
# ============================================================================

def test_project_dna_contribution(db_session: Session, agg_user: User):
    """Verify project design_spec and parameters contribute structured creative DNA."""
    proj = Project(
        user_id=agg_user.id,
        title="Project Cyberpunk Arena",
        genre="Shooter",
        prompt="A fast-paced twin-stick arena shooter with neon lighting",
        engine="Top-Down Action",
        modules=["Procedural Generation", "Enhanced NPC Behavior"],
        design_spec={
            "theme": "cyberpunk",
            "selected_modules": ["combat system"],
            "player_abilities": ["dash", "shoot"],
            "world_mode": "linear",
        },
    )
    db_session.add(proj)
    db_session.commit()

    mock_embed = MockEmbedder()
    custom_aggregator = PreferenceAggregator(embedder=mock_embed)
    profile = custom_aggregator.build_profile(db=db_session, user_id=agg_user.id)

    assert "Shooter" in profile.genres
    assert "procedural generation" in profile.mechanics
    assert "combat" in profile.mechanics
    assert "cyberpunk" in profile.themes

    proj_evidence = [e for e in profile.evidence if e.source == "project"]
    assert len(proj_evidence) >= 4
    assert all(e.source_id == proj.id for e in proj_evidence)


# ============================================================================
# 5. Avoidance Separation vs Cold Absence Tests
# ============================================================================

def test_avoidance_separation_from_cold_absence(db_session: Session, agg_user: User):
    """
    Verify core invariant:
    - Explicit avoidance ('Horror') is in explicit_avoidances.
    - Cold absence ('Simulation') is NEITHER in genres NOR in explicit_avoidances.
    """
    now = datetime.now(timezone.utc)
    # Positive preference
    db_session.add(UserGenrePreference(user_id=agg_user.id, genre="Strategy", score=6.0, interaction_count=3, last_interaction_at=now))
    # Explicit avoidance (score=0.0 and interaction_count=2)
    db_session.add(UserGenrePreference(user_id=agg_user.id, genre="Horror", score=0.0, interaction_count=2, last_interaction_at=now))
    db_session.commit()

    profile = preference_aggregator.build_profile(db=db_session, user_id=agg_user.id)

    assert "Horror" in profile.explicit_avoidances
    assert "Horror" not in profile.genres

    # Simulation was never interacted with
    assert "Simulation" not in profile.genres
    assert "Simulation" not in profile.explicit_avoidances


# ============================================================================
# 6. No False Negatives on Bookmark Deletion
# ============================================================================

def test_no_false_negatives_on_bookmark_deletion(db_session: Session, agg_user: User):
    """Verify that deleting a saved discovery row leaves zero negative or dislike signal."""
    app_id = "88801"
    save = SavedDiscovery(user_id=agg_user.id, steam_app_id=app_id)
    db_session.add(save)
    db_session.commit()

    # User removes the bookmark
    db_session.delete(save)
    db_session.commit()

    profile = preference_aggregator.build_profile(db=db_session, user_id=agg_user.id)

    # Deleting a bookmark does NOT add to suppressed_game_ids or explicit_avoidances
    assert app_id not in profile.suppressed_game_ids
    assert profile.confidence_tier == "COLD"
    assert profile.total_signal_count == 0


# ============================================================================
# 7. Vector Finiteness & Normalization Tests
# ============================================================================

def test_vector_normalization_and_finiteness(db_session: Session, agg_user: User):
    """Verify 384-dimensional vector aggregation satisfies finite and unit-norm checks."""
    app_id = "77701"
    raw_vec = np.random.randn(384).astype(np.float32)
    mock_idx = MockIndexManager({app_id: raw_vec})
    mock_cat = MockCatalogManager({app_id: {"genres": ["Action"]}})

    db_session.add(SavedDiscovery(user_id=agg_user.id, steam_app_id=app_id))
    db_session.commit()

    custom_aggregator = PreferenceAggregator(catalog_manager=mock_cat, index_manager=mock_idx)
    profile = custom_aggregator.build_profile(db=db_session, user_id=agg_user.id)

    assert profile.preference_vector is not None
    vec = np.array(profile.preference_vector, dtype=np.float32)
    assert vec.shape == (384,)
    assert np.isfinite(vec).all()
    norm = float(np.linalg.norm(vec))
    assert abs(norm - 1.0) < 1e-4


# ============================================================================
# 8. Determinism Tests
# ============================================================================

def test_aggregation_determinism(db_session: Session, agg_user: User):
    """Verify that multiple builds on identical database state produce byte-for-byte identical profiles."""
    now = datetime.now(timezone.utc)
    db_session.add(UserGenrePreference(user_id=agg_user.id, genre="Strategy", score=4.5, interaction_count=2, last_interaction_at=now))
    db_session.add(UserGenrePreference(user_id=agg_user.id, genre="RPG", score=3.0, interaction_count=1, last_interaction_at=now))
    db_session.commit()

    p1 = preference_aggregator.build_profile(db=db_session, user_id=agg_user.id)
    p2 = preference_aggregator.build_profile(db=db_session, user_id=agg_user.id)

    assert p1.genres == p2.genres
    assert p1.mechanics == p2.mechanics
    assert p1.themes == p2.themes
    assert p1.modes == p2.modes
    assert p1.confidence_tier == p2.confidence_tier
    assert p1.total_signal_count == p2.total_signal_count
    assert p1.explicit_avoidances == p2.explicit_avoidances
    assert len(p1.evidence) == len(p2.evidence)


# ============================================================================
# 9. Source Attribution & Provenance Tests
# ============================================================================

def test_source_attribution_provenance(db_session: Session, agg_user: User):
    """
    Verify aggregator tracks multi-source attribution for the same preference.
    e.g. 'Strategy' has evidence from onboarding, saved game, and project.
    """
    now = datetime.now(timezone.utc)

    # 1. Onboarding signal for Strategy
    db_session.add(UserGenrePreference(user_id=agg_user.id, genre="Strategy", score=3.0, interaction_count=1, last_interaction_at=now))

    # 2. Saved game with Strategy
    app_id = "55501"
    mock_cat = MockCatalogManager({app_id: {"genres": ["Strategy"]}})
    db_session.add(SavedDiscovery(user_id=agg_user.id, steam_app_id=app_id))

    # 3. Project with Strategy
    db_session.add(Project(user_id=agg_user.id, title="Strategy Project", genre="Strategy", prompt="Build a 4X game"))
    db_session.commit()

    custom_agg = PreferenceAggregator(catalog_manager=mock_cat)
    profile = custom_agg.build_profile(db=db_session, user_id=agg_user.id)

    strategy_evidence = [e for e in profile.evidence if e.dimension == "genre" and e.value == "Strategy"]
    sources = {e.source for e in strategy_evidence}

    # All three distinct sources must be traceable
    assert "onboarding" in sources
    assert "saved_discovery" in sources
    assert "project" in sources
    assert len(strategy_evidence) == 3


# ============================================================================
# 10. Confidence Tier Progression Tests
# ============================================================================

def test_confidence_tier_progression(db_session: Session, agg_user: User):
    """Verify deterministic progression: COLD -> EMERGING -> MODERATE -> ESTABLISHED."""
    now = datetime.now(timezone.utc)

    # COLD: 1 signal
    db_session.add(UserGenrePreference(user_id=agg_user.id, genre="Action", score=1.0, interaction_count=1, last_interaction_at=now))
    db_session.commit()
    p_cold = preference_aggregator.build_profile(db=db_session, user_id=agg_user.id)
    assert p_cold.confidence_tier == "COLD"

    # EMERGING: 3 signals from 1 source
    db_session.add(UserGenrePreference(user_id=agg_user.id, genre="RPG", score=2.0, interaction_count=1, last_interaction_at=now))
    db_session.add(UserGenrePreference(user_id=agg_user.id, genre="Strategy", score=3.0, interaction_count=1, last_interaction_at=now))
    db_session.commit()
    p_emerging = preference_aggregator.build_profile(db=db_session, user_id=agg_user.id)
    assert p_emerging.confidence_tier == "EMERGING"

    # MODERATE: >= 6 signals from >= 2 distinct sources
    # Add saved discoveries
    mock_cat = MockCatalogManager({
        f"game_{i}": {"genres": ["Strategy"], "tags": ["deckbuilder"]}
        for i in range(5)
    })
    for i in range(3):
        db_session.add(SavedDiscovery(user_id=agg_user.id, steam_app_id=f"game_{i}"))
    db_session.commit()

    custom_agg = PreferenceAggregator(catalog_manager=mock_cat)
    p_moderate = custom_agg.build_profile(db=db_session, user_id=agg_user.id)
    assert p_moderate.total_signal_count >= 6
    assert p_moderate.confidence_tier == "MODERATE"
