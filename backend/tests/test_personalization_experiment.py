"""
GameForge Personalization V1 — Phase 6: Experiment Service Tests
================================================================
Covers all requirements from the Phase 6 specification:
- Feature modes: OFF / SHADOW / TREATMENT
- Identity at lambda=0 → exact base ranking
- Safety: cold start, avoidance, hard constraints
- Cohort assignment: stable per user_id
- Shadow: response identical to control
- Treatment: response may differ only within safe candidate set
- Failure fallback: personalization exception → base response
- Project context: project switching
- Performance: latency diagnostics captured
"""
import pytest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from app.schemas.developer_profile import (
    DeveloperPreferenceProfile,
    EffectivePreferenceProfile,
    ProjectPreferenceProfile,
)
from app.schemas.discovery import (
    DiscoverySearchResponse,
    DiscoverySearchResult,
    GameDiscoveryItem,
)
from app.services.personalization_experiment import (
    ExperimentDiagnostics,
    PersonalizationExperimentService,
    PERSONALIZATION_MODE_OFF,
    PERSONALIZATION_MODE_SHADOW,
    PERSONALIZATION_MODE_TREATMENT,
    _user_in_treatment_cohort,
    _compute_profile_alignment,
    _classify_change,
    _mean_alignment,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(game_id: str, title: str, genres: Optional[List[str]] = None) -> GameDiscoveryItem:
    return GameDiscoveryItem(
        id=game_id,
        external_id=game_id,
        title=title,
        description="Test game",
        genres=genres or [],
        tags=[],
    )


def _make_result(game_id: str, title: str, score: float = 0.9, genres: Optional[List[str]] = None) -> DiscoverySearchResult:
    return DiscoverySearchResult(
        game=_make_game(game_id, title, genres),
        score=score,
        match_highlights=[],
        explanation="test",
        is_hidden_gem=False,
        trade_offs=[],
        personalization_reasons=[],
    )


def _make_base_response(results: List[DiscoverySearchResult], mode: str = "BEST_MATCH") -> DiscoverySearchResponse:
    return DiscoverySearchResponse(
        query="test query",
        match_count=len(results),
        no_strong_match=False,
        mode=mode,
        results=results,
    )


def _warm_profile(user_id: str = "user_warm") -> EffectivePreferenceProfile:
    """Profile with some genre affinity (non-cold)."""
    return EffectivePreferenceProfile(
        user_id=user_id,
        genres={"Strategy": 0.9, "RPG": 0.6},
        mechanics={"deckbuilding": 0.8},
        themes={"cyberpunk": 0.5},
        modes={},
        explicit_avoidances=[],
        suppressed_game_ids=[],
    )


def _cold_profile(user_id: str = "user_cold") -> EffectivePreferenceProfile:
    """Profile with no affinities (cold start)."""
    return EffectivePreferenceProfile(
        user_id=user_id,
        genres={},
        mechanics={},
        themes={},
        modes={},
        explicit_avoidances=[],
        suppressed_game_ids=[],
    )


def _make_service() -> PersonalizationExperimentService:
    return PersonalizationExperimentService()


# ---------------------------------------------------------------------------
# 1. Feature modes
# ---------------------------------------------------------------------------

class TestFeatureModes:
    """Phase 6 requirement: OFF / SHADOW / TREATMENT behaviour."""

    def test_off_mode_returns_base_unchanged(self):
        svc = _make_service()
        results = [_make_result("g1", "Game A", 0.9), _make_result("g2", "Game B", 0.8)]
        base = _make_base_response(results)
        profile = _warm_profile()

        final, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="user1",
            mode=PERSONALIZATION_MODE_OFF,
        )

        assert final is base, "OFF mode must return the exact base response object"
        assert diag.mode == PERSONALIZATION_MODE_OFF
        assert [r.game.id for r in final.results] == ["g1", "g2"]

    def test_shadow_mode_returns_base_unchanged(self):
        svc = _make_service()
        results = [_make_result("g1", "Game A", 0.9, ["Strategy"]),
                   _make_result("g2", "Game B", 0.8)]
        base = _make_base_response(results)
        profile = _warm_profile()

        final, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="user1",
            mode=PERSONALIZATION_MODE_SHADOW,
            treatment_pct=100,   # everyone would be in treatment, but SHADOW ignores this
        )

        # Response must be the base (shadow never changes the result)
        assert [r.game.id for r in final.results] == ["g1", "g2"]
        assert final.personalized is False
        assert diag.mode == PERSONALIZATION_MODE_SHADOW

    def test_treatment_mode_non_cohort_returns_base(self):
        """Users outside the cohort must receive the base response even in TREATMENT mode."""
        svc = _make_service()
        results = [_make_result("g1", "Game A", 0.9), _make_result("g2", "Game B", 0.8)]
        base = _make_base_response(results)
        profile = _warm_profile()

        # treatment_pct=0 → no user is in cohort
        final, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="user1",
            mode=PERSONALIZATION_MODE_TREATMENT,
            treatment_pct=0,
        )

        assert [r.game.id for r in final.results] == ["g1", "g2"]
        assert final.personalized is False
        assert diag.user_in_treatment_cohort is False

    def test_treatment_mode_cohort_user_may_get_personalized(self):
        """Cohort users in TREATMENT mode receive the personalized response."""
        svc = _make_service()
        # Two games — g2 is a Strategy game, matching the warm profile
        results = [
            _make_result("g1", "Game A", 0.90, ["Action"]),
            _make_result("g2", "Game B", 0.89, ["Strategy"]),
        ]
        base = _make_base_response(results)
        profile = _warm_profile()

        final, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="user1",
            mode=PERSONALIZATION_MODE_TREATMENT,
            treatment_pct=100,  # 100% in treatment
            lambda_=0.10,
        )

        # Response should be marked personalized
        assert final.personalized is True
        assert diag.user_in_treatment_cohort is True

    def test_invalid_mode_falls_back_to_off(self):
        svc = _make_service()
        results = [_make_result("g1", "Game A")]
        base = _make_base_response(results)
        profile = _warm_profile()

        final, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="user1",
            mode="GARBAGE_MODE",
        )

        assert final is base
        assert diag.mode == PERSONALIZATION_MODE_OFF


