"""
GameForge Personalization V1 — Phase 6: Shadow Mode, Feature Flag & Controlled A/B Integration
===============================================================================================

This module is the SINGLE integration point for personalization.

Architecture:
  Discovery Request
      ↓
  Existing Discovery Engine  (completely unchanged)
      ↓
  Base Top-K
      ↓
  PersonalizationExperimentService.apply()
      |
      ├── OFF      → return base results unchanged
      ├── SHADOW   → compute personalized ranking, record diagnostics, return BASE
      └── TREATMENT→ if user in cohort → return personalized; else → return base
      ↓
  Final HTTP Response

Core invariants (same as Phase 5):
- Production Discovery ranking is the default for ALL users.
- Cold start → personalized == base (exactly).
- Explicit constraints, avoidances, hard filters preserved.
- Any exception → return base result, record safety event.
- Gemini API calls = 0.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.developer_profile import (
    DeveloperPreferenceProfile,
    EffectivePreferenceProfile,
    ProjectPreferenceProfile,
)
from app.schemas.discovery import (
    DiscoverySearchResult,
    DiscoverySearchResponse,
)
from app.services.context_blender import context_blender
from app.services.personalization_explanation_service import (
    PersonalizationExplanationService,
)
from app.services.personalization_reranker import personalization_reranker


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mode constants
# ---------------------------------------------------------------------------

PERSONALIZATION_MODE_OFF = "OFF"
PERSONALIZATION_MODE_SHADOW = "SHADOW"
PERSONALIZATION_MODE_TREATMENT = "TREATMENT"

VALID_MODES = {PERSONALIZATION_MODE_OFF, PERSONALIZATION_MODE_SHADOW, PERSONALIZATION_MODE_TREATMENT}

# ---------------------------------------------------------------------------
# Change classification thresholds (Phase 6.1: Gap-Free & Mutually Exclusive)
# ---------------------------------------------------------------------------
# Partitioning of delta = (personalized_alignment - base_alignment):
#   BENEFICIAL: delta >= +0.05        (Meaningful profile alignment gain)
#   NEUTRAL:    -0.02 < delta < +0.05 (Negligible / acceptable movement without harm)
#   HARMFUL:    delta <= -0.02        (Detectable alignment regression)
#
# Every real number delta belongs to exactly one interval:
#   (-inf, -0.02]  -> HARMFUL
#   (-0.02, +0.05) -> NEUTRAL
#   [+0.05, +inf)  -> BENEFICIAL
_BENEFICIAL_MIN_ALIGNMENT_GAIN = 0.05
_HARMFUL_ALIGNMENT_LOSS = -0.02

# Dimension weights for Preference Alignment Score (same as re-ranker)
_W_GENRE = 0.35
_W_MECHANIC = 0.30
_W_THEME = 0.25
_W_MODE = 0.10


# ---------------------------------------------------------------------------
# Shadow / experiment diagnostics
# ---------------------------------------------------------------------------

@dataclass
class ExperimentDiagnostics:
    """
    Aggregated, privacy-safe experiment metrics recorded per request.
    NO raw query text or private profile data is stored here.
    """
    mode: str = PERSONALIZATION_MODE_OFF
    lambda_: float = 0.0
    profile_confidence_tier: str = "COLD"          # COLD / EMERGING / MODERATE / ESTABLISHED
    active_project: bool = False
    discovery_mode: str = "BEST_MATCH"             # BEST_MATCH / DISCOVER / HIDDEN_GEMS / POPULAR
    candidates_evaluated: int = 0
    candidates_moved: int = 0
    top5_churn: int = 0                             # number of positions changed in Top-5
    top10_churn: int = 0
    mean_abs_rank_delta: float = 0.0
    max_rank_delta: int = 0
    new_in_top5: int = 0                            # candidates entering Top-5 due to personalization
    left_top5: int = 0                              # candidates leaving Top-5 due to personalization
    preference_alignment_uplift: float = 0.0        # key metric: alignment(pers) - alignment(base)
    intent_violations: int = 0
    avoidance_violations: int = 0
    cold_regression: int = 0
    beneficial_changes: int = 0
    neutral_changes: int = 0
    harmful_changes: int = 0
    personalization_latency_ms: float = 0.0
    base_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    safety_fallback_triggered: bool = False
    safety_fallback_reason: str = ""
    user_in_treatment_cohort: bool = False
    no_evidence_personalization: bool = False
    base_top_k_ids: List[str] = field(default_factory=list)
    personalized_top_k_ids: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core alignment scoring utility
# ---------------------------------------------------------------------------

def _compute_profile_alignment(
    result: DiscoverySearchResult,
    effective_profile: EffectivePreferenceProfile,
) -> float:
    """
    Deterministic, LLM-free Preference Alignment Score in [0.0, 1.0].

    Measures how well a single search result matches the developer's
    effective preference profile across genre / mechanic / theme / mode.
    Used only for offline measurement; never used in ranking.
    """
    game = result.game

    # Candidate feature sets (lower-cased for case-insensitive matching)
    c_genres = {g.lower() for g in game.genres}
    c_mechanics = {t.lower() for t in game.tags}     # tags serve as mechanics proxy
    c_themes = {t.lower() for t in game.tags}
    c_modes = {m.lower() for m in game.player_modes}

    # Profile dimensions (lower-cased)
    p_genres = {k.lower(): v for k, v in effective_profile.genres.items()}
    p_mechanics = {k.lower(): v for k, v in effective_profile.mechanics.items()}
    p_themes = {k.lower(): v for k, v in effective_profile.themes.items()}
    p_modes = {k.lower(): v for k, v in effective_profile.modes.items()}

    # Best-matching score per dimension
    s_genre = max((p_genres.get(g, 0.0) for g in c_genres), default=0.0)
    s_mech = max((p_mechanics.get(m, 0.0) for m in c_mechanics), default=0.0)
    s_theme = max((p_themes.get(t, 0.0) for t in c_themes), default=0.0)
    s_mode = max((p_modes.get(md, 0.0) for md in c_modes), default=0.0)

    return (_W_GENRE * s_genre + _W_MECHANIC * s_mech + _W_THEME * s_theme + _W_MODE * s_mode)


def _mean_alignment(
    results: List[DiscoverySearchResult],
    effective_profile: EffectivePreferenceProfile,
    top_k: int = 5,
) -> float:
    """Return mean profile alignment score for the Top-K results."""
    top = results[:top_k]
    if not top:
        return 0.0
    return sum(_compute_profile_alignment(r, effective_profile) for r in top) / len(top)


def _classify_change(
    base_alignment: float,
    pers_alignment: float,
) -> str:
    """
    Classify a single Top-5 change as BENEFICIAL / NEUTRAL / HARMFUL.

    Mutually exclusive, gap-free boundaries:
      delta >= +0.05           -> BENEFICIAL
      -0.02 < delta < +0.05    -> NEUTRAL
      delta <= -0.02           -> HARMFUL
    """
    # Round delta to 6 decimal places to prevent IEEE 754 precision flutter
    delta = round(pers_alignment - base_alignment, 6)
    if delta >= _BENEFICIAL_MIN_ALIGNMENT_GAIN:
        return "BENEFICIAL"
    elif delta <= _HARMFUL_ALIGNMENT_LOSS:
        return "HARMFUL"
    else:
        return "NEUTRAL"


# ---------------------------------------------------------------------------
# Cohort assignment
# ---------------------------------------------------------------------------

def _user_in_treatment_cohort(user_id: str, treatment_pct: int) -> bool:
    """
    Deterministic, stable treatment cohort assignment.
    Uses hashlib.sha256(user_id) % 100 so the same user always receives
    the same cohort assignment regardless of request order or server restart.
    """
    if treatment_pct <= 0:
        return False
    if treatment_pct >= 100:
        return True
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    return bucket < treatment_pct


# ---------------------------------------------------------------------------
# Main experiment service
# ---------------------------------------------------------------------------

class PersonalizationExperimentService:
    """
    Single integration point for the Phase 6 personalization experiment.

    Responsibilities:
    - Read feature flag from settings (OFF / SHADOW / TREATMENT).
    - Assign user to control/treatment cohort deterministically.
    - In SHADOW: compute personalization internally, record diagnostics, return base result.
    - In TREATMENT: apply personalized ranking for cohort users; return base for non-cohort.
    - Classify every Top-5 change as BENEFICIAL / NEUTRAL / HARMFUL.
    - Compute Preference Alignment Uplift (key quality metric).
    - On any exception: fall back to base result, record safety event.
    - Attach grounded personalization explanations to TREATMENT results.
    """

    def __init__(self) -> None:
        self._explanation_service = PersonalizationExplanationService()
        self._history: List[ExperimentDiagnostics] = []

    def record_diagnostic(self, diag: ExperimentDiagnostics) -> None:
        """Store diagnostic in ring buffer (max 2000 entries)."""
        self._history.append(diag)
        if len(self._history) > 2000:
            self._history.pop(0)

    def get_history(self) -> List[ExperimentDiagnostics]:
        return list(self._history)

    def clear_history(self) -> None:
        self._history.clear()

    # ------------------------------------------------------------------
    # Primary entry point
    # ------------------------------------------------------------------

    def apply(
        self,
        base_response: DiscoverySearchResponse,
        effective_profile: Optional[EffectivePreferenceProfile],
        user_id: Optional[str],
        mode: str = PERSONALIZATION_MODE_OFF,
        lambda_: float = 0.05,
        treatment_pct: int = 0,
        latency_budget_ms: float = 50.0,
    ) -> Tuple[DiscoverySearchResponse, ExperimentDiagnostics]:
        """
        Apply the personalization experiment to a base Discovery response.

        Returns (final_response, diagnostics).
        - In OFF mode: returns base_response unchanged with minimal diagnostics.
        - In SHADOW mode: returns base_response, diagnostics contain the hypothetical impact.
        - In TREATMENT mode: returns personalized_response for cohort users; base for others.

        Any exception falls back to base_response.
        """
        diag = ExperimentDiagnostics(mode=mode, lambda_=lambda_)
        diag.discovery_mode = getattr(base_response, "mode", "BEST_MATCH") or "BEST_MATCH"

        # ── OFF: nothing to compute ──────────────────────────────────────────
        if mode not in VALID_MODES or mode == PERSONALIZATION_MODE_OFF:
            diag.mode = PERSONALIZATION_MODE_OFF
            return base_response, diag

        # ── Cold-start / missing profile: no-op regardless of mode ──────────
        if effective_profile is None:
            diag.cold_regression = len(base_response.results[:5])
            if mode == PERSONALIZATION_MODE_SHADOW:
                self.record_diagnostic(diag)
            return base_response, diag

        has_affinities = bool(
            effective_profile.genres
            or effective_profile.mechanics
            or effective_profile.themes
            or effective_profile.modes
        )
        if not has_affinities and effective_profile.preference_vector is None:
            # Truly cold profile — return base exactly
            diag.cold_regression = len(base_response.results[:5])
            if mode == PERSONALIZATION_MODE_SHADOW:
                self.record_diagnostic(diag)
            return base_response, diag

        # ── Cohort assignment (stable per user_id) ───────────────────────────
        user_in_cohort = (
            bool(user_id) and _user_in_treatment_cohort(user_id, treatment_pct)
        )
        diag.user_in_treatment_cohort = user_in_cohort
        diag.profile_confidence_tier = getattr(effective_profile, "confidence_tier", "COLD") or "COLD"
        diag.active_project = bool(effective_profile.active_project_id)

        try:
            return self._run_experiment(
                base_response=base_response,
                effective_profile=effective_profile,
                mode=mode,
                lambda_=lambda_,
                user_in_cohort=user_in_cohort,
                latency_budget_ms=latency_budget_ms,
                diag=diag,
            )
        except Exception as exc:
            logger.warning(
                "PersonalizationExperimentService: unhandled exception — falling back to base. %s",
                exc,
                exc_info=True,
            )
            diag.safety_fallback_triggered = True
            diag.safety_fallback_reason = f"unhandled_exception: {type(exc).__name__}"
            if mode == PERSONALIZATION_MODE_SHADOW:
                self.record_diagnostic(diag)
            return base_response, diag

    # ------------------------------------------------------------------
    # Internal experiment runner
    # ------------------------------------------------------------------

    def _run_experiment(
        self,
        base_response: DiscoverySearchResponse,
        effective_profile: EffectivePreferenceProfile,
        mode: str,
        lambda_: float,
        user_in_cohort: bool,
        latency_budget_ms: float,
        diag: ExperimentDiagnostics,
    ) -> Tuple[DiscoverySearchResponse, ExperimentDiagnostics]:
        """Core experiment logic (wrapped by apply() for exception safety)."""
        base_results = base_response.results
        if not base_results:
            return base_response, diag

        diag.candidates_evaluated = len(base_results)
        diag.discovery_mode = getattr(base_response, "mode", "BEST_MATCH") or "BEST_MATCH"
        diag.base_top_k_ids = [r.game.id for r in base_results[:10]]

        # ── Personalization computation (timed) ──────────────────────────────
        t0 = time.perf_counter()
        pers_results, traces = personalization_reranker.rerank(
            results=base_results,
            effective_profile=effective_profile,
            lambda_=lambda_,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        diag.personalization_latency_ms = round(elapsed_ms, 3)

        # Detect whether profile had any matching evidence for this query's candidates
        diag.no_evidence_personalization = all(t.personalization_score == 0.0 for t in traces)

        # ── Latency budget guard ──────────────────────────────────────────────
        if elapsed_ms > latency_budget_ms:
            logger.warning(
                "PersonalizationExperimentService: latency %.1f ms exceeded budget %.1f ms — fallback.",
                elapsed_ms,
                latency_budget_ms,
            )
            diag.safety_fallback_triggered = True
            diag.safety_fallback_reason = f"latency_budget_exceeded: {elapsed_ms:.1f}ms > {latency_budget_ms:.1f}ms"
            if mode == PERSONALIZATION_MODE_SHADOW:
                self.record_diagnostic(diag)
            return base_response, diag

        # ── Compute rank movement metrics ────────────────────────────────────
        base_ids = [r.game.id for r in base_results]
        pers_ids = [r.game.id for r in pers_results]
        diag.personalized_top_k_ids = pers_ids[:10]

        base_rank: Dict[str, int] = {gid: idx for idx, gid in enumerate(base_ids)}
        pers_rank: Dict[str, int] = {gid: idx for idx, gid in enumerate(pers_ids)}

        rank_deltas = []
        for gid in base_ids:
            b = base_rank.get(gid, 999)
            p = pers_rank.get(gid, 999)
            delta = abs(b - p)
            rank_deltas.append(delta)
            if delta > 0:
                diag.candidates_moved += 1

        diag.mean_abs_rank_delta = round(sum(rank_deltas) / len(rank_deltas), 3) if rank_deltas else 0.0
        diag.max_rank_delta = max(rank_deltas) if rank_deltas else 0

        base_top5 = set(base_ids[:5])
        pers_top5 = set(pers_ids[:5])
        diag.new_in_top5 = len(pers_top5 - base_top5)
        diag.left_top5 = len(base_top5 - pers_top5)
        diag.top5_churn = diag.new_in_top5
        diag.top10_churn = len(set(pers_ids[:10]) ^ set(base_ids[:10]))

        # ── Preference Alignment Uplift (key quality metric) ─────────────────
        base_alignment = _mean_alignment(base_results, effective_profile)
        pers_alignment = _mean_alignment(pers_results, effective_profile)
        diag.preference_alignment_uplift = round(pers_alignment - base_alignment, 4)

        # ── Classify Top-5 slot replacements ──────────────────────────────────
        # Compare personalized result vs base result at each Top-5 position that changed
        for i in range(min(5, len(pers_results), len(base_results))):
            if pers_results[i].game.id != base_results[i].game.id:
                pa = _compute_profile_alignment(pers_results[i], effective_profile)
                ba = _compute_profile_alignment(base_results[i], effective_profile)
                cls = _classify_change(ba, pa)
                if cls == "BENEFICIAL":
                    diag.beneficial_changes += 1
                elif cls == "HARMFUL":
                    diag.harmful_changes += 1
                else:
                    diag.neutral_changes += 1

        # ── SHADOW: return base result, record diagnostics only ──────────────
        if mode == PERSONALIZATION_MODE_SHADOW:
            self.record_diagnostic(diag)
            logger.debug(
                "PERSONALIZATION SHADOW: mode=%s uplift=%.4f top5_churn=%d moved=%d latency=%.1fms",
                diag.discovery_mode,
                diag.preference_alignment_uplift,
                diag.top5_churn,
                diag.candidates_moved,
                diag.personalization_latency_ms,
            )
            return base_response, diag

        # ── TREATMENT: apply only for cohort users ───────────────────────────
        if mode == PERSONALIZATION_MODE_TREATMENT:
            if not user_in_cohort:
                # Non-cohort user — return base (control path)
                return base_response, diag

            # Attach grounded explanations to genuinely-influenced results
            pers_results = self._attach_explanations(pers_results, base_rank, effective_profile)

            # Build treatment response (fully backward-compatible schema)
            treatment_response = DiscoverySearchResponse(
                query=base_response.query,
                match_count=base_response.match_count,
                no_strong_match=base_response.no_strong_match,
                query_type=base_response.query_type,
                target_entity=base_response.target_entity,
                mode=base_response.mode,
                why_these=base_response.why_these,
                personalized=True,
                personalization_evidence=[
                    f"Profile-aligned re-ranking (lambda={lambda_})"
                ],
                results=pers_results,
            )
            return treatment_response, diag

        # Fallback: unknown mode — return base
        return base_response, diag

    # ------------------------------------------------------------------
    # Grounded explanation attachment
    # ------------------------------------------------------------------

    def _attach_explanations(
        self,
        results: List[DiscoverySearchResult],
        base_rank: Dict[str, int],
        effective_profile: EffectivePreferenceProfile,
    ) -> List[DiscoverySearchResult]:
        """
        Attach personalization explanations only to results that were actually
        influenced by personalization (rank changed) AND have valid provenance.

        Returns a new list; original DiscoverySearchResult objects are not mutated.
        """
        updated: List[DiscoverySearchResult] = []
        for new_rank, result in enumerate(results):
            original_rank = base_rank.get(result.game.id, new_rank)
            actually_moved = original_rank != new_rank

            reasons: List[str] = []
            if actually_moved:
                # Build a plain dict for the explanation service
                candidate_dict = {
                    "id": result.game.id,
                    "title": result.game.title,
                    "genres": result.game.genres,
                    "tags": result.game.tags,
                    "player_modes": result.game.player_modes,
                    "score": result.score,
                }
                try:
                    p_reasons = self._explanation_service.generate_reasons(
                        candidate=candidate_dict,
                        effective_profile=effective_profile,
                    )
                    reasons = [r.text for r in p_reasons]
                except Exception as exc:
                    logger.debug("Explanation service error for %s: %s", result.game.id, exc)

            # Build a new result with explanations merged (no mutation)
            updated.append(
                DiscoverySearchResult(
                    game=result.game,
                    score=result.score,
                    match_highlights=result.match_highlights,
                    explanation=result.explanation,
                    is_hidden_gem=result.is_hidden_gem,
                    trade_offs=result.trade_offs,
                    personalization_reasons=reasons,
                )
            )
        return updated


# Module-level singleton
personalization_experiment_service = PersonalizationExperimentService()
