"""
GameForge Personalization V1 — Context Blender Unit Test Suite
==============================================================
Validates project-context extraction, 30/70 context blending,
missing-dimension preservation, absolute avoidance enforcement,
project switching immutability, provenance survival, and performance.
"""

from datetime import datetime, timezone
import time
from typing import Dict, List, Optional
import numpy as np
import pytest
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.user import User
from app.schemas.developer_profile import (
    DeveloperPreferenceProfile,
    PreferenceEvidence,
    ProjectPreferenceProfile,
)
from app.schemas.discovery import DiscoverySearchRequest
from app.services.context_blender import (
    ContextBlender,
    context_blender,
)


class MockEmbedder:
    """Mock text embedder returning deterministic normalized 384-dimensional vectors."""

    def embed_query(self, query: str) -> np.ndarray:
        vec = np.ones((1, 384), dtype=np.float32)
        return vec / np.linalg.norm(vec)


@pytest.fixture
def mock_user_id() -> str:
    return "test-user-context-123"


@pytest.fixture
def cozy_global_profile(mock_user_id: str) -> DeveloperPreferenceProfile:
    """A developer who globally enjoys cozy farming and casual simulation games."""
    now = datetime.now(timezone.utc)
    return DeveloperPreferenceProfile(
        user_id=mock_user_id,
        genres={"Casual": 0.90, "Simulation": 0.85, "Strategy": 0.60},
        mechanics={"crafting": 0.80, "base building": 0.70},
        themes={"cozy": 1.0, "nature": 0.75},
        modes={"singleplayer": 1.0},
        explicit_avoidances=["Horror"],
        suppressed_game_ids=[],
        preference_vector=[0.05] * 384,
        total_signal_count=8,
        confidence_tier="MODERATE",
        recent_focus_genre="Casual",
        last_updated=now,
        evidence=[
            PreferenceEvidence(dimension="genre", value="Casual", contribution=4.5, source="onboarding", timestamp=now),
            PreferenceEvidence(dimension="genre", value="Simulation", contribution=4.0, source="saved_discovery", timestamp=now),
            PreferenceEvidence(dimension="avoidance", value="Horror", contribution=1.0, source="onboarding", timestamp=now),
        ],
    )


# ============================================================================
# 1. Backward-Compatible API Request Context
# ============================================================================

def test_discovery_search_request_optional_project_id():
    """Verify DiscoverySearchRequest accepts optional project_id and remains backward-compatible."""
    # With project_id
    req1 = DiscoverySearchRequest(prompt="deckbuilder with combat", project_id="proj_xyz789")
    assert req1.project_id == "proj_xyz789"
    assert req1.prompt == "deckbuilder with combat"

    # Without project_id (backward-compatible)
    req2 = DiscoverySearchRequest(prompt="deckbuilder with combat")
    assert req2.project_id is None


# ============================================================================
# 2. Cold Start Matrix (All 4 Cases)
# ============================================================================

def test_cold_start_matrix_case_a_no_global_no_project():
    """Case A: No global profile + no active project -> COLD / Neutral."""
    cold_global = DeveloperPreferenceProfile(
        user_id="cold_user",
        genres={},
        mechanics={},
        themes={},
        modes={},
        explicit_avoidances=[],
        total_signal_count=0,
        confidence_tier="COLD",
    )
    effective = context_blender.blend(global_profile=cold_global, project_profile=None)

    assert effective.genres == {}
    assert effective.mechanics == {}
    assert effective.themes == {}
    assert effective.modes == {}
    assert effective.active_project_id is None
    assert effective.preference_vector is None


