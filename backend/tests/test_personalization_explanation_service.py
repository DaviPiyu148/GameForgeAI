"""
GameForge Personalization V1 — Personalization Explanation Service Unit Tests
=============================================================================
Validates grounded, deterministic, template-based explanation generation.
Covers global, project, hybrid, saved-discovery, cold-start, avoidance,
suppression, project-switching, maximum reasons, determinism, and performance.
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List
import pytest

from app.schemas.developer_profile import (
    DeveloperPreferenceProfile,
    EffectivePreferenceProfile,
    PersonalizationReason,
    ProjectPreferenceProfile,
)
from app.services.context_blender import context_blender
from app.services.personalization_explanation_service import (
    PersonalizationExplanationService,
    personalization_explanation_service,
)


@pytest.fixture
def sample_global_profile() -> DeveloperPreferenceProfile:
    """Developer with strong global interest in Strategy and crafting, avoiding Horror."""
    now = datetime.now(timezone.utc)
    return DeveloperPreferenceProfile(
        user_id="user_exp_1",
        genres={"Strategy": 0.90, "Casual": 0.75},
        mechanics={"crafting": 0.85, "base building": 0.80},
        themes={"space": 0.80},
        modes={"singleplayer": 1.0},
        explicit_avoidances=["Horror"],
        suppressed_game_ids=["banned_game_123"],
        total_signal_count=6,
        confidence_tier="MODERATE",
    )


@pytest.fixture
def sample_project_profile() -> ProjectPreferenceProfile:
    """Active project with Action genre, procedural generation mechanic, and cyberpunk theme."""
    return ProjectPreferenceProfile(
        project_id="proj_neon",
        title="Neon Protocol",
        genres={"Action": 1.0},
        mechanics={"procedural generation": 1.0, "twin-stick": 0.9},
        themes={"cyberpunk": 1.0},
        modes={"singleplayer": 1.0},
    )


# ============================================================================
# 1. Global-Only Personalization Reason
# ============================================================================

def test_global_preference_explanation(sample_global_profile: DeveloperPreferenceProfile):
    """Candidate matches strong global genre -> matches your long-term interest in Strategy games."""
    candidate = {
        "id": "game_strat_1",
        "title": "Stellar Tactics",
        "genres": ["Strategy"],
        "tags": ["space", "tactical"],
        "player_modes": ["Single-player"],
    }
    reasons = personalization_explanation_service.explain(
        candidate=candidate,
        global_profile=sample_global_profile,
        project_profile=None,
    )

    assert len(reasons) >= 1
    assert reasons[0].source == "GLOBAL"
    assert reasons[0].dimension == "genre"
    assert reasons[0].value == "Strategy"
    assert reasons[0].text == "Matches your long-term interest in Strategy games."


# ============================================================================
# 2. Project-Specific Personalization Reason
# ============================================================================

def test_project_preference_explanation(
    sample_global_profile: DeveloperPreferenceProfile,
    sample_project_profile: ProjectPreferenceProfile,
):
    """Candidate matches active project mechanic -> Recommended for your active project."""
    candidate = {
        "id": "game_proc_1",
        "title": "Rogue Core",
        "genres": ["Action"],
        "tags": ["procedural generation", "action"],
        "player_modes": ["Single-player"],
    }
    reasons = personalization_explanation_service.explain(
        candidate=candidate,
        global_profile=sample_global_profile,
        project_profile=sample_project_profile,
    )

    assert len(reasons) >= 1
    # Priority 1: Project reason
    assert reasons[0].source == "PROJECT"
    assert "Recommended for your active project" in reasons[0].text
    assert "mechanics" in reasons[0].text or "genre" in reasons[0].text


# ============================================================================
# 3. Both Sources (Priority Order: Project > Global)
# ============================================================================

def test_hybrid_both_sources_explanation(
    sample_global_profile: DeveloperPreferenceProfile,
    sample_project_profile: ProjectPreferenceProfile,
):
    """Candidate matches both project theme (cyberpunk) and global genre (Strategy)."""
    candidate = {
        "id": "game_hybrid_1",
        "title": "Cyber Syndicate Tactics",
        "genres": ["Strategy"],
        "tags": ["cyberpunk"],
        "player_modes": ["Single-player"],
    }
    reasons = personalization_explanation_service.explain(
        candidate=candidate,
        global_profile=sample_global_profile,
        project_profile=sample_project_profile,
    )

    assert len(reasons) == 2
    # First reason must be from active project (Priority 1)
    assert reasons[0].source == "PROJECT"
    assert reasons[0].dimension == "theme"
    assert reasons[0].value == "cyberpunk"
    assert reasons[0].text == "Recommended for your active project because it matches its Cyberpunk theme."

    # Second reason must be from global developer profile (Priority 2)
    assert reasons[1].source == "GLOBAL"
    assert reasons[1].dimension == "genre"
    assert reasons[1].value == "Strategy"
    assert reasons[1].text == "Matches your long-term interest in Strategy games."


# ============================================================================
# 4. Saved Discovery Semantic Similarity
# ============================================================================

def test_saved_discovery_similarity_explanation(sample_global_profile: DeveloperPreferenceProfile):
    """Candidate has vector cosine similarity >= 0.75 to concrete saved game 'Shapebreaker'."""
    candidate = {
        "id": "game_sim_1",
        "title": "Deckbuilder Tactics",
        "genres": ["Indie"],
        "tags": ["deck building"],
        "player_modes": ["Single-player"],
    }
    sims = [("Shapebreaker", 0.8450)]

    reasons = personalization_explanation_service.explain(
        candidate=candidate,
        global_profile=sample_global_profile,
        project_profile=None,
        saved_discovery_similarities=sims,
    )

    assert len(reasons) >= 1
    saved_reason = next((r for r in reasons if r.source == "SAVED_DISCOVERY"), None)
    assert saved_reason is not None
    assert saved_reason.text == "Similar gameplay feel to your saved discovery 'Shapebreaker'."
    assert saved_reason.value == "Shapebreaker"
    assert saved_reason.confidence == 0.8450


def test_saved_discovery_similarity_below_threshold_ignored(sample_global_profile: DeveloperPreferenceProfile):
    """Similarity below MIN_VECTOR_SIMILARITY (0.75) must NOT produce an explanation."""
    candidate = {"id": "game_low_sim", "title": "Random Game"}
    sims = [("Shapebreaker", 0.6200)]

    reasons = personalization_explanation_service.explain(
        candidate=candidate,
        global_profile=sample_global_profile,
        project_profile=None,
        saved_discovery_similarities=sims,
    )
    assert len(reasons) == 0


# ============================================================================
# 5. No Evidence -> No Explanation
# ============================================================================

def test_no_evidence_yields_empty_reasons(sample_global_profile: DeveloperPreferenceProfile):
    """Candidate shares zero attributes with profile -> returns strictly []."""
    candidate = {
        "id": "game_unrelated",
        "title": "Sports Football 2026",
        "genres": ["Sports"],
        "tags": ["soccer", "football", "simulation"],
        "player_modes": ["Multi-player"],
    }
    reasons = personalization_explanation_service.explain(
        candidate=candidate,
        global_profile=sample_global_profile,
        project_profile=None,
    )
    assert reasons == []


# ============================================================================
# 6. Cold Start Neutrality
# ============================================================================

def test_cold_start_neutrality_yields_empty_reasons():
    """Unregistered / zero-preference developer -> returns strictly []."""
    cold_profile = DeveloperPreferenceProfile(
        user_id="cold_user",
        genres={},
        mechanics={},
        themes={},
        modes={},
        total_signal_count=0,
        confidence_tier="COLD",
    )
    candidate = {
        "id": "game_any",
        "title": "Popular RPG",
        "genres": ["RPG", "Action"],
        "tags": ["fantasy"],
    }
    reasons = personalization_explanation_service.explain(
        candidate=candidate,
        global_profile=cold_profile,
        project_profile=None,
    )
    assert reasons == []


# ============================================================================
# 7. Absolute Avoidance Safety
# ============================================================================

def test_explicit_avoidance_safety(sample_global_profile: DeveloperPreferenceProfile):
    """
    Candidate matches Horror tag/genre, but user explicitly avoids 'Horror'.
    Horror must NEVER be used to explain or recommend this game.
    """
    assert "Horror" in sample_global_profile.explicit_avoidances

    candidate = {
        "id": "game_horror_1",
        "title": "Haunted Woods",
        "genres": ["Horror", "Adventure"],
        "tags": ["horror", "dark", "survival"],
    }
    reasons = personalization_explanation_service.explain(
        candidate=candidate,
        global_profile=sample_global_profile,
        project_profile=None,
    )

    for r in reasons:
        assert "horror" not in r.text.lower()
        assert "horror" not in r.value.lower()


# ============================================================================
# 8. Suppressed Game Safety
# ============================================================================

def test_suppressed_game_yields_zero_reasons(sample_global_profile: DeveloperPreferenceProfile):
    """Disliked / suppressed game must never receive a personalized reason."""
    candidate = {
        "id": "banned_game_123",
        "title": "Disliked Game",
        "genres": ["Strategy"],  # matches user's favorite genre, but game is suppressed
        "tags": ["tactics"],
    }
    reasons = personalization_explanation_service.explain(
        candidate=candidate,
        global_profile=sample_global_profile,
        project_profile=None,
    )
    assert reasons == []


# ============================================================================
# 9. Project Switching Isolation
# ============================================================================

def test_project_switching_explanation_isolation(sample_global_profile: DeveloperPreferenceProfile):
    """
    Verifies that Project A reasons never contaminate Project B or No Project.
    """
    proj_a = ProjectPreferenceProfile(
        project_id="p_a",
        title="Project A",
        genres={"Shooter": 1.0},
        themes={"cyberpunk": 1.0},
    )
    proj_b = ProjectPreferenceProfile(
        project_id="p_b",
        title="Project B",
        genres={"RPG": 1.0},
        themes={"dungeon": 1.0},
    )
    candidate = {
        "id": "game_switch",
        "title": "Versatile Title",
        "genres": ["Shooter", "RPG", "Strategy"],
        "tags": ["cyberpunk", "dungeon"],
    }

    # Context A
    reasons_a = personalization_explanation_service.explain(candidate, sample_global_profile, proj_a)
    assert any(r.source == "PROJECT" and ("Cyberpunk" in r.text or "Shooter" in r.text) for r in reasons_a)
    assert not any("dungeon" in r.text.lower() or "rpg" in r.text.lower() for r in reasons_a)

    # Context B
    reasons_b = personalization_explanation_service.explain(candidate, sample_global_profile, proj_b)
    assert any(r.source == "PROJECT" and ("Dungeon" in r.text or "RPG" in r.text) for r in reasons_b)
    assert not any("cyberpunk" in r.text.lower() or "shooter" in r.text.lower() for r in reasons_b)

    # Context None (Global Only)
    reasons_none = personalization_explanation_service.explain(candidate, sample_global_profile, None)
    assert not any(r.source == "PROJECT" for r in reasons_none)
    assert all(r.source == "GLOBAL" for r in reasons_none)


# ============================================================================
# 10. Maximum Reasons Cap & Determinism
# ============================================================================

def test_max_reasons_cap_and_determinism(
    sample_global_profile: DeveloperPreferenceProfile,
    sample_project_profile: ProjectPreferenceProfile,
):
    """Never emits more than 2 reasons, and output is 100% deterministic."""
    candidate = {
        "id": "game_many_matches",
        "title": "Super Hybrid",
        "genres": ["Action", "Strategy", "Casual"],
        "tags": ["cyberpunk", "procedural generation", "crafting", "base building", "space"],
        "player_modes": ["Single-player"],
    }
    sims = [("Shapebreaker", 0.90)]

    run1 = personalization_explanation_service.explain(
        candidate, sample_global_profile, sample_project_profile, saved_discovery_similarities=sims
    )
    run2 = personalization_explanation_service.explain(
        candidate, sample_global_profile, sample_project_profile, saved_discovery_similarities=sims
    )

    assert len(run1) <= 2
    assert len(run1) == len(run2)
    assert [r.text for r in run1] == [r.text for r in run2]
    assert [r.source for r in run1] == [r.source for r in run2]


# ============================================================================
# 11. Performance
# ============================================================================

def test_explanation_service_performance(
    sample_global_profile: DeveloperPreferenceProfile,
    sample_project_profile: ProjectPreferenceProfile,
):
    """Average explanation generation time must be sub-millisecond (< 0.5 ms)."""
    candidate = {
        "id": "game_perf",
        "title": "Performance Title",
        "genres": ["Action", "Strategy"],
        "tags": ["cyberpunk", "procedural generation"],
        "player_modes": ["Single-player"],
    }

    start = time.perf_counter()
    for _ in range(200):
        _ = personalization_explanation_service.explain(
            candidate, sample_global_profile, sample_project_profile
        )
    duration_ms = (time.perf_counter() - start) * 1000.0 / 200.0

    assert duration_ms < 0.50, f"Explanation generation too slow: {duration_ms:.3f} ms"