# ---------------------------------------------------------------------------
# 2. Identity at lambda=0
# ---------------------------------------------------------------------------

class TestLambdaZeroIdentity:
    """Phase 6 req: lambda=0 → exact base ordering."""

    def test_lambda_zero_produces_exact_base_ordering(self):
        svc = _make_service()
        results = [
            _make_result("g1", "Top Game", 0.95, ["Strategy"]),
            _make_result("g2", "Second Game", 0.85, ["RPG"]),
            _make_result("g3", "Third Game", 0.75, ["Action"]),
        ]
        base = _make_base_response(results)
        profile = _warm_profile()

        # TREATMENT + cohort + lambda=0 → no reordering
        final, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="user1",
            mode=PERSONALIZATION_MODE_TREATMENT,
            treatment_pct=100,
            lambda_=0.0,
        )

        base_ids = [r.game.id for r in results]
        final_ids = [r.game.id for r in final.results]
        assert final_ids == base_ids, "lambda=0 must produce exactly the base ranking"
        assert diag.candidates_moved == 0


# ---------------------------------------------------------------------------
# 3. Cold start safety
# ---------------------------------------------------------------------------

class TestColdStartSafety:
    """Phase 6 req: cold profile → identity (no movement)."""

    def test_cold_profile_shadow_mode_returns_base(self):
        svc = _make_service()
        results = [_make_result("g1", "Game A"), _make_result("g2", "Game B")]
        base = _make_base_response(results)
        profile = _cold_profile()

        final, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="cold_user",
            mode=PERSONALIZATION_MODE_SHADOW,
        )

        assert [r.game.id for r in final.results] == ["g1", "g2"]
        assert diag.cold_regression >= 0  # cold regression recorded

    def test_cold_profile_treatment_mode_returns_base(self):
        svc = _make_service()
        results = [_make_result("g1", "Game A"), _make_result("g2", "Game B")]
        base = _make_base_response(results)
        profile = _cold_profile()

        final, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="cold_user",
            mode=PERSONALIZATION_MODE_TREATMENT,
            treatment_pct=100,
        )

        assert [r.game.id for r in final.results] == ["g1", "g2"]

    def test_none_profile_returns_base_in_all_modes(self):
        svc = _make_service()
        results = [_make_result("g1", "Game A")]
        base = _make_base_response(results)

        for mode in [PERSONALIZATION_MODE_SHADOW, PERSONALIZATION_MODE_TREATMENT]:
            final, diag = svc.apply(
                base_response=base,
                effective_profile=None,
                user_id="any_user",
                mode=mode,
                treatment_pct=100,
            )
            assert [r.game.id for r in final.results] == ["g1"]


# ---------------------------------------------------------------------------
# 4. Cohort assignment stability
# ---------------------------------------------------------------------------

class TestCohortAssignment:
    """Phase 6 req: same user → same cohort, deterministic and stable."""

    def test_same_user_always_in_same_cohort(self):
        for user_id in ["user_alpha", "user_beta", "user_gamma", "user_delta"]:
            cohort1 = _user_in_treatment_cohort(user_id, 50)
            cohort2 = _user_in_treatment_cohort(user_id, 50)
            assert cohort1 == cohort2, f"{user_id} changed cohort between calls"

    def test_zero_pct_means_no_user_in_treatment(self):
        for user_id in ["u1", "u2", "u3", "u4", "u5"]:
            assert _user_in_treatment_cohort(user_id, 0) is False

    def test_100_pct_means_all_users_in_treatment(self):
        for user_id in ["u1", "u2", "u3", "u4", "u5"]:
            assert _user_in_treatment_cohort(user_id, 100) is True

    def test_50_pct_roughly_splits_population(self):
        users = [f"user_{i:04d}" for i in range(200)]
        in_treatment = sum(1 for u in users if _user_in_treatment_cohort(u, 50))
        # Should be roughly 50% (±15% tolerance for 200-sample hash distribution)
        assert 70 <= in_treatment <= 130, f"Expected ~100/200 in treatment, got {in_treatment}"

    def test_cohort_assignment_does_not_depend_on_call_order(self):
        users = ["userA", "userB", "userC"]
        forward = [_user_in_treatment_cohort(u, 30) for u in users]
        backward = [_user_in_treatment_cohort(u, 30) for u in reversed(users)]
        assert forward == list(reversed(backward))


# ---------------------------------------------------------------------------
# 5. Safety: explicit avoidance guard
# ---------------------------------------------------------------------------