def test_cold_start_matrix_case_b_no_global_active_project():
    """Case B: No global profile + active project -> 100% project-derived context."""
    cold_global = DeveloperPreferenceProfile(
        user_id="cold_user",
        genres={},
        mechanics={},
        themes={},
        modes={},
        explicit_avoidances=[],
        total_signal_count=0,
        confidence_tier="COLD",
    )
    proj_profile = ProjectPreferenceProfile(
        project_id="p1",
        title="Project Neon",
        genres={"Shooter": 1.0},
        mechanics={"twin-stick": 1.0},
        themes={"cyberpunk": 1.0},
        modes={"singleplayer": 1.0},
    )
    effective = context_blender.blend(global_profile=cold_global, project_profile=proj_profile)

    assert effective.genres == {"Shooter": 1.0}
    assert effective.mechanics == {"twin-stick": 1.0}
    assert effective.themes == {"cyberpunk": 1.0}
    assert effective.active_project_id == "p1"
    assert effective.blend_weights == {"global": 0.0, "project": 1.0}


def test_cold_start_matrix_case_c_global_no_project(cozy_global_profile: DeveloperPreferenceProfile):
    """Case C: Global profile + no active project -> 100% global profile."""
    effective = context_blender.blend(global_profile=cozy_global_profile, project_profile=None)

    assert effective.genres == cozy_global_profile.genres
    assert effective.mechanics == cozy_global_profile.mechanics
    assert effective.themes == cozy_global_profile.themes
    assert effective.explicit_avoidances == ["Horror"]
    assert effective.active_project_id is None
    assert effective.blend_weights == {"global": 1.0, "project": 0.0}


def test_cold_start_matrix_case_d_global_active_project(cozy_global_profile: DeveloperPreferenceProfile):
    """Case D: Global profile + active project -> 30% global + 70% active project blend."""
    proj_profile = ProjectPreferenceProfile(
        project_id="proj_cyber",
        title="Cyber Strike",
        genres={"Shooter": 1.0, "Action": 0.8},
        mechanics={"combat": 1.0, "dash ability": 0.8},
        themes={"cyberpunk": 1.0},
        modes={"singleplayer": 1.0},
    )
    effective = context_blender.blend(global_profile=cozy_global_profile, project_profile=proj_profile)

    assert effective.active_project_id == "proj_cyber"
    assert effective.blend_weights == {"global": 0.30, "project": 0.70}
    # Shooter & Action dominate, while Casual & Simulation remain represented
    assert "Shooter" in effective.genres
    assert "Casual" in effective.genres
    assert effective.genres["Shooter"] > effective.genres["Casual"]


# ============================================================================
# 3. Context Isolation & Project Switching Immutability
# ============================================================================

def test_project_switching_preserves_global_immutability(cozy_global_profile: DeveloperPreferenceProfile):
    """
    Verify that switching between Project A, Project B, and None:
    1. Produces isolated effective profiles for each project.
    2. Leaves the global profile completely unchanged.
    """
    initial_global_genres = dict(cozy_global_profile.genres)
    initial_global_themes = dict(cozy_global_profile.themes)

    # Project A: Cyberpunk Shooter
    proj_a = ProjectPreferenceProfile(
        project_id="proj_a",
        title="Project A (Shooter)",
        genres={"Shooter": 1.0},
        themes={"cyberpunk": 1.0},
    )
    eff_a = context_blender.blend(cozy_global_profile, proj_a)
    assert eff_a.active_project_id == "proj_a"
    assert "Shooter" in eff_a.genres
    assert "cyberpunk" in eff_a.themes

    # Project B: Dungeon Roguelike RPG
    proj_b = ProjectPreferenceProfile(
        project_id="proj_b",
        title="Project B (Dungeon)",
        genres={"RPG": 1.0, "Roguelike": 0.9},
        themes={"dungeon": 1.0},
    )
    eff_b = context_blender.blend(cozy_global_profile, proj_b)
    assert eff_b.active_project_id == "proj_b"
    assert "RPG" in eff_b.genres
    assert "Shooter" not in eff_b.genres  # Project A did NOT contaminate Project B
    assert "dungeon" in eff_b.themes
    assert "cyberpunk" not in eff_b.themes  # Project A did NOT contaminate Project B

    # Switch back to None (Global only)
    eff_none = context_blender.blend(cozy_global_profile, None)
    assert eff_none.active_project_id is None
    assert "Shooter" not in eff_none.genres
    assert "RPG" not in eff_none.genres
    assert eff_none.genres == initial_global_genres

    # Verify Global Profile was never mutated
    assert cozy_global_profile.genres == initial_global_genres
    assert cozy_global_profile.themes == initial_global_themes


