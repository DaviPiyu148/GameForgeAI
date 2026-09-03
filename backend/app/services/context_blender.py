"""
GameForge Personalization V1 — Context Blender Service
======================================================
Blends global developer preference profiles with active project-specific DNA.

Phase 3 Core Invariants:
- Global explicit avoidances are ABSOLUTE and can NEVER be overridden by project context.
- Missing project dimensions do not erase valid global preferences.
- Switching or clearing active projects never mutates the underlying global profile.
- 100% deterministic (zero randomness, zero LLM / Gemini calls).
- Preference ranking remains DISABLED in this phase.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from app.models.project import Project
from app.schemas.developer_profile import (
    BlendedPreferenceItem,
    DeveloperPreferenceProfile,
    EffectivePreferenceProfile,
    PreferenceDimension,
    PreferenceEvidence,
    ProjectPreferenceProfile,
)
from app.services.preference_aggregator import (
    MECHANIC_SYNONYMS,
    MODE_SYNONYMS,
    THEME_SYNONYMS,
    normalize_term,
)
from app.services.preference_service import CANONICAL_GENRES, PreferenceService

logger = logging.getLogger(__name__)


# ============================================================================
# Centralized Blending Policy Weights
# ============================================================================

DEFAULT_GLOBAL_CONTEXT_WEIGHT: float = 0.30
DEFAULT_PROJECT_CONTEXT_WEIGHT: float = 0.70


class ContextBlender:
    """
    Deterministic context blender that fuses long-term global developer preferences
    with active project context into an EffectivePreferenceProfile.
    """

    def __init__(
        self,
        global_weight: float = DEFAULT_GLOBAL_CONTEXT_WEIGHT,
        project_weight: float = DEFAULT_PROJECT_CONTEXT_WEIGHT,
        embedder: Optional[Any] = None,
    ):
        self.global_weight = global_weight
        self.project_weight = project_weight
        self._embedder = embedder

    def _get_embedder(self) -> Optional[Any]:
        if self._embedder is not None:
            return self._embedder
        try:
            from app.search.embedder import QueryEmbedder
            return QueryEmbedder.get_instance()
        except Exception as e:
            logger.debug("QueryEmbedder unavailable in ContextBlender: %s", e)
            return None

    def build_project_profile(
        self,
        project: Any,
        embedder: Optional[Any] = None,
        db: Optional[Any] = None,
    ) -> ProjectPreferenceProfile:
        """
        Extract structured preference DNA from a persisted Project model or ID.
        Derived strictly from structured metadata: genre, modules, design_spec, world_mode.
        """
        if isinstance(project, str) and db is not None:
            proj_entity = db.query(Project).filter(Project.id == project).first()
            if not proj_entity:
                raise ValueError(f"Project with ID '{project}' not found.")
            project = proj_entity

        now = datetime.now(timezone.utc)
        evidence: List[PreferenceEvidence] = []

        raw_genres: Dict[str, float] = {}
        raw_mechanics: Dict[str, float] = {}
        raw_themes: Dict[str, float] = {}
        raw_modes: Dict[str, float] = {}

        # 1. Project Genre
        if project.genre:
            c_genres = PreferenceService.map_to_canonical_genres([project.genre])
            for cg in c_genres:
                raw_genres[cg] = raw_genres.get(cg, 0.0) + 1.0
                evidence.append(
                    PreferenceEvidence(
                        dimension="genre",
                        value=cg,
                        contribution=1.0,
                        source="project",
                        source_id=project.id,
                        timestamp=project.updated_at or project.created_at or now,
                    )
                )

        # 2. Build Modules (parameters.modules)
        p_modules = project.modules or []
        if isinstance(p_modules, list):
            for mod in p_modules:
                if isinstance(mod, str):
                    norm_m = normalize_term(mod, MECHANIC_SYNONYMS)
                    if norm_m:
                        raw_mechanics[norm_m] = raw_mechanics.get(norm_m, 0.0) + 1.0
                        evidence.append(
                            PreferenceEvidence(
                                dimension="mechanic",
                                value=norm_m,
                                contribution=1.0,
                                source="project",
                                source_id=project.id,
                                timestamp=project.updated_at or project.created_at or now,
                            )
                        )

        # 3. Structured Design Spec DNA
        ds = project.design_spec
        if ds and isinstance(ds, dict):
            # Theme
            ds_theme = ds.get("theme")
            if ds_theme and isinstance(ds_theme, str):
                norm_t = normalize_term(ds_theme, THEME_SYNONYMS)
                if norm_t:
                    raw_themes[norm_t] = raw_themes.get(norm_t, 0.0) + 1.0
                    evidence.append(
                        PreferenceEvidence(
                            dimension="theme",
                            value=norm_t,
                            contribution=1.0,
                            source="project",
                            source_id=project.id,
                            timestamp=project.updated_at or project.created_at or now,
                        )
                    )

            # Selected Modules in design spec
            for mod in ds.get("selected_modules", []):
                if isinstance(mod, str):
                    norm_m = normalize_term(mod, MECHANIC_SYNONYMS)
                    if norm_m:
                        raw_mechanics[norm_m] = raw_mechanics.get(norm_m, 0.0) + 1.0
                        evidence.append(
                            PreferenceEvidence(
                                dimension="mechanic",
                                value=norm_m,
                                contribution=1.0,
                                source="project",
                                source_id=project.id,
                                timestamp=project.updated_at or project.created_at or now,
                            )
                        )

            # Player Abilities
            for ability in ds.get("player_abilities", []):
                if isinstance(ability, str):
                    norm_m = normalize_term(ability, MECHANIC_SYNONYMS)
                    if norm_m:
                        raw_mechanics[norm_m] = raw_mechanics.get(norm_m, 0.0) + 0.5
                        evidence.append(
                            PreferenceEvidence(
                                dimension="mechanic",
                                value=norm_m,
                                contribution=0.5,
                                source="project",
                                source_id=project.id,
                                timestamp=project.updated_at or project.created_at or now,
                            )
                        )

            # World Mode
            w_mode = ds.get("world_mode")
            if w_mode and isinstance(w_mode, str):
                norm_mode = normalize_term(w_mode, MODE_SYNONYMS)
                if norm_mode:
                    raw_modes[norm_mode] = raw_modes.get(norm_mode, 0.0) + 1.0
                    evidence.append(
                        PreferenceEvidence(
                            dimension="mode",
                            value=norm_mode,
                            contribution=1.0,
                            source="project",
                            source_id=project.id,
                            timestamp=project.updated_at or project.created_at or now,
                        )
                    )

        # Normalize project dimension dictionaries to 0.0 - 1.0
        genres = self._normalize_scores(raw_genres)
        mechanics = self._normalize_scores(raw_mechanics)
        themes = self._normalize_scores(raw_themes)
        modes = self._normalize_scores(raw_modes)

        # 4. Prompt Vector Generation
        active_embedder = embedder or self._get_embedder()
        project_vec: Optional[List[float]] = None
        if active_embedder and project.prompt and project.prompt.strip():
            try:
                p_vec = active_embedder.embed_query(project.prompt.strip()[:300])
                if p_vec is not None:
                    flat = p_vec.flatten().astype(np.float32)
                    norm = np.linalg.norm(flat)
                    if flat.shape[0] == 384 and norm > 0 and np.isfinite(flat).all():
                        project_vec = [float(x) for x in (flat / norm).tolist()]
            except Exception as ex:
                logger.debug("Failed to embed project prompt for project %s: %s", project.id, ex)

        # Context confidence score based on structured DNA completeness
        dna_signals = len(genres) + len(mechanics) + len(themes) + len(modes)
        context_conf = min(1.0, round(dna_signals / 5.0, 2)) if dna_signals > 0 else 0.0

        return ProjectPreferenceProfile(
            project_id=project.id,
            title=project.title,
            genres=genres,
            mechanics=mechanics,
            themes=themes,
            modes=modes,
            preference_vector=project_vec,
            context_confidence=context_conf,
            last_updated=now,
            evidence=evidence,
        )

    def blend(
        self,
        global_profile: DeveloperPreferenceProfile,
        project_profile: Optional[ProjectPreferenceProfile] = None,
        global_weight: Optional[float] = None,
        project_weight: Optional[float] = None,
    ) -> EffectivePreferenceProfile:
        """
        Fuse global developer profile with optional active project context.

        Blending Rules:
        - If project_profile is None: 100% global profile returned.
        - If global_profile is COLD: 100% project profile returned.
        - If both present: 30% global + 70% active project blend.
        - Missing dimension handling: If project has zero evidence in a dimension,
          global affinities are preserved intact without being dampened by 0.30.
        - Explicit avoidances: Global avoidances remain ABSOLUTE. Any project DNA
          colliding with global avoidance is suppressed and recorded as a conflict.
        """
        now = datetime.now(timezone.utc)
        w_global = self.global_weight if global_weight is None else global_weight
        w_project = self.project_weight if project_weight is None else project_weight

        # Case 1: No active project context
        if project_profile is None:
            return self._build_global_only_effective(global_profile, now)

        # Case 2: Global is cold (zero signals / empty affinities), project is active
        is_global_cold = (
            not global_profile.genres
            and not global_profile.mechanics
            and not global_profile.themes
            and not global_profile.modes
            and global_profile.total_signal_count == 0
        )
        if is_global_cold:
            return self._build_project_only_effective(global_profile.user_id, project_profile, now)

        # Case 3: Both Global and Project profiles have active signals
        conflicts: List[str] = []
        blended_details: List[BlendedPreferenceItem] = []

        # Enforce global explicit avoidances as ABSOLUTE constraints
        explicit_avoid_set = {a.lower() for a in global_profile.explicit_avoidances}

        # Check for conflicts
        for g_name in project_profile.genres.keys():
            if g_name.lower() in explicit_avoid_set:
                conflicts.append(
                    f"Conflict: Active project specifies genre '{g_name}', which is in developer explicit avoidances. Avoidance enforced."
                )
        for t_name in project_profile.themes.keys():
            if t_name.lower() in explicit_avoid_set:
                conflicts.append(
                    f"Conflict: Active project specifies theme '{t_name}', which is in developer explicit avoidances. Avoidance enforced."
                )

        # Blend dimensions with missing-evidence protection
        effective_genres = self._blend_single_dimension(
            dimension="genre",
            global_dict=global_profile.genres,
            project_dict=project_profile.genres,
            w_global=w_global,
            w_project=w_project,
            avoid_set=explicit_avoid_set,
            blended_details=blended_details,
        )

        effective_mechanics = self._blend_single_dimension(
            dimension="mechanic",
            global_dict=global_profile.mechanics,
            project_dict=project_profile.mechanics,
            w_global=w_global,
            w_project=w_project,
            avoid_set=explicit_avoid_set,
            blended_details=blended_details,
        )

        effective_themes = self._blend_single_dimension(
            dimension="theme",
            global_dict=global_profile.themes,
            project_dict=project_profile.themes,
            w_global=w_global,
            w_project=w_project,
            avoid_set=explicit_avoid_set,
            blended_details=blended_details,
        )

        effective_modes = self._blend_single_dimension(
            dimension="mode",
            global_dict=global_profile.modes,
            project_dict=project_profile.modes,
            w_global=w_global,
            w_project=w_project,
            avoid_set=explicit_avoid_set,
            blended_details=blended_details,
        )

        # Vector Blending (normalized 384-dimensional centroid)
        effective_vec = self._blend_vectors(
            vec_global=global_profile.preference_vector,
            vec_project=project_profile.preference_vector,
            w_global=w_global,
            w_project=w_project,
        )

        # Determine contextual focus genre: project top genre takes precedence if available
        recent_focus = None
        if effective_genres:
            recent_focus = next(iter(effective_genres.keys()))
        elif global_profile.recent_focus_genre:
            recent_focus = global_profile.recent_focus_genre

        # Combined evidence collection
        combined_evidence = list(global_profile.evidence) + list(project_profile.evidence)

        return EffectivePreferenceProfile(
            user_id=global_profile.user_id,
            active_project_id=project_profile.project_id,
            active_project_title=project_profile.title,
            confidence_tier=global_profile.confidence_tier,
            genres=effective_genres,
            mechanics=effective_mechanics,
            themes=effective_themes,
            modes=effective_modes,
            explicit_avoidances=list(global_profile.explicit_avoidances),
            suppressed_game_ids=list(global_profile.suppressed_game_ids),
            preference_vector=effective_vec,
            blend_weights={"global": w_global, "project": w_project},
            conflicts=conflicts,
            recent_focus_genre=recent_focus,
            last_updated=now,
            evidence=combined_evidence,
            blended_details=blended_details,
        )

    @classmethod
    def _blend_single_dimension(
        cls,
        dimension: PreferenceDimension,
        global_dict: Dict[str, float],
        project_dict: Dict[str, float],
        w_global: float,
        w_project: float,
        avoid_set: Set[str],
        blended_details: List[BlendedPreferenceItem],
    ) -> Dict[str, float]:
        """
        Blend a single dimension between global and project dictionaries.

        Missing-Dimension / Single-Source Protection Rules:
        - Term present in both: 0.30 * global + 0.70 * project
        - Term present in project only: 100% project score (NOT multiplied by 0.70)
        - Term present in global only: 100% global score (NOT multiplied by 0.30)
        Then normalized relative to the maximum raw score in the dimension.
        """
        all_keys = set(global_dict.keys()) | set(project_dict.keys())
        if not all_keys:
            return {}

        raw_blended: Dict[str, float] = {}

        for k in all_keys:
            # Absolute avoidance check
            if k.lower() in avoid_set:
                continue

            s_global = global_dict.get(k, 0.0)
            s_project = project_dict.get(k, 0.0)

            was_g = k in global_dict
            was_p = k in project_dict

            if was_g and was_p:
                raw_score = (w_global * s_global) + (w_project * s_project)
            elif was_p:
                raw_score = s_project
            else:  # was_g only
                raw_score = s_global

            raw_blended[k] = raw_score

        if not raw_blended:
            return {}

        # Normalize: effective_score = raw_score / max(1.0, max(raw_scores))
        denom = max(1.0, max(raw_blended.values()))
        norm_factor = 1.0 / denom if denom > 0.0 else 1.0

        normalized: Dict[str, float] = {}
        for k, raw in raw_blended.items():
            eff = round(min(1.0, raw * norm_factor), 4)
            normalized[k] = eff

            # Record traceable detail item
            blended_details.append(
                BlendedPreferenceItem(
                    dimension=dimension,
                    value=k,
                    global_score=round(global_dict.get(k, 0.0), 4),
                    project_score=round(project_dict.get(k, 0.0), 4),
                    effective_score=eff,
                    was_global=(k in global_dict),
                    was_project=(k in project_dict),
                )
            )

        # Sort descending by effective score, breaking ties by preferring active project items, then alphabetically
        def sort_key(item: Tuple[str, float]):
            val, score = item
            is_proj = 1 if val in project_dict else 0
            return (-score, -is_proj, val)

        return dict(sorted(normalized.items(), key=sort_key))

    @classmethod
    def _blend_vectors(
        cls,
        vec_global: Optional[List[float]],
        vec_project: Optional[List[float]],
        w_global: float,
        w_project: float,
    ) -> Optional[List[float]]:
        """Compute weighted normalized centroid vector between global and project vectors."""
        if vec_global is None and vec_project is None:
            return None
        if vec_global is not None and vec_project is None:
            return list(vec_global)
        if vec_global is None and vec_project is not None:
            return list(vec_project)

        vg = np.array(vec_global, dtype=np.float32)
        vp = np.array(vec_project, dtype=np.float32)

        if vg.shape[0] != 384 or vp.shape[0] != 384:
            return None

        combined = (w_global * vg) + (w_project * vp)
        norm = float(np.linalg.norm(combined))
        if norm <= 1e-6 or not np.isfinite(norm):
            return None

        normalized = (combined / norm).astype(np.float32)
        return [float(x) for x in normalized.tolist()]

    @classmethod
    def _build_global_only_effective(
        cls,
        global_profile: DeveloperPreferenceProfile,
        now: datetime,
    ) -> EffectivePreferenceProfile:
        """Construct an effective profile when no active project context is provided."""
        details: List[BlendedPreferenceItem] = []
        for dim, items in [
            ("genre", global_profile.genres),
            ("mechanic", global_profile.mechanics),
            ("theme", global_profile.themes),
            ("mode", global_profile.modes),
        ]:
            for k, v in items.items():
                details.append(
                    BlendedPreferenceItem(
                        dimension=dim,  # type: ignore
                        value=k,
                        global_score=v,
                        project_score=0.0,
                        effective_score=v,
                        was_global=True,
                        was_project=False,
                    )
                )

        return EffectivePreferenceProfile(
            user_id=global_profile.user_id,
            active_project_id=None,
            active_project_title=None,
            confidence_tier=global_profile.confidence_tier,
            genres=dict(global_profile.genres),
            mechanics=dict(global_profile.mechanics),
            themes=dict(global_profile.themes),
            modes=dict(global_profile.modes),
            explicit_avoidances=list(global_profile.explicit_avoidances),
            suppressed_game_ids=list(global_profile.suppressed_game_ids),
            preference_vector=list(global_profile.preference_vector) if global_profile.preference_vector else None,
            blend_weights={"global": 1.0, "project": 0.0},
            conflicts=[],
            recent_focus_genre=global_profile.recent_focus_genre,
            last_updated=now,
            evidence=list(global_profile.evidence),
            blended_details=details,
        )

    @classmethod
    def _build_project_only_effective(
        cls,
        user_id: str,
        project_profile: ProjectPreferenceProfile,
        now: datetime,
    ) -> EffectivePreferenceProfile:
        """Construct an effective profile when the developer has zero global history."""
        details: List[BlendedPreferenceItem] = []
        for dim, items in [
            ("genre", project_profile.genres),
            ("mechanic", project_profile.mechanics),
            ("theme", project_profile.themes),
            ("mode", project_profile.modes),
        ]:
            for k, v in items.items():
                details.append(
                    BlendedPreferenceItem(
                        dimension=dim,  # type: ignore
                        value=k,
                        global_score=0.0,
                        project_score=v,
                        effective_score=v,
                        was_global=False,
                        was_project=True,
                    )
                )

        top_genre = next(iter(project_profile.genres.keys())) if project_profile.genres else None

        return EffectivePreferenceProfile(
            user_id=user_id,
            active_project_id=project_profile.project_id,
            active_project_title=project_profile.title,
            confidence_tier="MODERATE",
            genres=dict(project_profile.genres),
            mechanics=dict(project_profile.mechanics),
            themes=dict(project_profile.themes),
            modes=dict(project_profile.modes),
            explicit_avoidances=[],
            suppressed_game_ids=[],
            preference_vector=list(project_profile.preference_vector) if project_profile.preference_vector else None,
            blend_weights={"global": 0.0, "project": 1.0},
            conflicts=[],
            recent_focus_genre=top_genre,
            last_updated=now,
            evidence=list(project_profile.evidence),
            blended_details=details,
        )

    @classmethod
    def _normalize_scores(cls, raw: Dict[str, float]) -> Dict[str, float]:
        """Normalize a dictionary of raw counts/weights to 0.0 - 1.0."""
        if not raw:
            return {}
        max_v = max(raw.values())
        if max_v <= 0.0:
            return {}
        norm = {k: round(float(v / max_v), 4) for k, v in raw.items()}
        return dict(sorted(norm.items(), key=lambda x: x[1], reverse=True))


context_blender = ContextBlender()
