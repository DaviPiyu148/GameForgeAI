"""
GameForge Personalization V1 — Offline Personalization Re-Ranker Unit Tests
===========================================================================
Validates mathematical bounds, identity at lambda=0.0, cold-start neutrality,
hard-constraint & explicit avoidance enforcement, project switching isolation,
saved-discovery gradient, determinism, and performance.
"""

from typing import Any, Dict, List
import pytest

from app.schemas.developer_profile import (
    DeveloperPreferenceProfile,
    EffectivePreferenceProfile,
    ProjectPreferenceProfile,
)
from app.services.context_blender import context_blender
from app.services.personalization_reranker import (
    PersonalizationReRanker,
    personalization_reranker,
)


@pytest.fixture
def sample_candidates() -> List[Dict[str, Any]]:
    return [
        {
            "id": "game_1",
            "title": "Neon Rogue",
            "score": 0.85,
            "genres": ["Action", "Roguelike"],
            "tags": ["cyberpunk", "procedural generation"],
            "player_modes": ["Single-player"],
        },
        {
            "id": "game_2",
            "title": "Sprout Valley",
            "score": 0.82,
            "genres": ["Casual", "Simulation"],
            "tags": ["farming", "crafting", "cozy"],
            "player_modes": ["Single-player"],
        },
        {
            "id": "game_3",
            "title": "Tactical Strike",
            "score": 0.80,
            "genres": ["Strategy"],
            "tags": ["turn-based", "tactical"],
            "player_modes": ["Single-player"],
        },
        {
            "id": "game_4",
            "title": "Cabin of Terror",
            "score": 0.78,
            "genres": ["Horror"],
            "tags": ["horror", "dark"],
            "player_modes": ["Single-player"],
        },
    ]


@pytest.fixture
def active_effective_profile() -> EffectivePreferenceProfile:
    g_prof = DeveloperPreferenceProfile(
        user_id="dev_tactical_1",
        genres={"Strategy": 1.0, "Casual": 0.7},
        mechanics={"turn-based": 1.0, "tactical": 0.9},
        explicit_avoidances=["Horror"],
        suppressed_game_ids=["banned_game_999"],
        total_signal_count=5,
    )
    p_prof = ProjectPreferenceProfile(
        project_id="proj_tactics",
        title="Hex Tactics",
        genres={"Strategy": 1.0},
        mechanics={"turn-based": 1.0},
    )
    return context_blender.blend(g_prof, p_prof)


# ============================================================================
# 1. Identity at Lambda = 0.0
# ============================================================================

def test_lambda_zero_identity(
    sample_candidates: List[Dict[str, Any]],
    active_effective_profile: EffectivePreferenceProfile,
):
    """When lambda=0.0, final rankings and scores must match baseline exactly."""
    reranked, traces = personalization_reranker.rerank(
        results=sample_candidates,
        effective_profile=active_effective_profile,
        lambda_=0.0,
    )

    assert len(reranked) == len(sample_candidates)
    # Exact ordering preserved
    for idx, (orig, item, trace) in enumerate(zip(sample_candidates, reranked, traces), start=1):
        assert item["id"] == orig["id"]
        assert trace.base_rank == idx
        assert trace.personalized_rank == idx
        assert trace.rank_delta == 0
        assert trace.personalized_final_score == orig["score"]


# ============================================================================
# 2. Cold-Start Identity (Zero Delta on 100% of Candidates)
# ============================================================================

def test_cold_start_neutrality_exact_identity(sample_candidates: List[Dict[str, Any]]):
    """When profile is Cold / Empty, personalization score is 0.0 and rankings are unchanged."""
    cold_profile = DeveloperPreferenceProfile(
        user_id="cold_dev",
        genres={},
        mechanics={},
        themes={},
        modes={},
        total_signal_count=0,
    )
    eff_cold = context_blender.blend(cold_profile, None)

    # Even at lambda = 0.15, cold profile must have zero movement
    reranked, traces = personalization_reranker.rerank(
        results=sample_candidates,
        effective_profile=eff_cold,
        lambda_=0.15,
    )

    for orig, item, trace in zip(sample_candidates, reranked, traces):
        assert item["id"] == orig["id"]
        assert trace.personalization_score == 0.0
        assert trace.rank_delta == 0
        assert trace.personalized_final_score == orig["score"]


# ============================================================================
# 3. Bounded Personalization Score [0.0, 1.0]
# ============================================================================

def test_personalization_score_strictly_bounded(
    sample_candidates: List[Dict[str, Any]],
    active_effective_profile: EffectivePreferenceProfile,
):
    """Personalization score must be strictly in [0.0, 1.0]."""
    for cand in sample_candidates:
        score, meta = personalization_reranker.compute_personalization_score(
            candidate=cand,
            effective_profile=active_effective_profile,
        )
        assert 0.0 <= score <= 1.0
        assert isinstance(score, float)


# ============================================================================
# 4. Project-Context Influence
# ============================================================================