# ============================================================================
# 4. Missing Dimension Protection
# ============================================================================

def test_missing_dimension_protection(cozy_global_profile: DeveloperPreferenceProfile):
    """
    Verify that if a project contains ZERO evidence in a dimension (e.g. no themes),
    global preferences in that dimension are preserved at full strength and not dampened by 0.30.
    """
    # Project with mechanics and genres, but EMPTY themes
    proj_no_themes = ProjectPreferenceProfile(
        project_id="p_empty_themes",
        title="Minimal Project",
        genres={"Strategy": 1.0},
        mechanics={"automation": 1.0},
        themes={},  # Project has zero theme evidence
    )
    effective = context_blender.blend(cozy_global_profile, proj_no_themes)

    # Global themes ("cozy": 1.0, "nature": 0.75) must be preserved intact
    assert "cozy" in effective.themes
    assert effective.themes["cozy"] == 1.0
    assert effective.themes["nature"] == 0.75


# ============================================================================
# 5. Dominance Without Erasure
# ============================================================================

def test_project_dominance_without_erasing_global_dna(cozy_global_profile: DeveloperPreferenceProfile):
    """
    Desired behavior:
    Global: Casual=0.9, Strategy=0.6
    Project: Shooter=1.0, Action=0.9
    Effective: Shooter/Action are dominant, Casual/Strategy remain represented at full global weight.
    """
    proj = ProjectPreferenceProfile(
        project_id="p_dom",
        title="Action Rush",
        genres={"Shooter": 1.0, "Action": 0.9},
    )
    effective = context_blender.blend(cozy_global_profile, proj)

    # Project items dominant at top
    top_keys = list(effective.genres.keys())
    assert top_keys[0] == "Shooter"
    assert top_keys[1] == "Action"
    assert effective.genres["Shooter"] == 1.0
    assert effective.genres["Action"] == 0.9

    # Global items preserved at full global strength (Casual=0.9, Strategy=0.6)
    assert "Casual" in effective.genres
    assert "Strategy" in effective.genres
    assert effective.genres["Casual"] == 0.9
    assert effective.genres["Strategy"] == 0.6


def test_missing_dimension_blend_protection_all_cases():
    """
    Verify the corrected missing-dimension formula across all permutations:
    - Global-only term: raw = global_score (NOT 0.30 * global)
    - Project-only term: raw = project_score (NOT 0.70 * project)
    - Both sources term: raw = 0.30 * global + 0.70 * project
    """
    # 1. Global-only genre
    g_prof = DeveloperPreferenceProfile(
        user_id="u1",
        genres={"Strategy": 1.0},
        mechanics={"ranged combat": 1.0},
        themes={"cyberpunk": 1.0},
    )
    p_prof = ProjectPreferenceProfile(
        project_id="p1",
        title="Empty Project",
        genres={},
        mechanics={},
        themes={},
    )
    eff = context_blender.blend(g_prof, p_prof)
    assert eff.genres.get("Strategy") == 1.0
    assert eff.mechanics.get("ranged combat") == 1.0
    assert eff.themes.get("cyberpunk") == 1.0

    # 2. Project-only genre
    g_empty = DeveloperPreferenceProfile(user_id="u2", genres={})
    p_action = ProjectPreferenceProfile(project_id="p2", title="Action Proj", genres={"Action": 1.0})
    eff2 = context_blender.blend(g_empty, p_action)
    assert eff2.genres.get("Action") == 1.0

    # 3. Both sources with identical scores
    g_both = DeveloperPreferenceProfile(user_id="u3", genres={"Action": 1.0})
    p_both = ProjectPreferenceProfile(project_id="p3", title="Action Proj", genres={"Action": 1.0})
    eff3 = context_blender.blend(g_both, p_both)
    assert eff3.genres.get("Action") == 1.0

    # 4. Mixed evidence
    # global Strategy = 0.8, project Strategy = 0.4
    # raw = 0.30 * 0.8 + 0.70 * 0.4 = 0.24 + 0.28 = 0.52
    g_mixed = DeveloperPreferenceProfile(user_id="u4", genres={"Strategy": 0.8})
    p_mixed = ProjectPreferenceProfile(project_id="p4", title="Strategy Proj", genres={"Strategy": 0.4})
    eff4 = context_blender.blend(g_mixed, p_mixed)
    assert eff4.genres.get("Strategy") == 0.52