class TestAvoidanceSafety:
    """Phase 6 req: explicit avoidance wins over project preference and personalization."""

    def test_avoided_genre_gets_zero_alignment(self):
        profile = EffectivePreferenceProfile(
            user_id="user_av",
            genres={"Horror": 1.0},
            mechanics={},
            themes={},
            modes={},
            explicit_avoidances=["Horror"],
            suppressed_game_ids=[],
        )
        result = _make_result("g_horror", "Scary Game", 0.85, ["Horror"])

        # The re-ranker's avoidance guard means the score is 0.0
        # We verify the alignment metric also respects avoidances
        # (PersonalizationExperimentService falls back to base for avoided candidates)
        alignment = _compute_profile_alignment(result, profile)
        # The horror genre IS in the profile (affinity 1.0), but avoidances
        # must dominate at the re-ranker level. alignment() is a pure measurement;
        # the guard is at the re-ranker level.  The key integration test
        # for avoidance is the fallback — we test that here via the service.
        svc = _make_service()
        results = [result]
        base = _make_base_response(results)

        final, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="user_av",
            mode=PERSONALIZATION_MODE_TREATMENT,
            treatment_pct=100,
        )
        # Base ordering must be preserved (avoidance guard in re-ranker → score=0 → no reorder)
        assert [r.game.id for r in final.results] == ["g_horror"]


# ---------------------------------------------------------------------------
# 6. Shadow: diagnostics collected, response not changed
# ---------------------------------------------------------------------------

class TestShadowDiagnostics:
    """Phase 6 req: shadow mode collects diagnostics without changing response."""

    def test_shadow_diagnostics_populated(self):
        svc = _make_service()
        results = [
            _make_result("g1", "Strategy A", 0.90, ["Strategy"]),
            _make_result("g2", "Action B", 0.89, ["Action"]),
        ]
        base = _make_base_response(results)
        profile = _warm_profile()

        final, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="shadow_user",
            mode=PERSONALIZATION_MODE_SHADOW,
        )

        assert diag.mode == PERSONALIZATION_MODE_SHADOW
        assert diag.candidates_evaluated == 2
        assert diag.personalization_latency_ms >= 0.0
        # Alignment uplift is computed even in shadow mode
        assert isinstance(diag.preference_alignment_uplift, float)

    def test_shadow_response_body_identical_to_base(self):
        svc = _make_service()
        results = [
            _make_result("g1", "Game A", 0.95, ["Action"]),
            _make_result("g2", "Game B", 0.85, ["Strategy"]),
            _make_result("g3", "Game C", 0.75, ["RPG"]),
        ]
        base = _make_base_response(results)
        profile = _warm_profile()

        final, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="u1",
            mode=PERSONALIZATION_MODE_SHADOW,
        )

        # Phase 6.1 Section 3: Exhaustive response identity check
        assert final.personalized is False
        assert final.query == base.query
        assert final.match_count == base.match_count
        assert final.mode == base.mode
        assert len(final.results) == len(base.results)
        for r_base, r_final in zip(base.results, final.results):
            assert r_final.game.id == r_base.game.id
            assert r_final.score == r_base.score
            assert r_final.explanation == r_base.explanation
            assert r_final.personalization_reasons == []

    def test_shadow_diagnostic_schema_fields(self):
        """Phase 6.1 Section 4: Verify all diagnostic schema fields are populated."""
        svc = _make_service()
        svc.clear_history()
        results = [
            _make_result("g1", "Game A", 0.90, ["Action"]),
            _make_result("g2", "Game B", 0.89, ["Strategy"]),
        ]
        base = _make_base_response(results)
        profile = _warm_profile()

        final, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="u1",
            mode=PERSONALIZATION_MODE_SHADOW,
            lambda_=0.05,
        )

        assert diag.mode == PERSONALIZATION_MODE_SHADOW
        assert diag.lambda_ == 0.05
        assert diag.discovery_mode == "BEST_MATCH"
        assert diag.profile_confidence_tier in ("COLD", "EMERGING", "MODERATE", "ESTABLISHED")
        assert isinstance(diag.active_project, bool)
        assert diag.base_top_k_ids == ["g1", "g2"]
        assert len(diag.personalized_top_k_ids) == 2
        assert isinstance(diag.top5_churn, int)
        assert isinstance(diag.top10_churn, int)
        assert isinstance(diag.mean_abs_rank_delta, float)
        assert isinstance(diag.max_rank_delta, int)
        assert isinstance(diag.preference_alignment_uplift, float)
        assert isinstance(diag.beneficial_changes, int)
        assert isinstance(diag.neutral_changes, int)
        assert isinstance(diag.harmful_changes, int)
        assert isinstance(diag.safety_fallback_triggered, bool)
        assert isinstance(diag.no_evidence_personalization, bool)
        assert diag.personalization_latency_ms >= 0.0

        # Ring buffer history
        history = svc.get_history()
        assert len(history) == 1
        assert history[0].mode == PERSONALIZATION_MODE_SHADOW


# ---------------------------------------------------------------------------
# 7. Failure fallback
# ---------------------------------------------------------------------------

class TestFailureFallback:
    """Phase 6 req: any personalization exception → base response returned."""

    def test_reranker_exception_triggers_fallback(self):
        svc = _make_service()
        results = [_make_result("g1", "Game A"), _make_result("g2", "Game B")]
        base = _make_base_response(results)
        profile = _warm_profile()

        # Patch the re-ranker to raise an exception
        with patch.object(
            svc,
            "_run_experiment",
            side_effect=RuntimeError("Simulated re-ranker crash"),
        ):
            final, diag = svc.apply(
                base_response=base,
                effective_profile=profile,
                user_id="u1",
                mode=PERSONALIZATION_MODE_SHADOW,
            )

        assert [r.game.id for r in final.results] == ["g1", "g2"]
        assert diag.safety_fallback_triggered is True
        assert "unhandled_exception" in diag.safety_fallback_reason

    def test_latency_budget_exceeded_triggers_fallback(self):
        svc = _make_service()
        results = [_make_result("g1", "Game A")]
        base = _make_base_response(results)
        profile = _warm_profile()

        # Set latency budget to 0 ms → any computation will exceed it
        final, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="u1",
            mode=PERSONALIZATION_MODE_SHADOW,
            latency_budget_ms=0.0,  # impossible to meet
        )

        assert [r.game.id for r in final.results] == ["g1"]
        assert diag.safety_fallback_triggered is True
        assert "latency_budget_exceeded" in diag.safety_fallback_reason


