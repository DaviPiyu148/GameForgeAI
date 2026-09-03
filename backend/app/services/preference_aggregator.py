"""
GameForge Personalization V1 — Deterministic Preference Aggregator Service
===========================================================================
Aggregates first-party developer preferences, saved game bookmarks, and project
specifications into a structured DeveloperPreferenceProfile with explicit provenance.

Phase 1 Invariants:
- 100% deterministic (zero randomness, zero LLM / Gemini calls).
- No Discovery ranking integration.
- Cold-start safety: no evidence -> no invented preferences.
- Explicit avoidances strictly separated from absent interest.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from sqlalchemy.orm import Session

from app.models.preference import UserGenrePreference
from app.models.project import Project
from app.models.saved_discovery import SavedDiscovery
from app.models.user import User
from app.schemas.developer_profile import (
    ConfidenceTier,
    DeveloperPreferenceProfile,
    PreferenceDimension,
    PreferenceEvidence,
    PreferenceSource,
)
from app.services.preference_service import CANONICAL_GENRES, PreferenceService

logger = logging.getLogger(__name__)


# ============================================================================
# Centralized Aggregation Weights & Policies (Phase 1 Conservative Defaults)
# ============================================================================

# Saved Discoveries Contribution Policy
SAVED_GAME_GENRE_WEIGHT: float = 2.0
SAVED_GAME_MECHANIC_WEIGHT: float = 1.0
SAVED_GAME_THEME_WEIGHT: float = 1.0
SAVED_GAME_MODE_WEIGHT: float = 1.0
SAVED_GAME_VECTOR_WEIGHT: float = 1.0

# Project & GameDesignSpec Contribution Policy
PROJECT_GENRE_WEIGHT: float = 2.5
PROJECT_MECHANIC_WEIGHT: float = 1.5
PROJECT_THEME_WEIGHT: float = 2.0
PROJECT_MODE_WEIGHT: float = 1.5
PROJECT_PROMPT_VECTOR_WEIGHT: float = 1.5

# Maturity Tier Boundaries
TIER_COLD_MAX_SIGNALS: int = 1
TIER_EMERGING_MAX_SIGNALS: int = 5
TIER_MODERATE_MAX_SIGNALS: int = 14
MIN_SOURCES_FOR_MODERATE: int = 2
MIN_SOURCES_FOR_ESTABLISHED: int = 2


# ============================================================================
# Canonical Taxonomy & Normalization Dictionaries
# ============================================================================

MECHANIC_SYNONYMS: Dict[str, str] = {
    # Deckbuilding
    "deckbuilder": "deckbuilding",
    "deck building": "deckbuilding",
    "deck-building": "deckbuilding",
    "card battler": "deckbuilding",
    "card game": "deckbuilding",
    "deck construction": "deckbuilding",
    # Building & Automation
    "base building": "base building",
    "base-building": "base building",
    "building": "base building",
    "city builder": "city builder",
    "tower defense": "tower defense",
    "tower-defense": "tower defense",
    "automation": "automation",
    "factory": "automation",
    "crafting": "crafting",
    "resource management": "resource management",
    # Combat & Mechanics
    "turn based": "turn-based",
    "turn-based": "turn-based",
    "turn based combat": "turn-based",
    "turn-based combat": "turn-based",
    "real time": "real-time",
    "real-time": "real-time",
    "procedural generation": "procedural generation",
    "procedural": "procedural generation",
    "procedural levels": "procedural generation",
    "twin stick": "twin-stick",
    "twin-stick": "twin-stick",
    "bullet hell": "bullet hell",
    "bullet-hell": "bullet hell",
    "permadeath": "permadeath",
    "perma death": "permadeath",
    "physics": "physics",
    "physics-based": "physics",
    "stealth": "stealth",
    "grid movement": "grid movement",
    "grid based movement": "grid movement",
    "loot": "loot",
    "loot drop": "loot",
    "metroidvania": "metroidvania",
    "exploration": "exploration",
    "platforming": "platforming",
    "precision platformer": "platforming",
    "puzzle solving": "puzzle solving",
    "logic": "puzzle solving",
    # Module & Ability mappings
    "combat system": "combat",
    "combat": "combat",
    "melee combat": "combat",
    "shoot": "ranged combat",
    "dash": "dash ability",
    "inventory system": "inventory",
    "inventory": "inventory",
    "dialogue system": "dialogue",
    "dialogue": "dialogue",
    "wave spawner": "wave survival",
    "wave survival": "wave survival",
    "enhanced npc behavior": "npc behavior",
}

THEME_SYNONYMS: Dict[str, str] = {
    "cyberpunk": "cyberpunk",
    "retro_arcade": "retro_arcade",
    "retro arcade": "retro_arcade",
    "arcade": "retro_arcade",
    "pixel art": "retro_arcade",
    "retro": "retro_arcade",
    "dungeon": "dungeon",
    "dark fantasy": "dungeon",
    "space": "space",
    "sci fi": "sci-fi",
    "sci-fi": "sci-fi",
    "science fiction": "sci-fi",
    "neon": "neon",
    "minimal": "minimal",
    "minimalist": "minimal",
    "fantasy": "fantasy",
    "medieval": "fantasy",
    "post-apocalyptic": "post-apocalyptic",
    "post apocalyptic": "post-apocalyptic",
    "steampunk": "steampunk",
    "horror": "horror",
    "psychological horror": "horror",
    "cozy": "cozy",
    "relaxing": "cozy",
    "nature": "nature",
    "farming": "cozy",
}

MODE_SYNONYMS: Dict[str, str] = {
    "singleplayer": "singleplayer",
    "single player": "singleplayer",
    "single-player": "singleplayer",
    "co-op": "co-op",
    "coop": "co-op",
    "cooperative": "co-op",
    "local co-op": "co-op",
    "online co-op": "co-op",
    "multiplayer": "multiplayer",
    "multi-player": "multiplayer",
    "pvp": "pvp",
    "competitive": "pvp",
    "linear": "singleplayer",
    "campaign": "singleplayer",
    "open_world": "open_world",
}


def normalize_term(term: str, synonym_map: Dict[str, str]) -> Optional[str]:
    """Normalize a raw tag, module name, or feature into a standardized canonical term."""
    clean = term.strip().lower()
    if clean in synonym_map:
        return synonym_map[clean]
    # Check substring match
    for syn_key, canonical in synonym_map.items():
        if syn_key in clean or clean in syn_key:
            return canonical
    return None


# ============================================================================
# Signal Adapter Interface (Architecture Audit Compliance)
# ============================================================================

class SignalAdapter:
    """
    Base contract for pluggable developer signal adapters.
    Identifies existing storage/API representations while keeping deferred
    signals disabled in Phase 1 until their multi-session semantics are benchmarked.
    """
    name: str = "base"
    enabled: bool = False

    def extract_evidence(self, db: Session, user_id: str) -> List[PreferenceEvidence]:
        """Extract evidence records if enabled. Returns empty list when disabled."""
        if not self.enabled:
            return []
        raise NotImplementedError


class SearchEngagementAdapter(SignalAdapter):
    """Adapter for discovery query telemetry (deferred in Phase 1)."""
    name = "search_engagement"
    enabled = False


class PlaytestTelemetryAdapter(SignalAdapter):
    """Adapter for playtest session duration and telemetry (deferred in Phase 1)."""
    name = "playtest_telemetry"
    enabled = False


class BuildInspirationAdapter(SignalAdapter):
    """Adapter for 'build similar' inspiration extraction (deferred in Phase 1)."""
    name = "build_inspiration"
    enabled = False


class FeedbackSignalAdapter(SignalAdapter):
    """Adapter for direct game recommendation like/dislike signals (deferred in Phase 1)."""
    name = "feedback"
    enabled = False


# ============================================================================
# Core Preference Aggregator
# ============================================================================

class PreferenceAggregator:
    """
    Deterministic aggregator that builds a DeveloperPreferenceProfile from
    first-party stored records: user_genre_preferences, saved_discoveries, and projects.
    """

    def __init__(
        self,
        catalog_manager: Optional[Any] = None,
        index_manager: Optional[Any] = None,
        embedder: Optional[Any] = None,
    ):
        self._catalog_manager = catalog_manager
        self._index_manager = index_manager
        self._embedder = embedder

    def _get_catalog_manager(self) -> Optional[Any]:
        if self._catalog_manager is not None:
            return self._catalog_manager
        try:
            from app.search.catalog import CatalogManager
            return CatalogManager.get_instance()
        except Exception as e:
            logger.debug("CatalogManager unavailable: %s", e)
            return None

    def _get_index_manager(self) -> Optional[Any]:
        if self._index_manager is not None:
            return self._index_manager
        try:
            from app.search.index import FAISSIndexManager
            return FAISSIndexManager.get_instance()
        except Exception as e:
            logger.debug("FAISSIndexManager unavailable: %s", e)
            return None

    def _get_embedder(self) -> Optional[Any]:
        if self._embedder is not None:
            return self._embedder
        try:
            from app.search.embedder import QueryEmbedder
            return QueryEmbedder.get_instance()
        except Exception as e:
            logger.debug("QueryEmbedder unavailable: %s", e)
            return None

    def build_profile(
        self,
        db: Session,
        user_id: str,
    ) -> DeveloperPreferenceProfile:
        """
        Construct a strongly-typed DeveloperPreferenceProfile for user_id.
        Returns a cold-start profile if the user does not exist or has zero signals.
        """
        now = datetime.now(timezone.utc)

        # 1. Cold-start guard: check user identity
        if not user_id or not user_id.strip():
            return self._cold_start_profile(user_id or "anonymous", now)

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return self._cold_start_profile(user_id, now)

        evidence: List[PreferenceEvidence] = []
        suppressed_game_ids: List[str] = []

        # 2. Extract explicit onboarding & genre preferences (user_genre_preferences)
        genre_prefs = (
            db.query(UserGenrePreference)
            .filter(UserGenrePreference.user_id == user_id)
            .all()
        )

        explicit_avoidances: List[str] = []
        latest_interaction_at: Optional[datetime] = None
        recent_focus_genre: Optional[str] = None

        for gp in genre_prefs:
            if gp.last_interaction_at:
                if latest_interaction_at is None or gp.last_interaction_at > latest_interaction_at:
                    latest_interaction_at = gp.last_interaction_at
                    recent_focus_genre = gp.genre

            # Check if this is an explicit avoidance (score == 0.0 and interaction_count > 1)
            if gp.score == 0.0 and gp.interaction_count > 1:
                explicit_avoidances.append(gp.genre)
                evidence.append(
                    PreferenceEvidence(
                        dimension="avoidance",
                        value=gp.genre,
                        contribution=1.0,
                        source="onboarding",
                        source_id=gp.id,
                        timestamp=gp.last_interaction_at or now,
                    )
                )
            elif gp.score > 0.0:
                evidence.append(
                    PreferenceEvidence(
                        dimension="genre",
                        value=gp.genre,
                        contribution=float(gp.score),
                        source="onboarding",
                        source_id=gp.id,
                        timestamp=gp.last_interaction_at or now,
                    )
                )

        # 3. Extract saved discoveries (saved_discoveries)
        saved_records = (
            db.query(SavedDiscovery)
            .filter(SavedDiscovery.user_id == user_id)
            .order_by(SavedDiscovery.created_at.desc())
            .all()
        )

        catalog_mgr = self._get_catalog_manager()
        index_mgr = self._get_index_manager()
        saved_vectors: List[np.ndarray] = []

        for sr in saved_records:
            app_id = str(sr.steam_app_id)
            game_meta = catalog_mgr.get_game(app_id) if catalog_mgr else None

            if game_meta:
                # Genres from saved game
                for g in game_meta.get("genres", []):
                    c_genres = PreferenceService.map_to_canonical_genres([g])
                    for cg in c_genres:
                        evidence.append(
                            PreferenceEvidence(
                                dimension="genre",
                                value=cg,
                                contribution=SAVED_GAME_GENRE_WEIGHT,
                                source="saved_discovery",
                                source_id=app_id,
                                timestamp=sr.created_at or now,
                            )
                        )

                # Mechanics & themes from tags
                for tag in game_meta.get("tags", []):
                    norm_mech = normalize_term(tag, MECHANIC_SYNONYMS)
                    if norm_mech:
                        evidence.append(
                            PreferenceEvidence(
                                dimension="mechanic",
                                value=norm_mech,
                                contribution=SAVED_GAME_MECHANIC_WEIGHT,
                                source="saved_discovery",
                                source_id=app_id,
                                timestamp=sr.created_at or now,
                            )
                        )
                    norm_theme = normalize_term(tag, THEME_SYNONYMS)
                    if norm_theme:
                        evidence.append(
                            PreferenceEvidence(
                                dimension="theme",
                                value=norm_theme,
                                contribution=SAVED_GAME_THEME_WEIGHT,
                                source="saved_discovery",
                                source_id=app_id,
                                timestamp=sr.created_at or now,
                            )
                        )

                # Player modes
                for mode in game_meta.get("player_modes", []):
                    norm_mode = normalize_term(mode, MODE_SYNONYMS)
                    if norm_mode:
                        evidence.append(
                            PreferenceEvidence(
                                dimension="mode",
                                value=norm_mode,
                                contribution=SAVED_GAME_MODE_WEIGHT,
                                source="saved_discovery",
                                source_id=app_id,
                                timestamp=sr.created_at or now,
                            )
                        )

            # Vector from FAISS index (reviewed-only or popular-20k pool)
            if index_mgr and index_mgr.is_ready():
                vec = index_mgr.get_vector(app_id)
                if vec is not None and vec.shape[-1] == 384 and np.isfinite(vec).all():
                    saved_vectors.append(vec.astype(np.float32))

        # 4. Extract project DNA (projects & design_spec)
        projects = (
            db.query(Project)
            .filter(Project.user_id == user_id)
            .order_by(Project.created_at.desc())
            .all()
        )

        project_prompt_vectors: List[np.ndarray] = []
        embedder = self._get_embedder()

        for p in projects:
            p_time = p.updated_at or p.created_at or now

            # Genre from project
            if p.genre:
                c_genres = PreferenceService.map_to_canonical_genres([p.genre])
                for cg in c_genres:
                    evidence.append(
                        PreferenceEvidence(
                            dimension="genre",
                            value=cg,
                            contribution=PROJECT_GENRE_WEIGHT,
                            source="project",
                            source_id=p.id,
                            timestamp=p_time,
                        )
                    )

            # Modules from build parameters
            p_modules = p.modules or []
            if isinstance(p_modules, list):
                for mod in p_modules:
                    if isinstance(mod, str):
                        norm_mech = normalize_term(mod, MECHANIC_SYNONYMS)
                        if norm_mech:
                            evidence.append(
                                PreferenceEvidence(
                                    dimension="mechanic",
                                    value=norm_mech,
                                    contribution=PROJECT_MECHANIC_WEIGHT,
                                    source="project",
                                    source_id=p.id,
                                    timestamp=p_time,
                                )
                            )

            # Structured Design Spec DNA
            if p.design_spec and isinstance(p.design_spec, dict):
                ds = p.design_spec

                # Theme
                ds_theme = ds.get("theme")
                if ds_theme and isinstance(ds_theme, str):
                    norm_theme = normalize_term(ds_theme, THEME_SYNONYMS)
                    if norm_theme:
                        evidence.append(
                            PreferenceEvidence(
                                dimension="theme",
                                value=norm_theme,
                                contribution=PROJECT_THEME_WEIGHT,
                                source="project",
                                source_id=p.id,
                                timestamp=p_time,
                            )
                        )

                # Selected Modules in Design Spec
                for mod in ds.get("selected_modules", []):
                    if isinstance(mod, str):
                        norm_mech = normalize_term(mod, MECHANIC_SYNONYMS)
                        if norm_mech:
                            evidence.append(
                                PreferenceEvidence(
                                    dimension="mechanic",
                                    value=norm_mech,
                                    contribution=PROJECT_MECHANIC_WEIGHT,
                                    source="project",
                                    source_id=p.id,
                                    timestamp=p_time,
                                )
                            )

                # Player Abilities
                for ability in ds.get("player_abilities", []):
                    if isinstance(ability, str):
                        norm_mech = normalize_term(ability, MECHANIC_SYNONYMS)
                        if norm_mech:
                            evidence.append(
                                PreferenceEvidence(
                                    dimension="mechanic",
                                    value=norm_mech,
                                    contribution=PROJECT_MECHANIC_WEIGHT * 0.5,
                                    source="project",
                                    source_id=p.id,
                                    timestamp=p_time,
                                )
                            )

                # World Mode / Camera
                w_mode = ds.get("world_mode")
                if w_mode and isinstance(w_mode, str):
                    norm_mode = normalize_term(w_mode, MODE_SYNONYMS)
                    if norm_mode:
                        evidence.append(
                            PreferenceEvidence(
                                dimension="mode",
                                value=norm_mode,
                                contribution=PROJECT_MODE_WEIGHT,
                                source="project",
                                source_id=p.id,
                                timestamp=p_time,
                            )
                        )

            # Project Prompt Vector (if embedder is loaded)
            if embedder and p.prompt and p.prompt.strip():
                try:
                    p_vec = embedder.embed_query(p.prompt.strip()[:300])
                    if p_vec is not None:
                        flat_vec = p_vec.flatten().astype(np.float32)
                        if flat_vec.shape[0] == 384 and np.isfinite(flat_vec).all():
                            project_prompt_vectors.append(flat_vec)
                except Exception as ex:
                    logger.debug("Failed to embed project prompt for project %s: %s", p.id, ex)

        # 5. Cold-Start Check
        if not evidence:
            return self._cold_start_profile(user_id, now)

        # 6. Aggregate Affinities per Dimension
        genres_conf = self._normalize_dimension(evidence, "genre")
        mechanics_conf = self._normalize_dimension(evidence, "mechanic")
        themes_conf = self._normalize_dimension(evidence, "theme")
        modes_conf = self._normalize_dimension(evidence, "mode")

        # 7. Preference Vector Computation (Diagnostic / Experimental)
        pref_vector: Optional[List[float]] = self._compute_preference_vector(
            saved_vectors=saved_vectors,
            project_vectors=project_prompt_vectors,
        )

        # 8. Maturity / Confidence Tier Determination
        total_signals = len(evidence)
        distinct_sources = {e.source for e in evidence}
        tier = self._classify_confidence_tier(total_signals, distinct_sources)

        # Deduplicate avoidances preserving order
        seen_av: Set[str] = set()
        dedup_avoidances: List[str] = []
        for av in explicit_avoidances:
            if av not in seen_av:
                seen_av.add(av)
                dedup_avoidances.append(av)

        return DeveloperPreferenceProfile(
            user_id=user_id,
            genres=genres_conf,
            mechanics=mechanics_conf,
            themes=themes_conf,
            modes=modes_conf,
            explicit_avoidances=dedup_avoidances,
            suppressed_game_ids=suppressed_game_ids,
            preference_vector=pref_vector,
            total_signal_count=total_signals,
            confidence_tier=tier,
            recent_focus_genre=recent_focus_genre,
            last_updated=now,
            evidence=evidence,
        )

    @classmethod
    def _cold_start_profile(cls, user_id: str, now: datetime) -> DeveloperPreferenceProfile:
        """Return an unpersonalized baseline profile with zero inferred preferences."""
        return DeveloperPreferenceProfile(
            user_id=user_id,
            genres={},
            mechanics={},
            themes={},
            modes={},
            explicit_avoidances=[],
            suppressed_game_ids=[],
            preference_vector=None,
            total_signal_count=0,
            confidence_tier="COLD",
            recent_focus_genre=None,
            last_updated=now,
            evidence=[],
        )

    @classmethod
    def _normalize_dimension(
        cls,
        evidence: List[PreferenceEvidence],
        dimension: PreferenceDimension,
    ) -> Dict[str, float]:
        """Group evidence by canonical value and normalize to 0.0 - 1.0 confidence."""
        scores: Dict[str, float] = {}
        for ev in evidence:
            if ev.dimension == dimension and ev.value:
                scores[ev.value] = scores.get(ev.value, 0.0) + ev.contribution

        if not scores:
            return {}

        max_score = max(scores.values())
        if max_score <= 0.0:
            return {}

        normalized: Dict[str, float] = {}
        for val, sc in scores.items():
            conf = min(1.0, sc / max_score)
            normalized[val] = round(float(conf), 4)

        # Sort descending by normalized confidence
        return dict(sorted(normalized.items(), key=lambda item: item[1], reverse=True))

    @classmethod
    def _compute_preference_vector(
        cls,
        saved_vectors: List[np.ndarray],
        project_vectors: List[np.ndarray],
    ) -> Optional[List[float]]:
        """
        Compute 384-dimensional normalized preference centroid vector.
        Formula: normalize( sum(saved_vectors) + 1.5 * sum(project_vectors) )
        """
        if not saved_vectors and not project_vectors:
            return None

        combined = np.zeros((384,), dtype=np.float32)

        for sv in saved_vectors:
            norm_sv = np.linalg.norm(sv)
            if norm_sv > 0:
                combined += (sv / norm_sv) * SAVED_GAME_VECTOR_WEIGHT

        for pv in project_vectors:
            norm_pv = np.linalg.norm(pv)
            if norm_pv > 0:
                combined += (pv / norm_pv) * PROJECT_PROMPT_VECTOR_WEIGHT

        total_norm = float(np.linalg.norm(combined))
        if total_norm <= 1e-6 or not np.isfinite(total_norm):
            return None

        normalized_vec = (combined / total_norm).astype(np.float32)

        # Validation invariants
        if normalized_vec.shape[0] != 384:
            return None
        if not np.isfinite(normalized_vec).all():
            return None

        return [float(x) for x in normalized_vec.tolist()]

    @classmethod
    def _classify_confidence_tier(
        cls,
        total_signals: int,
        distinct_sources: Set[PreferenceSource],
    ) -> ConfidenceTier:
        """
        Classify maturity tier deterministically:
        - COLD: < 2 signals
        - EMERGING: 2 <= signals <= 5 (or single-source)
        - MODERATE: 6 <= signals <= 14 with >= 2 distinct sources
        - ESTABLISHED: >= 15 signals with >= 2 distinct sources
        """
        if total_signals <= TIER_COLD_MAX_SIGNALS:
            return "COLD"
        if total_signals <= TIER_EMERGING_MAX_SIGNALS:
            return "EMERGING"

        num_sources = len(distinct_sources)
        if total_signals <= TIER_MODERATE_MAX_SIGNALS:
            return "MODERATE" if num_sources >= MIN_SOURCES_FOR_MODERATE else "EMERGING"

        return "ESTABLISHED" if num_sources >= MIN_SOURCES_FOR_ESTABLISHED else "MODERATE"


preference_aggregator = PreferenceAggregator()