def test_single_source_terms_not_dampened_when_dimension_shared():
    """
    Verify that when both global and project provide terms in the same dimension,
    unshared terms from either source are preserved at 100% of their respective scores.
    """
    # Global has Action=1.0 and Casual=0.1233
    # Project has Action=1.0
    g_prof = DeveloperPreferenceProfile(user_id="u5", genres={"Action": 1.0, "Casual": 0.1233})
    p_prof = ProjectPreferenceProfile(project_id="p5", title="Action Focus", genres={"Action": 1.0})
    eff = context_blender.blend(g_prof, p_prof)

    assert eff.genres["Action"] == 1.0
    # Casual must be 0.1233, NOT dampened to 0.0370
    assert eff.genres["Casual"] == 0.1233

    # Global has ranged combat=1.0
    # Project has procedural generation=1.0, npc behavior=1.0
    g_mech = DeveloperPreferenceProfile(user_id="u6", mechanics={"ranged combat": 1.0})
    p_mech = ProjectPreferenceProfile(
        project_id="p6",
        title="Procedural World",
        mechanics={"procedural generation": 1.0, "npc behavior": 1.0},
    )
    eff_mech = context_blender.blend(g_mech, p_mech)

    assert eff_mech.mechanics["procedural generation"] == 1.0
    assert eff_mech.mechanics["npc behavior"] == 1.0
    # ranged combat must be preserved at 1.0, NOT dampened to 0.4286
    assert eff_mech.mechanics["ranged combat"] == 1.0


def test_missing_dimension_isolation_cozy_and_cyberpunk():
    """
    Verify cross-dimension isolation:
    global: Cozy=0.9, Simulation=0.85
    project: theme=cyberpunk, genre=Action, mechanics=tactical
    """
    g_prof = DeveloperPreferenceProfile(
        user_id="u7",
        genres={"Casual": 0.90, "Simulation": 0.85},
    )
    p_prof = ProjectPreferenceProfile(
        project_id="p7",
        title="Cyber Strike",
        genres={"Action": 1.0},
        mechanics={"tactical": 1.0},
        themes={"cyberpunk": 1.0},
    )
    eff = context_blender.blend(g_prof, p_prof)

    # Global genres preserved intact
    assert eff.genres["Action"] == 1.0
    assert eff.genres["Casual"] == 0.90
    assert eff.genres["Simulation"] == 0.85

    # Project themes and mechanics present
    assert eff.themes["cyberpunk"] == 1.0
    assert eff.mechanics["tactical"] == 1.0


# ============================================================================
# 6. Absolute Avoidance Conflict Enforcement
# ============================================================================