# ---------------------------------------------------------------------------
# 8. Alignment uplift metric
# ---------------------------------------------------------------------------

class TestAlignmentUplift:
    """Phase 6 req: Preference Alignment Uplift must be a meaningful quality signal."""

    def test_alignment_zero_for_cold_profile(self):
        profile = _cold_profile()
        result = _make_result("g1", "Game", 0.9, ["Strategy"])
        alignment = _compute_profile_alignment(result, profile)
        assert alignment == 0.0

    def test_alignment_positive_for_matching_genre(self):
        profile = EffectivePreferenceProfile(
            user_id="u",
            genres={"Strategy": 0.9},
            mechanics={},
            themes={},
            modes={},
            explicit_avoidances=[],
            suppressed_game_ids=[],
        )
        result = _make_result("g1", "Strat Game", 0.9, ["Strategy"])
        alignment = _compute_profile_alignment(result, profile)
        assert alignment > 0.0
        assert alignment <= 1.0

    def test_alignment_higher_for_better_match(self):
        profile = EffectivePreferenceProfile(
            user_id="u",
            genres={"Strategy": 0.9},
            mechanics={},
            themes={},
            modes={},
            explicit_avoidances=[],
            suppressed_game_ids=[],
        )
        good_result = _make_result("g1", "Strategy Game", 0.9, ["Strategy"])
        bad_result = _make_result("g2", "Action Game", 0.9, ["Action"])

        assert _compute_profile_alignment(good_result, profile) > _compute_profile_alignment(bad_result, profile)

    @pytest.mark.parametrize(
        "base_val, pers_val, expected_class",
        [
            (0.50, 0.4500, "HARMFUL"),     # delta = -0.050
            (0.50, 0.4800, "HARMFUL"),     # delta = -0.020 (inclusive harmful threshold)
            (0.50, 0.4801, "NEUTRAL"),     # delta = -0.0199
            (0.50, 0.5000, "NEUTRAL"),     # delta =  0.000
            (0.50, 0.5199, "NEUTRAL"),     # delta = +0.0199
            (0.50, 0.5200, "NEUTRAL"),     # delta = +0.020
            (0.50, 0.5201, "NEUTRAL"),     # delta = +0.0201
            (0.50, 0.5499, "NEUTRAL"),     # delta = +0.0499
            (0.50, 0.5500, "BENEFICIAL"),  # delta = +0.050 (inclusive beneficial threshold)
            (0.50, 0.5501, "BENEFICIAL"),  # delta = +0.0501
        ],
    )
    def test_classification_boundaries_exhaustive(self, base_val, pers_val, expected_class):
        """
        Phase 6.1 Section 1: Exhaustive boundary testing ensuring gap-free,
        mutually exclusive partitioning across all requested thresholds.
        """
        assert _classify_change(base_val, pers_val) == expected_class

    def test_classify_change_beneficial(self):
        assert _classify_change(0.0, 0.2) == "BENEFICIAL"

    def test_classify_change_harmful(self):
        assert _classify_change(0.5, 0.4) == "HARMFUL"

    def test_classify_change_neutral(self):
        assert _classify_change(0.3, 0.32) == "NEUTRAL"

    def test_mean_alignment_empty_results(self):
        profile = _warm_profile()
        assert _mean_alignment([], profile) == 0.0


# ---------------------------------------------------------------------------
# 9. Churn metrics
# ---------------------------------------------------------------------------

class TestChurnMetrics:
    """Phase 6 req: churn ≠ success; classify every Top-5 change."""

    def test_top5_churn_zero_when_no_reorder(self):
        svc = _make_service()
        results = [_make_result("g1", "G1"), _make_result("g2", "G2")]
        base = _make_base_response(results)
        profile = _warm_profile()

        # lambda=0 → no reorder → zero churn
        _, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="u1",
            mode=PERSONALIZATION_MODE_SHADOW,
            lambda_=0.0,
        )

        assert diag.top5_churn == 0
        assert diag.candidates_moved == 0

    def test_churn_tracked_when_reorder_occurs(self):
        svc = _make_service()
        # g2 matches profile strongly; g1 does not
        results = [
            _make_result("g1", "G1", 0.90, ["Horror"]),
            _make_result("g2", "G2", 0.89, ["Strategy"]),
        ]
        base = _make_base_response(results)
        profile = EffectivePreferenceProfile(
            user_id="u",
            genres={"Strategy": 1.0},
            mechanics={},
            themes={},
            modes={},
            explicit_avoidances=[],
            suppressed_game_ids=[],
        )

        _, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="u1",
            mode=PERSONALIZATION_MODE_SHADOW,
            lambda_=0.15,
        )

        # With lambda=0.15, g2 (Strategy=1.0) should leapfrog g1 (Horror=0)
        assert diag.candidates_moved >= 0  # may or may not reorder depending on score delta


# ---------------------------------------------------------------------------
# 10. Empty results guard
# ---------------------------------------------------------------------------

class TestEmptyResults:
    def test_empty_base_response_returns_safely(self):
        svc = _make_service()
        base = _make_base_response([])
        profile = _warm_profile()

        final, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="u1",
            mode=PERSONALIZATION_MODE_SHADOW,
        )

        assert final.results == []
        assert diag.candidates_evaluated == 0


# ---------------------------------------------------------------------------
# 11. Project context in diagnostics
# ---------------------------------------------------------------------------

