"""
GameForge Personalization V1 — Developer Preference Profile Schema
==================================================================
Strongly-typed, deterministic data contracts for the developer preference layer.
Preserves internal signal provenance for auditability and explainability.
"""

from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


ConfidenceTier = Literal["COLD", "EMERGING", "MODERATE", "ESTABLISHED"]
PreferenceDimension = Literal["genre", "mechanic", "theme", "mode", "avoidance", "suppression"]
PreferenceSource = Literal[
    "onboarding",
    "saved_discovery",
    "project",
    "feedback_dislike",
    "feedback_like",
    "session_context",
]


class PreferenceEvidence(BaseModel):
    """
    Traceable provenance for an aggregated preference signal.
    Preserves exact origin to explain 'Why does this preference exist?'.
    """
    dimension: PreferenceDimension = Field(..., description="Target dimension: genre, mechanic, theme, mode, etc.")
    value: str = Field(..., description="Canonical value, e.g. 'Strategy', 'deckbuilding', 'cyberpunk'")
    contribution: float = Field(ge=0.0, description="Numerical strength contribution of this evidence piece")
    source: PreferenceSource = Field(..., description="First-party origin of the signal")
    source_id: Optional[str] = Field(default=None, description="Referenced entity ID (game ID, project ID, etc.)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(extra="ignore")


class DeveloperPreferenceProfile(BaseModel):
    """
    Deterministic, strongly-typed internal representation of a developer's creative DNA.
    Aggregates first-party preferences, saved discoveries, and project metadata.
    """
    user_id: str = Field(..., description="Authenticated user ID")

    # 1. Categorical Affinities (normalized 0.0 - 1.0 confidence)
    genres: Dict[str, float] = Field(
        default_factory=dict,
        description="Normalized genre confidence scores (0.0 - 1.0) across 13 canonical genres",
    )
    mechanics: Dict[str, float] = Field(
        default_factory=dict,
        description="Normalized gameplay mechanic confidence scores (0.0 - 1.0)",
    )
    themes: Dict[str, float] = Field(
        default_factory=dict,
        description="Normalized visual and thematic aesthetic confidence scores (0.0 - 1.0)",
    )
    modes: Dict[str, float] = Field(
        default_factory=dict,
        description="Normalized player mode confidence scores (0.0 - 1.0)",
    )

    # 2. Negative Constraints & Suppressions (Absolute boundaries)
    explicit_avoidances: List[str] = Field(
        default_factory=list,
        description="Explicitly declared avoidance categories (e.g. ['Horror', 'PvP'])",
    )
    suppressed_game_ids: List[str] = Field(
        default_factory=list,
        description="Game IDs explicitly disliked or flagged 'less like this'",
    )

    # 3. Dense Semantic Vector Anchor (Diagnostic / experimental only in Phase 1)
    preference_vector: Optional[List[float]] = Field(
        default=None,
        description="384-dimensional normalized centroid vector, or None if insufficient vector sources",
    )

    # 4. Profile Maturity & Metadata
    total_signal_count: int = Field(default=0, ge=0, description="Total discrete signals aggregated")
    confidence_tier: ConfidenceTier = Field(default="COLD", description="Profile maturity tier")
    recent_focus_genre: Optional[str] = Field(default=None, description="Most recently active genre focus")
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when this profile snapshot was generated",
    )

    # 5. Signal Provenance (Internal evidence items)
    evidence: List[PreferenceEvidence] = Field(
        default_factory=list,
        description="Itemized evidence records explaining each preference dimension",
    )

    model_config = ConfigDict(extra="ignore")


class ProjectPreferenceProfile(BaseModel):
    """
    Structured preference DNA extracted from an active project context.
    Derived strictly from structured project data (genre, modules, design_spec, world_mode).
    """
    project_id: str = Field(..., description="Active project ID")
    title: str = Field(..., description="Project title")

    genres: Dict[str, float] = Field(default_factory=dict, description="Project genre affinities (0.0 - 1.0)")
    mechanics: Dict[str, float] = Field(default_factory=dict, description="Project gameplay mechanics (0.0 - 1.0)")
    themes: Dict[str, float] = Field(default_factory=dict, description="Project themes and visual aesthetics (0.0 - 1.0)")
    modes: Dict[str, float] = Field(default_factory=dict, description="Project player modes (0.0 - 1.0)")

    preference_vector: Optional[List[float]] = Field(
        default=None,
        description="384-dimensional normalized prompt semantic vector, or None",
    )
    context_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score based on structured DNA completeness",
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when this project profile was extracted",
    )
    evidence: List[PreferenceEvidence] = Field(
        default_factory=list,
        description="Provenance records attributed directly to this project",
    )

    model_config = ConfigDict(extra="ignore")