def test_explicit_avoidance_conflict_enforcement(cozy_global_profile: DeveloperPreferenceProfile):
    """
    Verify that if an active project specifies a genre or theme that the user globally avoids:
    1. Global explicit avoidance remains ABSOLUTE.
    2. The avoided term is suppressed from effective affinities.
    3. The conflict is recorded in effective.conflicts.
    """
    # User globally avoids "Horror"
    assert "Horror" in cozy_global_profile.explicit_avoidances

    # Active project specifies Horror genre and theme
    proj_horror = ProjectPreferenceProfile(
        project_id="p_horror",
        title="Haunted Mansion",
        genres={"Horror": 1.0, "Adventure": 0.8},
        themes={"horror": 1.0, "dungeon": 0.7},
    )
    effective = context_blender.blend(cozy_global_profile, proj_horror)

    # Horror must NOT be present in effective genres or themes
    assert "Horror" not in effective.genres
    assert "horror" not in effective.themes

    # Permitted terms survive
    assert "Adventure" in effective.genres
    assert "dungeon" in effective.themes

    # Avoidance still enforced in list
    assert "Horror" in effective.explicit_avoidances

    # Conflict alerts recorded
    assert len(effective.conflicts) >= 1
    assert any("Horror" in c for c in effective.conflicts)


# ============================================================================
# 7. Provenance Survival
# ============================================================================

def test_provenance_survival_through_blending(cozy_global_profile: DeveloperPreferenceProfile):
    """Verify that blended_details records exact multi-source attribution."""
    proj = ProjectPreferenceProfile(
        project_id="p_prov",
        title="Prov Project",
        genres={"Strategy": 1.0, "Shooter": 0.9},
    )
    effective = context_blender.blend(cozy_global_profile, proj)

    details = {item.value: item for item in effective.blended_details if item.dimension == "genre"}

    # Strategy existed in both
    strat_item = details.get("Strategy")
    assert strat_item is not None
    assert strat_item.was_global is True
    assert strat_item.was_project is True
    assert strat_item.global_score == 0.60
    assert strat_item.project_score == 1.0

    # Shooter existed only in project
    shooter_item = details.get("Shooter")
    assert shooter_item is not None
    assert shooter_item.was_global is False
    assert shooter_item.was_project is True

    # Casual existed only in global
    casual_item = details.get("Casual")
    assert casual_item is not None
    assert casual_item.was_global is True
    assert casual_item.was_project is False


# ============================================================================
# 8. Vector Blending & Normalization
# ============================================================================

def test_vector_blending_normalization():
    """Verify semantic vectors fuse with correct 384 dimensions and unit norm."""
    vec_g = np.random.randn(384).astype(np.float32)
    vec_g = (vec_g / np.linalg.norm(vec_g)).tolist()

    vec_p = np.random.randn(384).astype(np.float32)
    vec_p = (vec_p / np.linalg.norm(vec_p)).tolist()

    blended_vec = ContextBlender._blend_vectors(
        vec_global=vec_g,
        vec_project=vec_p,
        w_global=0.30,
        w_project=0.70,
    )

    assert blended_vec is not None
    assert len(blended_vec) == 384
    arr = np.array(blended_vec, dtype=np.float32)
    assert np.isfinite(arr).all()
    norm = float(np.linalg.norm(arr))
    assert abs(norm - 1.0) < 1e-4


# ============================================================================
# 9. Performance & Execution Speed
# ============================================================================

def test_context_blender_performance(cozy_global_profile: DeveloperPreferenceProfile):
    """Verify that project profile extraction and blending executes in sub-millisecond time."""
    project = Project(
        id="perf_proj",
        user_id=cozy_global_profile.user_id,
        title="Performance Test Project",
        genre="Strategy",
        modules=["Procedural Generation", "Enhanced NPC Behavior"],
        design_spec={
            "theme": "cyberpunk",
            "selected_modules": ["combat system"],
            "player_abilities": ["dash"],
            "world_mode": "linear",
        },
    )

    mock_embedder = MockEmbedder()

    # Warmup
    _ = context_blender.build_project_profile(project, embedder=mock_embedder)

    start = time.perf_counter()
    for _ in range(100):
        proj_prof = context_blender.build_project_profile(project, embedder=mock_embedder)
        _ = context_blender.blend(cozy_global_profile, proj_prof)
    duration_ms = (time.perf_counter() - start) * 1000.0 / 100.0

    # Must complete in under 2ms per invocation (typically < 0.2ms)
    assert duration_ms < 2.0, f"Context blending too slow: {duration_ms:.2f} ms"