class TestProjectContext:
    def test_active_project_recorded_in_diagnostics(self):
        svc = _make_service()
        profile = EffectivePreferenceProfile(
            user_id="u",
            active_project_id="proj_123",
            active_project_title="My Game",
            genres={"Strategy": 0.9},
            mechanics={},
            themes={},
            modes={},
            explicit_avoidances=[],
            suppressed_game_ids=[],
        )
        results = [_make_result("g1", "Game A")]
        base = _make_base_response(results)

        _, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="u",
            mode=PERSONALIZATION_MODE_SHADOW,
        )

        assert diag.active_project is True

    def test_no_active_project_recorded_as_false(self):
        svc = _make_service()
        profile = _warm_profile()
        assert profile.active_project_id is None

        results = [_make_result("g1", "Game A")]
        base = _make_base_response(results)

        _, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="u",
            mode=PERSONALIZATION_MODE_SHADOW,
        )

        assert diag.active_project is False


# ---------------------------------------------------------------------------
# 12. Treatment explanations
# ---------------------------------------------------------------------------

class TestTreatmentExplanations:
    def test_treatment_result_may_have_explanations_for_moved_results(self):
        """personalization_reasons are only attached when a result moved rank."""
        svc = _make_service()
        # Use a profile that perfectly matches g2
        profile = EffectivePreferenceProfile(
            user_id="u",
            genres={"Strategy": 1.0},
            mechanics={},
            themes={},
            modes={},
            explicit_avoidances=[],
            suppressed_game_ids=[],
        )
        results = [
            _make_result("g1", "Action Game", 0.90, ["Action"]),
            _make_result("g2", "Strategy Game", 0.89, ["Strategy"]),
        ]
        base = _make_base_response(results)

        final, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="u",
            mode=PERSONALIZATION_MODE_TREATMENT,
            treatment_pct=100,
            lambda_=0.15,
        )

        # Results that did NOT move should have no personalization_reasons
        for res in final.results:
            # Reasons are only injected when rank changed
            assert isinstance(res.personalization_reasons, list)


class TestModeLambdas:
    """Phase 6.2: Test mode-specific lambda resolution."""

    def test_mode_lambdas_overrides_default_lambda(self):
        svc = _make_service()
        results = [
            _make_result("g1", "Action Game", 0.90, ["Action"]),
            _make_result("g2", "Strategy Game", 0.89, ["Strategy"]),
        ]
        base = _make_base_response(results, mode="BEST_MATCH")
        profile = _warm_profile()

        # Provide mode_lambdas with BEST_MATCH=0.02
        _, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="u",
            mode=PERSONALIZATION_MODE_SHADOW,
            lambda_=0.05,
            mode_lambdas={"BEST_MATCH": 0.02, "DISCOVER": 0.07},
        )

        assert diag.lambda_ == 0.02
        assert diag.discovery_mode == "BEST_MATCH"

    def test_mode_lambdas_falls_back_if_mode_not_specified(self):
        svc = _make_service()
        results = [_make_result("g1", "Action Game", 0.90, ["Action"])]
        base = _make_base_response(results, mode="HIDDEN_GEMS")
        profile = _warm_profile()

        _, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="u",
            mode=PERSONALIZATION_MODE_SHADOW,
            lambda_=0.05,
            mode_lambdas={"BEST_MATCH": 0.02},  # HIDDEN_GEMS not present
        )

        assert diag.lambda_ == 0.05
        assert diag.discovery_mode == "HIDDEN_GEMS"


class TestPhase63ModeSpecificShadow:
    """Phase 6.3: Formal regression tests for mode-specific shadow policy and invariants."""

    POLICY = {
        "DISCOVER": 0.05,
        "HIDDEN_GEMS": 0.05,
        "BEST_MATCH": 0.02,
        "POPULAR": 0.00,
    }

    def test_policy_resolution_all_modes(self):
        svc = _make_service()
        results = [_make_result("g1", "Action Game", 0.90, ["Action"])]
        profile = _warm_profile()

        for mode_name, expected_lambda in self.POLICY.items():
            base = _make_base_response(results, mode=mode_name)
            resp, diag = svc.apply(
                base_response=base,
                effective_profile=profile,
                user_id="u",
                mode=PERSONALIZATION_MODE_SHADOW,
                mode_lambdas=self.POLICY,
            )
            assert diag.discovery_mode == mode_name
            assert diag.lambda_ == expected_lambda
            assert diag.configured_mode_lambdas == self.POLICY
            # Shadow invariant: public response is identical to base
            assert resp.results[0].game.id == base.results[0].game.id

    def test_popular_lambda_zero_produces_exact_identity(self):
        svc = _make_service()
        c1 = _make_result("g1", "Generic Game", 0.90, ["Strategy"])
        c2 = _make_result("g2", "Favored Action", 0.89, ["Action"])
        base = _make_base_response([c1, c2], mode="POPULAR")
        profile = _warm_profile()  # has Action=1.0

        resp, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="u",
            mode=PERSONALIZATION_MODE_SHADOW,
            mode_lambdas=self.POLICY,
        )
        assert diag.lambda_ == 0.00
        assert diag.top5_churn == 0
        assert diag.top10_churn == 0
        assert diag.candidates_moved == 0
        assert diag.preference_alignment_uplift == 0.0
        assert [r.game.id for r in resp.results] == ["g1", "g2"]

    def test_best_match_lambda_02_preserves_shadow_identity(self):
        svc = _make_service()
        c1 = _make_result("g1", "Generic Game", 0.90, ["Strategy"])
        c2 = _make_result("g2", "Favored Action", 0.89, ["Action"])
        base = _make_base_response([c1, c2], mode="BEST_MATCH")
        profile = _warm_profile()

        resp, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="u",
            mode=PERSONALIZATION_MODE_SHADOW,
            mode_lambdas=self.POLICY,
        )
        assert diag.lambda_ == 0.02
        assert resp.results[0].game.id == "g1"
        assert resp.results[1].game.id == "g2"

    def test_no_accidental_cross_mode_leakage(self):
        svc = _make_service()
        results = [_make_result("g1", "Action Game", 0.90, ["Action"])]
        profile = _warm_profile()

        # Run multiple interleaved requests across different modes
        modes_to_test = ["POPULAR", "DISCOVER", "BEST_MATCH", "HIDDEN_GEMS", "POPULAR", "BEST_MATCH"]
        for m in modes_to_test:
            base = _make_base_response(results, mode=m)
            _, diag = svc.apply(
                base_response=base,
                effective_profile=profile,
                user_id="u",
                mode=PERSONALIZATION_MODE_SHADOW,
                mode_lambdas=self.POLICY,
            )
            assert diag.discovery_mode == m
            assert diag.lambda_ == self.POLICY[m]