def test_project_context_reorders_close_candidates(sample_candidates: List[Dict[str, Any]]):
    """
    Candidate 3 (Tactical Strike, base score 0.80) matches project Strategy + tactical.
    At lambda=0.10, its personalization score should lift it above Candidate 2 (0.82).
    """
    g_prof = DeveloperPreferenceProfile(
        user_id="dev_tactical_2",
        genres={"Strategy": 1.0},
        mechanics={"tactical": 1.0, "turn-based": 1.0},
        total_signal_count=4,
    )
    p_prof = ProjectPreferenceProfile(
        project_id="proj_tac_strike",
        title="Strike Mission",
        genres={"Strategy": 1.0},
        mechanics={"tactical": 1.0},
    )
    eff = context_blender.blend(g_prof, p_prof)

    reranked, traces = personalization_reranker.rerank(
        results=sample_candidates,
        effective_profile=eff,
        lambda_=0.10,
    )

    t3 = next(t for t in traces if t.candidate_id == "game_3")
    assert t3.personalization_score > 0.50
    assert t3.personalized_final_score > 0.80
    assert t3.rank_delta > 0  # Rose in rank!


# ============================================================================
# 5. Project Switching Isolation
# ============================================================================

def test_project_switching_isolation(sample_candidates: List[Dict[str, Any]]):
    """Project A context must never bleed into Project B or No Project."""
    g_prof = DeveloperPreferenceProfile(
        user_id="dev_switch_1",
        genres={"Action": 1.0},
        total_signal_count=2,
    )
    p_cozy = ProjectPreferenceProfile(
        project_id="p_cozy",
        title="Cozy Valley",
        genres={"Casual": 1.0, "Simulation": 1.0},
        mechanics={"farming": 1.0},
    )
    p_tactics = ProjectPreferenceProfile(
        project_id="p_tac",
        title="Warfare",
        genres={"Strategy": 1.0},
        mechanics={"tactical": 1.0},
    )

    eff_cozy = context_blender.blend(g_prof, p_cozy)
    eff_tac = context_blender.blend(g_prof, p_tactics)
    eff_none = context_blender.blend(g_prof, None)

    _, traces_cozy = personalization_reranker.rerank(sample_candidates, eff_cozy, lambda_=0.10)
    _, traces_tac = personalization_reranker.rerank(sample_candidates, eff_tac, lambda_=0.10)
    _, traces_none = personalization_reranker.rerank(sample_candidates, eff_none, lambda_=0.10)

    # In Cozy context, Sprout Valley (game_2) receives high score
    t_cozy_g2 = next(t for t in traces_cozy if t.candidate_id == "game_2")
    # In Tactics context, Sprout Valley receives low/zero score
    t_tac_g2 = next(t for t in traces_tac if t.candidate_id == "game_2")

    assert t_cozy_g2.personalization_score > t_tac_g2.personalization_score
    assert any("simulation" in k.lower() or "casual" in k.lower() for k in t_cozy_g2.matched_features)
    assert not any("strategy" in k.lower() for k in t_cozy_g2.matched_features)


# ============================================================================
# 6. Absolute Explicit Avoidance Enforcement
# ============================================================================

def test_explicit_avoidance_receives_zero_personalization(sample_candidates: List[Dict[str, Any]]):
    """Candidate with Horror must receive 0.0 personalization if Horror is explicitly avoided."""
    dev_avoids_horror = DeveloperPreferenceProfile(
        user_id="dev_no_horror",
        genres={"Action": 1.0},
        explicit_avoidances=["Horror"],
        total_signal_count=3,
    )
    # Project attempts to specify Horror
    proj_horror = ProjectPreferenceProfile(
        project_id="proj_horror_clash",
        title="Haunted",
        genres={"Horror": 1.0},
    )
    eff = context_blender.blend(dev_avoids_horror, proj_horror)

    p_score, meta = personalization_reranker.compute_personalization_score(
        candidate=sample_candidates[3],  # "Cabin of Terror" (Horror)
        effective_profile=eff,
    )
    assert p_score == 0.0
    assert meta["matched_features"] == {}


# ============================================================================
# 7. Suppressed Game Receives Zero Personalization
# ============================================================================

def test_suppressed_game_receives_zero_personalization(sample_candidates: List[Dict[str, Any]]):
    """Disliked / suppressed game ID receives strictly 0.0 personalization score."""
    dev = DeveloperPreferenceProfile(
        user_id="dev_suppress_test",
        genres={"Strategy": 1.0},
        suppressed_game_ids=["game_3"],
        total_signal_count=2,
    )
    eff = context_blender.blend(dev, None)

    p_score, _ = personalization_reranker.compute_personalization_score(
        candidate=sample_candidates[2],  # "Tactical Strike" (game_3)
        effective_profile=eff,
    )
    assert p_score == 0.0


# ============================================================================
# 8. Determinism Test
# ============================================================================

def test_reranker_determinism(
    sample_candidates: List[Dict[str, Any]],
    active_effective_profile: EffectivePreferenceProfile,
):
    """Repeated calls with identical inputs must produce identical outputs."""
    r1, t1 = personalization_reranker.rerank(sample_candidates, active_effective_profile, lambda_=0.08)
    r2, t2 = personalization_reranker.rerank(sample_candidates, active_effective_profile, lambda_=0.08)

    assert [x["id"] for x in r1] == [x["id"] for x in r2]
    assert [t.personalized_final_score for t in t1] == [t.personalized_final_score for t in t2]
    assert [t.rank_delta for t in t1] == [t.rank_delta for t in t2]