class BlendedPreferenceItem(BaseModel):
    """Detailed multi-source breakdown for a single preference term after blending."""
    dimension: PreferenceDimension
    value: str
    global_score: float = Field(ge=0.0, le=1.0)
    project_score: float = Field(ge=0.0, le=1.0)
    effective_score: float = Field(ge=0.0, le=1.0)
    was_global: bool = False
    was_project: bool = False

    model_config = ConfigDict(extra="ignore")


class EffectivePreferenceProfile(BaseModel):
    """
    Unified, context-aware preference profile resulting from blending global developer DNA
    with the currently active project context.
    
    Invariants:
    - Global explicit avoidances are ABSOLUTE and cannot be overridden by project context.
    - Missing project dimensions do not erase valid global preferences.
    - Switching or clearing active project never mutates the underlying global profile.
    """
    user_id: str
    active_project_id: Optional[str] = None
    active_project_title: Optional[str] = None
    confidence_tier: ConfidenceTier = Field(default="COLD", description="Profile maturity tier inherited from global developer DNA")

    # Blended categorical affinities (normalized 0.0 - 1.0)
    genres: Dict[str, float] = Field(default_factory=dict)
    mechanics: Dict[str, float] = Field(default_factory=dict)
    themes: Dict[str, float] = Field(default_factory=dict)
    modes: Dict[str, float] = Field(default_factory=dict)

    # Absolute constraints
    explicit_avoidances: List[str] = Field(default_factory=list)
    suppressed_game_ids: List[str] = Field(default_factory=list)

    # Semantic vector anchor (blended 384-dim centroid)
    preference_vector: Optional[List[float]] = None

    # Context blending parameters and conflict tracking
    blend_weights: Dict[str, float] = Field(
        default_factory=lambda: {"global": 0.30, "project": 0.70}
    )
    conflicts: List[str] = Field(
        default_factory=list,
        description="Documented conflict alerts, e.g. project requested a theme that global explicitly avoids",
    )
    recent_focus_genre: Optional[str] = None
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Detailed provenance & explainability trail
    evidence: List[PreferenceEvidence] = Field(default_factory=list)
    blended_details: List[BlendedPreferenceItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


ExplanationSource = Literal["PROJECT", "GLOBAL", "SAVED_DISCOVERY"]


class PersonalizationReason(BaseModel):
    """
    Structured, fully traceable personalization reason supporting an explanation.
    Grounded strictly in actual candidate attributes, profile affinities, and project context.
    """
    text: str = Field(..., description="Human-readable grounded explanation string")
    source: ExplanationSource = Field(..., description="Origin of the underlying signal: PROJECT, GLOBAL, SAVED_DISCOVERY")
    dimension: str = Field(..., description="Evidence dimension: genre, mechanic, theme, mode, saved_game")
    value: str = Field(..., description="Evidence term or referenced entity, e.g. 'Strategy', 'procedural generation', 'Shapebreaker'")
    confidence: float = Field(ge=0.0, le=1.0, description="Effective confidence score (0.0 - 1.0)")

    model_config = ConfigDict(extra="ignore")


class PersonalizationTrace(BaseModel):
    """
    Detailed, auditable scoring trace for a candidate in the personalization re-ranker.
    Captures exact base score, personalization boost, and rank movements.
    """
    candidate_id: str
    candidate_title: str
    base_discovery_score: float
    personalization_score: float
    personalization_sources: List[str] = Field(default_factory=list)
    personalization_dimensions: List[str] = Field(default_factory=list)
    effective_profile_confidence: float = 1.0
    lambda_: float = 0.0
    personalized_final_score: float
    base_rank: int
    personalized_rank: int
    rank_delta: int = 0  # base_rank - personalized_rank (>0 means rose in rank)
    matched_features: Dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")