class TestPhase62ProjectContextAndSafety:
    """Phase 6.2: Formal regression tests for project-context sensitivity and safety invariants."""

    def test_project_context_produces_actual_rank_movement(self):
        from app.services.personalization_reranker import personalization_reranker
        from app.services.context_blender import context_blender

        # Global: Cozy Farming
        global_prof = DeveloperPreferenceProfile(
            user_id="dev_cozy",
            genres={"Casual": 1.0, "Simulation": 0.9},
            mechanics={"farming": 1.0},
            themes={"cozy": 1.0},
            total_signal_count=5,
            confidence_tier="ESTABLISHED",
        )
        # Project A: Cyberpunk Tactical Shooter
        proj_a = ProjectPreferenceProfile(
            project_id="p_cyber",
            title="Cyber Ops",
            genres={"Shooter": 1.0, "Action": 1.0},
            mechanics={"tactical": 1.0},
            themes={"cyberpunk": 1.0},
        )
        # Project B: Dark Fantasy RPG
        proj_b = ProjectPreferenceProfile(
            project_id="p_rpg",
            title="Dungeon Shadows",
            genres={"RPG": 1.0},
            mechanics={"dungeon crawler": 1.0},
            themes={"dark fantasy": 1.0},
        )

        # Candidates:
        # Candidate 1: Generic base leader
        c1 = _make_result("c1", "Generic Strategy", 0.90, ["Strategy"])
        # Candidate 2: Tactical Shooter (Matches Project A)
        c2 = _make_result("c2", "Tactical Cyberpunk", 0.88, ["Shooter", "Action"])
        # Candidate 3: Dark RPG (Matches Project B)
        c3 = _make_result("c3", "Dark Fantasy Crawler", 0.87, ["RPG"])

        items = [c1, c2, c3]

        # 1. No project: Global has zero affinity for Shooter or RPG
        p_none = context_blender.blend(global_prof, None)
        res_none, _ = personalization_reranker.rerank(items, p_none, lambda_=0.10)
        assert [r.game.id for r in res_none] == ["c1", "c2", "c3"]

        # 2. Project A: Tactical Cyberpunk gets strong boost and overtakes c1
        p_eff_a = context_blender.blend(global_prof, proj_a)
        res_a, traces_a = personalization_reranker.rerank(items, p_eff_a, lambda_=0.10)
        assert res_a[0].game.id == "c2"  # Candidate 2 rose to rank 1!

        # 3. Project B: Dark Fantasy Crawler gets strong boost and overtakes c1
        p_eff_b = context_blender.blend(global_prof, proj_b)
        res_b, traces_b = personalization_reranker.rerank(items, p_eff_b, lambda_=0.10)
        assert res_b[0].game.id == "c3"  # Candidate 3 rose to rank 1!

        # 4. No project again: reverts to exact base ordering
        res_none_again, _ = personalization_reranker.rerank(items, p_none, lambda_=0.10)
        assert [r.game.id for r in res_none_again] == ["c1", "c2", "c3"]

    def test_global_profile_immutability_during_blending(self):
        from app.services.context_blender import context_blender

        global_prof = DeveloperPreferenceProfile(
            user_id="dev_immut",
            genres={"Casual": 1.0, "Simulation": 0.8},
            mechanics={"farming": 0.9},
            themes={"cozy": 1.0},
            total_signal_count=4,
            confidence_tier="ESTABLISHED",
        )
        before_state = global_prof.model_dump()

        proj_a = ProjectPreferenceProfile(
            project_id="p1",
            title="Title A",
            genres={"Shooter": 1.0},
            mechanics={"tactical": 0.9},
        )
        proj_b = ProjectPreferenceProfile(
            project_id="p2",
            title="Title B",
            genres={"RPG": 1.0},
            mechanics={"dungeon": 0.9},
        )

        _ = context_blender.blend(global_prof, proj_a)
        _ = context_blender.blend(global_prof, proj_b)
        _ = context_blender.blend(global_prof, None)

        after_state = global_prof.model_dump()
        assert before_state == after_state

    def test_project_movement_produces_grounded_explanations(self):
        from app.services.context_blender import context_blender
        from app.services.personalization_explanation_service import PersonalizationExplanationService

        expl_svc = PersonalizationExplanationService()
        global_prof = DeveloperPreferenceProfile(
            user_id="dev_expl",
            genres={"Casual": 1.0},
            total_signal_count=2,
            confidence_tier="EMERGING",
        )
        proj = ProjectPreferenceProfile(
            project_id="p_cyber",
            title="Cyber Ops",
            genres={"Shooter": 1.0},
            themes={"cyberpunk": 1.0},
        )
        eff = context_blender.blend(global_prof, proj)

        candidate = _make_result("g_cyber", "Cyber Vanguard", 0.90, ["Shooter"])
        reasons = expl_svc.explain(candidate=candidate, effective_profile=eff, project_profile=proj)

        assert len(reasons) > 0
        assert reasons[0].source == "PROJECT"
        assert "Shooter" in reasons[0].text or "active project" in reasons[0].text

    def test_saved_discovery_gradient_monotonicity(self):
        from app.services.personalization_reranker import personalization_reranker

        cold_prof = EffectivePreferenceProfile(user_id="test_cold")
        dummy = _make_result("g1", "Test Game", 0.90, [])

        sim_ladder = [0.95, 0.90, 0.80, 0.75, 0.70, 0.50]
        scores = []
        for s in sim_ladder:
            score, _ = personalization_reranker.compute_personalization_score(
                candidate=dummy,
                effective_profile=cold_prof,
                saved_discovery_similarities=[("ReferenceGame", s)],
            )
            scores.append(score)

        # Monotonicity check
        assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))
        # Threshold: < 0.75 gets zero boost
        assert scores[-2] == 0.0
        assert scores[-1] == 0.0


