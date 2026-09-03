"""
GameForge Personalization V1 — Grounded Deterministic Personalization Explanation Service
========================================================================================
Generates grounded, factual, template-based personalization explanations for search results.

Core Invariants:
- Absolute Groundedness: Explains ONLY evidence that actually exists in the candidate and profile.
- No Evidence -> No Explanation: If candidate does not match sufficient evidence, returns [].
- Project Context Priority: Active project evidence is prioritized over global preferences.
- Clear Distinction: Distinguishes temporary project context from long-term developer identity.
- Absolute Avoidance Safety: Never produces reasons mentioning explicitly avoided categories.
- Suppressed Game Safety: Never produces reasons for suppressed/disliked games.
- Deterministic & LLM-Free: Zero Gemini calls (0), zero external network calls, zero hallucinations.
- Discovery Ranking Integration: DISABLED.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

from app.schemas.developer_profile import (
    DeveloperPreferenceProfile,
    EffectivePreferenceProfile,
    PersonalizationReason,
    ProjectPreferenceProfile,
)
from app.services.preference_aggregator import (
    MECHANIC_SYNONYMS,
    MODE_SYNONYMS,
    THEME_SYNONYMS,
    normalize_term,
)
from app.services.preference_service import PreferenceService


# ============================================================================
# Centralized Configurable Explanation Thresholds
# ============================================================================

MIN_GLOBAL_EXPLANATION_AFFINITY: float = 0.50
MIN_PROJECT_EXPLANATION_AFFINITY: float = 0.50
MIN_VECTOR_SIMILARITY: float = 0.75
MAX_REASONS_PER_RESULT: int = 2


class PersonalizationExplanationService:
    """
    Deterministic, side-effect free service for generating grounded explanations.
    """

    def __init__(
        self,
        min_global_affinity: float = MIN_GLOBAL_EXPLANATION_AFFINITY,
        min_project_affinity: float = MIN_PROJECT_EXPLANATION_AFFINITY,
        min_vector_similarity: float = MIN_VECTOR_SIMILARITY,
        max_reasons: int = MAX_REASONS_PER_RESULT,
    ):
        self.min_global_affinity = min_global_affinity
        self.min_project_affinity = min_project_affinity
        self.min_vector_similarity = min_vector_similarity
        self.max_reasons = max_reasons

    def explain(
        self,
        candidate: Any,
        global_profile: Optional[DeveloperPreferenceProfile] = None,
        project_profile: Optional[ProjectPreferenceProfile] = None,
        effective_profile: Optional[EffectivePreferenceProfile] = None,
        saved_discovery_similarities: Optional[List[Tuple[str, float]]] = None,
    ) -> List[PersonalizationReason]:
        """
        Generate up to `max_reasons` deterministic personalization reasons grounded strictly
        in candidate metadata, active project context, and developer preference profiles.

        Returns an empty list [] if:
        - Profiles are absent or cold (no evidence).
        - Candidate is suppressed/disliked.
        - Candidate does not meet the minimum explanation affinity threshold.
        """
        # 1. Resolve Effective Profile & Constraints
        eff = effective_profile
        if eff is None and global_profile is not None:
            from app.services.context_blender import context_blender
            eff = context_blender.blend(global_profile, project_profile)

        if eff is None:
            return []

        # 2. Extract Candidate Attributes
        c_id, c_title, c_genres, c_mechanics, c_themes, c_modes = self._extract_candidate_features(candidate)

        # 3. Suppressed Game Guard: Never personalize a suppressed/disliked game
        if c_id and c_id in eff.suppressed_game_ids:
            return []
        if global_profile and c_id and c_id in global_profile.suppressed_game_ids:
            return []

        # 4. Explicit Avoidances Guard: Identify banned terms (must never appear in reasons)
        avoid_set = {a.lower() for a in eff.explicit_avoidances}
        if global_profile:
            avoid_set.update(a.lower() for a in global_profile.explicit_avoidances)

        candidate_reasons: List[PersonalizationReason] = []

        # 5. Priority 1: Active Project Evidence
        # Only fire if project is genuinely active and context is present
        proj_themes: Dict[str, float] = {}
        proj_mechanics: Dict[str, float] = {}
        proj_genres: Dict[str, float] = {}
        proj_modes: Dict[str, float] = {}

        if project_profile:
            proj_themes = project_profile.themes
            proj_mechanics = project_profile.mechanics
            proj_genres = project_profile.genres
            proj_modes = project_profile.modes
        elif eff.active_project_id:
            # Reconstruct project evidence directly from blended_details or evidence on eff
            if getattr(eff, "blended_details", None):
                for b_item in eff.blended_details:
                    if getattr(b_item, "project_score", 0.0) > 0:
                        dim = getattr(b_item, "dimension", None)
                        term = getattr(b_item, "value", None) or getattr(b_item, "term", None)
                        if dim == "theme" and term:
                            proj_themes[term] = b_item.project_score
                        elif dim == "mechanic" and term:
                            proj_mechanics[term] = b_item.project_score
                        elif dim == "genre" and term:
                            proj_genres[term] = b_item.project_score
                        elif dim == "mode" and term:
                            proj_modes[term] = b_item.project_score
            if getattr(eff, "evidence", None):
                for ev in eff.evidence:
                    if str(getattr(ev, "source", "")).lower() == "project":
                        dim = getattr(ev, "dimension", None)
                        val = getattr(ev, "value", None)
                        contrib = getattr(ev, "contribution", 1.0)
                        if dim == "theme" and val and val not in proj_themes:
                            proj_themes[val] = contrib
                        elif dim == "mechanic" and val and val not in proj_mechanics:
                            proj_mechanics[val] = contrib
                        elif dim == "genre" and val and val not in proj_genres:
                            proj_genres[val] = contrib
                        elif dim == "mode" and val and val not in proj_modes:
                            proj_modes[val] = contrib

        if eff.active_project_id and (proj_themes or proj_mechanics or proj_genres or proj_modes):
            # A. Project Themes
            for theme in sorted(c_themes):
                if theme.lower() in avoid_set:
                    continue
                score = proj_themes.get(theme, 0.0)
                if score >= self.min_project_affinity:
                    candidate_reasons.append(
                        PersonalizationReason(
                            text=f"Recommended for your active project because it matches its {theme.title()} theme.",
                            source="PROJECT",
                            dimension="theme",
                            value=theme,
                            confidence=score,
                        )
                    )

            # B. Project Mechanics
            for mech in sorted(c_mechanics):
                if mech.lower() in avoid_set:
                    continue
                score = proj_mechanics.get(mech, 0.0)
                if score >= self.min_project_affinity:
                    candidate_reasons.append(
                        PersonalizationReason(
                            text=f"Recommended for your active project because it matches its {mech} mechanics.",
                            source="PROJECT",
                            dimension="mechanic",
                            value=mech,
                            confidence=score,
                        )
                    )

            # C. Project Genres
            for genre in sorted(c_genres):
                if genre.lower() in avoid_set:
                    continue
                score = proj_genres.get(genre, 0.0)
                if score >= self.min_project_affinity:
                    candidate_reasons.append(
                        PersonalizationReason(
                            text=f"Recommended for your active project because it aligns with its {genre} genre.",
                            source="PROJECT",
                            dimension="genre",
                            value=genre,
                            confidence=score,
                        )
                    )

            # D. Project Player Modes
            for mode in sorted(c_modes):
                if mode.lower() in avoid_set:
                    continue
                score = proj_modes.get(mode, 0.0)
                if score >= self.min_project_affinity:
                    candidate_reasons.append(
                        PersonalizationReason(
                            text=f"Recommended for your active project because it matches its {mode} player mode.",
                            source="PROJECT",
                            dimension="mode",
                            value=mode,
                            confidence=score,
                        )
                    )

        # 6. Priority 2: Explicit Global Preferences
        # Explains long-term developer preferences without using project language
        g_prof = global_profile or eff
        if g_prof and getattr(g_prof, "total_signal_count", 1) > 0:
            # A. Global Genres
            for genre in sorted(c_genres):
                if genre.lower() in avoid_set:
                    continue
                score = g_prof.genres.get(genre, 0.0)
                if score >= self.min_global_affinity:
                    candidate_reasons.append(
                        PersonalizationReason(
                            text=f"Matches your long-term interest in {genre} games.",
                            source="GLOBAL",
                            dimension="genre",
                            value=genre,
                            confidence=score,
                        )
                    )

            # B. Global Mechanics
            for mech in sorted(c_mechanics):
                if mech.lower() in avoid_set:
                    continue
                score = g_prof.mechanics.get(mech, 0.0)
                if score >= self.min_global_affinity:
                    candidate_reasons.append(
                        PersonalizationReason(
                            text=f"Matches your preference for {mech} mechanics.",
                            source="GLOBAL",
                            dimension="mechanic",
                            value=mech,
                            confidence=score,
                        )
                    )

            # C. Global Themes
            for theme in sorted(c_themes):
                if theme.lower() in avoid_set:
                    continue
                score = g_prof.themes.get(theme, 0.0)
                if score >= self.min_global_affinity:
                    candidate_reasons.append(
                        PersonalizationReason(
                            text=f"Matches your interest in {theme.title()} settings.",
                            source="GLOBAL",
                            dimension="theme",
                            value=theme,
                            confidence=score,
                        )
                    )

            # D. Global Modes
            for mode in sorted(c_modes):
                if mode.lower() in avoid_set:
                    continue
                score = g_prof.modes.get(mode, 0.0)
                if score >= self.min_global_affinity:
                    candidate_reasons.append(
                        PersonalizationReason(
                            text=f"Matches your preference for {mode} games.",
                            source="GLOBAL",
                            dimension="mode",
                            value=mode,
                            confidence=score,
                        )
                    )

        # 7. Priority 3: Saved Discovery Similarity
        # Requires a concrete saved game anchor with cosine similarity >= threshold
        if saved_discovery_similarities:
            for saved_title, sim_score in saved_discovery_similarities:
                if sim_score >= self.min_vector_similarity and saved_title and saved_title.strip():
                    candidate_reasons.append(
                        PersonalizationReason(
                            text=f"Similar gameplay feel to your saved discovery '{saved_title.strip()}'.",
                            source="SAVED_DISCOVERY",
                            dimension="saved_game",
                            value=saved_title.strip(),
                            confidence=round(sim_score, 4),
                        )
                    )

        if not candidate_reasons:
            return []

        # 8. Deduplicate and Order Deterministically
        seen_keys: Set[Tuple[str, str, str]] = set()
        deduped: List[PersonalizationReason] = []
        for r in candidate_reasons:
            key = (r.source, r.dimension, r.value)
            if key not in seen_keys:
                seen_keys.add(key)
                deduped.append(r)

        # Dimension priority: fundamental game attributes (genre/mechanic/theme) over format (mode)
        dim_priority = {
            "genre": 0,
            "mechanic": 1,
            "theme": 2,
            "saved_game": 3,
            "mode": 4,
        }

        def reason_sort_key(r: PersonalizationReason):
            d_order = dim_priority.get(r.dimension, 5)
            return (d_order, -r.confidence, r.value)

        project_reasons = sorted([r for r in deduped if r.source == "PROJECT"], key=reason_sort_key)
        global_reasons = sorted([r for r in deduped if r.source == "GLOBAL"], key=reason_sort_key)
        saved_reasons = sorted([r for r in deduped if r.source == "SAVED_DISCOVERY"], key=reason_sort_key)

        selected: List[PersonalizationReason] = []

        # If both project and global evidence exist, balance with 1 project + 1 global reason
        if project_reasons and global_reasons:
            selected.append(project_reasons[0])
            selected.append(global_reasons[0])
        elif project_reasons:
            selected.extend(project_reasons[: self.max_reasons])
        elif global_reasons:
            selected.extend(global_reasons[: self.max_reasons])

        # Fill any remaining slots with saved discovery similarity if available
        if len(selected) < self.max_reasons and saved_reasons:
            for sr in saved_reasons:
                if len(selected) >= self.max_reasons:
                    break
                if sr not in selected:
                    selected.append(sr)

        return selected[: self.max_reasons]

    @classmethod
    def _extract_candidate_features(
        cls, candidate: Any
    ) -> Tuple[str, str, Set[str], Set[str], Set[str], Set[str]]:
        """
        Extract normalized features from candidate dictionary or Pydantic model.
        Returns: (game_id, title, genres, mechanics, themes, modes)
        """
        game_id = ""
        title = ""
        raw_genres: List[str] = []
        raw_tags: List[str] = []
        raw_modes: List[str] = []

        if isinstance(candidate, dict):
            game_id = str(candidate.get("id") or candidate.get("game_id") or candidate.get("external_id") or "")
            title = str(candidate.get("title") or "")
            raw_genres = candidate.get("genres") or []
            raw_tags = candidate.get("tags") or []
            raw_modes = candidate.get("player_modes") or []
        elif hasattr(candidate, "game"):
            # Candidate is a DiscoverySearchResult wrapper
            inner = candidate.game
            return cls._extract_candidate_features(inner)
        else:
            # Candidate is GameDiscoveryItem or similar object
            game_id = str(getattr(candidate, "id", "") or getattr(candidate, "external_id", ""))
            title = str(getattr(candidate, "title", ""))
            raw_genres = getattr(candidate, "genres", []) or []
            raw_tags = getattr(candidate, "tags", []) or []
            raw_modes = getattr(candidate, "player_modes", []) or []

        # 1. Canonical Genres (Exact and synonym match, preventing 'sports' -> 'rts' collisions)
        from app.services.preference_service import CANONICAL_GENRES, GENRE_SYNONYMS
        c_genres: Set[str] = set()
        for g in raw_genres:
            if not isinstance(g, str):
                continue
            norm_g = g.lower().strip()
            # Direct canonical match
            for canonical in CANONICAL_GENRES:
                if canonical.lower() == norm_g:
                    c_genres.add(canonical)
            # Exact synonym match
            if norm_g in GENRE_SYNONYMS:
                c_genres.add(GENRE_SYNONYMS[norm_g])

        # 2. Normalized Mechanics
        c_mechanics: Set[str] = set()
        for t in raw_tags:
            if isinstance(t, str):
                nm = normalize_term(t, MECHANIC_SYNONYMS)
                if nm:
                    c_mechanics.add(nm)

        # 3. Normalized Themes
        c_themes: Set[str] = set()
        for t in raw_tags:
            if isinstance(t, str):
                nt = normalize_term(t, THEME_SYNONYMS)
                if nt:
                    c_themes.add(nt)

        # 4. Normalized Player Modes
        c_modes: Set[str] = set()
        for m in raw_modes:
            if isinstance(m, str):
                n_mode = normalize_term(m, MODE_SYNONYMS)
                if n_mode:
                    c_modes.add(n_mode)

        return game_id, title, c_genres, c_mechanics, c_themes, c_modes


personalization_explanation_service = PersonalizationExplanationService()