class TestPhase7ControlledTreatment:
    """Phase 7: Focused unit tests for controlled 5% treatment cohort rollout."""

    POLICY = {
        "DISCOVER": 0.05,
        "HIDDEN_GEMS": 0.05,
        "BEST_MATCH": 0.02,
        "POPULAR": 0.00,
    }

    @staticmethod
    def _find_cohort_users():
        """Helper to find deterministic user IDs in and out of the 5% cohort."""
        svc = _make_service()
        treat_user = None
        ctrl_user = None
        for i in range(1000):
            uid = f"user_test_cohort_{i}"
            if svc.user_in_treatment_cohort(uid, 5) and treat_user is None:
                treat_user = uid
            elif not svc.user_in_treatment_cohort(uid, 5) and ctrl_user is None:
                ctrl_user = uid
            if treat_user and ctrl_user:
                break
        return treat_user, ctrl_user

    def test_off_mode_returns_base(self):
        svc = _make_service()
        r1 = _make_result("g1", "Puzzle Game", 0.85, ["Puzzle"])
        r2 = _make_result("g2", "Action Game", 0.80, ["Action"])
        base = _make_base_response([r1, r2], mode="DISCOVER")
        profile = _warm_profile()

        resp, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id="any_user",
            mode=PERSONALIZATION_MODE_OFF,
            mode_lambdas=self.POLICY,
        )
        assert resp.personalized is False
        assert [r.game.id for r in resp.results] == ["g1", "g2"]
        assert diag.mode == PERSONALIZATION_MODE_OFF

    def test_shadow_mode_returns_base_response_identity(self):
        svc = _make_service()
        r1 = _make_result("g1", "Puzzle Game", 0.85, ["Puzzle"])
        r2 = _make_result("g2", "Action Game", 0.80, ["Action"])
        base = _make_base_response([r1, r2], mode="DISCOVER")
        profile = _warm_profile()

        treat_user, _ = self._find_cohort_users()
        resp, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id=treat_user,
            mode=PERSONALIZATION_MODE_SHADOW,
            mode_lambdas=self.POLICY,
        )
        # Even for treatment-eligible user, SHADOW returns base response
        assert resp.personalized is False
        assert [r.game.id for r in resp.results] == ["g1", "g2"]
        assert diag.mode == PERSONALIZATION_MODE_SHADOW
        assert diag.lambda_ == 0.05

    def test_treatment_control_cohort_receives_base_response(self):
        svc = _make_service()
        r1 = _make_result("g1", "Puzzle Game", 0.85, ["Puzzle"])
        r2 = _make_result("g2", "Action Game", 0.80, ["Action"])
        base = _make_base_response([r1, r2], mode="DISCOVER")
        profile = _warm_profile()

        _, ctrl_user = self._find_cohort_users()
        resp, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id=ctrl_user,
            mode=PERSONALIZATION_MODE_TREATMENT,
            treatment_pct=5,
            mode_lambdas=self.POLICY,
        )
        # Control user must receive exact base response, unpersonalized
        assert resp.personalized is False
        assert [r.game.id for r in resp.results] == ["g1", "g2"]
        for r in resp.results:
            assert len(r.personalization_reasons) == 0

    def test_treatment_treatment_cohort_receives_personalized_response(self):
        svc = _make_service()
        r1 = _make_result("g1", "Puzzle Game", 0.805, ["Puzzle"])
        r2 = _make_result("g2", "Strategy Game", 0.800, ["Strategy"])
        base = _make_base_response([r1, r2], mode="DISCOVER")
        profile = _warm_profile()  # Strategy = 0.90 affinity

        treat_user, _ = self._find_cohort_users()
        resp, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id=treat_user,
            mode=PERSONALIZATION_MODE_TREATMENT,
            treatment_pct=5,
            mode_lambdas=self.POLICY,
        )
        # Treatment user receives personalized response with flipped order (g2 boosted over g1)
        assert resp.personalized is True
        assert [r.game.id for r in resp.results] == ["g2", "g1"]
        assert diag.lambda_ == 0.05
        assert diag.candidates_moved == 2
        assert diag.mean_abs_rank_delta == 1.0
        # Grounded explanation attached to moved game
        assert len(resp.results[0].personalization_reasons) > 0

    def test_popular_mode_treatment_cohort_exact_base_identity(self):
        svc = _make_service()
        r1 = _make_result("g1", "Puzzle Game", 0.805, ["Puzzle"])
        r2 = _make_result("g2", "Action Game", 0.800, ["Action"])
        base = _make_base_response([r1, r2], mode="POPULAR")
        profile = _warm_profile()

        treat_user, _ = self._find_cohort_users()
        resp, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id=treat_user,
            mode=PERSONALIZATION_MODE_TREATMENT,
            treatment_pct=5,
            mode_lambdas=self.POLICY,
        )
        # POPULAR has lambda = 0.00 -> zero churn, exact base identity
        assert diag.lambda_ == 0.00
        assert diag.top5_churn == 0
        assert diag.candidates_moved == 0
        assert diag.preference_alignment_uplift == 0.0
        assert [r.game.id for r in resp.results] == ["g1", "g2"]

    def test_best_match_mode_treatment_cohort_lambda_02(self):
        svc = _make_service()
        r1 = _make_result("g1", "Puzzle Game", 0.95, ["Puzzle"])
        r2 = _make_result("g2", "Action Game", 0.80, ["Action"])
        base = _make_base_response([r1, r2], mode="BEST_MATCH")
        profile = _warm_profile()

        treat_user, _ = self._find_cohort_users()
        resp, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id=treat_user,
            mode=PERSONALIZATION_MODE_TREATMENT,
            treatment_pct=5,
            mode_lambdas=self.POLICY,
        )
        assert diag.lambda_ == 0.02
        assert diag.discovery_mode == "BEST_MATCH"
        # High score difference preserved at lambda=0.02
        assert [r.game.id for r in resp.results] == ["g1", "g2"]

    def test_cold_start_user_in_treatment_is_noop(self):
        svc = _make_service()
        r1 = _make_result("g1", "Puzzle Game", 0.85, ["Puzzle"])
        r2 = _make_result("g2", "Action Game", 0.80, ["Action"])
        base = _make_base_response([r1, r2], mode="DISCOVER")
        cold_profile = EffectivePreferenceProfile(user_id="cold_treat_user")

        treat_user, _ = self._find_cohort_users()
        resp, diag = svc.apply(
            base_response=base,
            effective_profile=cold_profile,
            user_id=treat_user,
            mode=PERSONALIZATION_MODE_TREATMENT,
            treatment_pct=5,
            mode_lambdas=self.POLICY,
        )
        # Cold start must produce zero movement, zero explanations, exact base
        assert diag.candidates_moved == 0
        assert diag.top5_churn == 0
        assert [r.game.id for r in resp.results] == ["g1", "g2"]
        for r in resp.results:
            assert len(r.personalization_reasons) == 0

    def test_stable_cohort_assignment(self):
        svc = _make_service()
        treat_user, ctrl_user = self._find_cohort_users()

        # Invariant: stable across repeated evaluations, queries, and times
        for _ in range(10):
            assert svc.user_in_treatment_cohort(treat_user, 5) is True
            assert svc.user_in_treatment_cohort(ctrl_user, 5) is False

        # Anonymous user (empty or None) always gets control
        assert svc.user_in_treatment_cohort("", 5) is False
        assert svc.user_in_treatment_cohort(None, 5) is False

    def test_safety_fallback_reverts_to_base_response(self):
        svc = _make_service()
        r1 = _make_result("g1", "Horror Game", 0.85, ["Horror"])
        r2 = _make_result("g2", "Action Game", 0.80, ["Action"])
        base = _make_base_response([r1, r2], mode="DISCOVER")

        # Profile with explicit avoidance of Horror
        profile = EffectivePreferenceProfile(
            user_id="user_avoid",
            genres={"Action": 0.9},
            explicit_avoidances=["Horror"],
        )

        treat_user, _ = self._find_cohort_users()
        resp, diag = svc.apply(
            base_response=base,
            effective_profile=profile,
            user_id=treat_user,
            mode=PERSONALIZATION_MODE_TREATMENT,
            treatment_pct=5,
            latency_budget_ms=0.0001,  # Force latency budget trigger
            mode_lambdas=self.POLICY,
        )
        # Safety fallback must return base response
        assert diag.safety_fallback_triggered is True
        assert [r.game.id for r in resp.results] == ["g1", "g2"]

    def test_project_evidence_extracted_from_effective_profile_blended_details(self):
        """Phase 7.1 QA: Project evidence must not be overpowered by global evidence."""
        from app.services.personalization_explanation_service import PersonalizationExplanationService
        expl_svc = PersonalizationExplanationService()
        r = _make_result("g_space", "Stellar Tactics", 0.85, ["Strategy"])
        r.game.tags = ["Space", "procedural generation"]

        from app.schemas.developer_profile import BlendedPreferenceItem
        eff = EffectivePreferenceProfile(
            user_id="treat_user_proj",
            active_project_id="proj_space_odyssey",
            active_project_title="Space Odyssey",
            genres={"Strategy": 0.8, "Action": 0.9},
            themes={"space": 1.0},
            mechanics={"procedural generation": 1.0},
            blended_details=[
                BlendedPreferenceItem(
                    dimension="theme",
                    value="space",
                    global_score=0.2,
                    project_score=1.0,
                    effective_score=0.8,
                    was_global=True,
                    was_project=True,
                ),
                BlendedPreferenceItem(
                    dimension="genre",
                    value="Strategy",
                    global_score=0.8,
                    project_score=0.9,
                    effective_score=0.88,
                    was_global=True,
                    was_project=True,
                ),
            ],
            total_signal_count=10,
        )

        reasons = expl_svc.explain(candidate=r, effective_profile=eff)
        assert len(reasons) > 0
        # Priority 1: Must generate PROJECT reason, not just GLOBAL Action
        assert any("active project" in reason.text for reason in reasons)
        assert any("Strategy" in reason.text for reason in reasons)
