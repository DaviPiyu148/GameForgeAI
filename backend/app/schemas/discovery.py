from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class StorefrontItem(BaseModel):
    """Structured representation of verified game store availability."""

    model_config = ConfigDict(extra="ignore")

    provider: str = Field(..., description="Store provider identifier: steam, epic, gog, playstation, xbox, nintendo, itch")
    name: str = Field(..., description="Human-readable storefront name, e.g. Steam, Epic Games Store, GOG")
    url: str = Field(..., description="Direct validated HTTP(S) URL to the game's storefront page")
    platform: Optional[str] = Field(default="PC", description="Platform, e.g. PC, PlayStation, Xbox, Nintendo Switch")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v or not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("Storefront URL must be a valid HTTP or HTTPS address.")
        lower_v = v.lower()
        if any(bad in lower_v for bad in ["javascript:", "data:", "file:", "vbscript:", "<script"]):
            raise ValueError("Storefront URL contains prohibited or unsafe scheme.")
        return v


class DiscoveryFilters(BaseModel):
    """Supported deterministic hard constraints for game discovery search."""

    model_config = ConfigDict(extra="forbid")

    platforms: Optional[List[str]] = Field(default=None, max_length=10)
    player_modes: Optional[List[str]] = Field(default=None, max_length=10)
    genres: Optional[List[str]] = Field(default=None, max_length=20)
    tags: Optional[List[str]] = Field(default=None, max_length=20)
    is_free: Optional[bool] = None
    min_year: Optional[int] = Field(default=None, ge=1970, le=2035)
    max_year: Optional[int] = Field(default=None, ge=1970, le=2035)


class DiscoverySessionContext(BaseModel):
    """Client-side session context and interactive refinements for discovery."""

    model_config = ConfigDict(extra="ignore")

    refinements: Optional[List[str]] = Field(default=None, description="Active refinement tags, e.g. 'More Relaxing', 'Less Combat'")
    less_like_this_game_ids: Optional[List[str]] = Field(default=None, description="Game IDs user selected 'Less Like This' for in current session")
    temporary_avoid_tags: Optional[List[str]] = Field(default=None, description="Session-scoped avoid tags")
    temporary_avoid_genres: Optional[List[str]] = Field(default=None, description="Session-scoped avoid genres")
    surprise_seed: Optional[int] = Field(default=None, description="Stable seed for deterministic Surprise Me perturbation")


class DiscoveryFeedbackRequest(BaseModel):
    """Request payload for POST /api/discovery/feedback."""

    model_config = ConfigDict(extra="forbid")

    game_id: str = Field(..., description="Canonical game ID or Steam App ID")
    feedback: str = Field(..., description="Interaction signal: 'like', 'dislike', 'less_like_this'")

    @field_validator("feedback")
    @classmethod
    def validate_feedback(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in ("like", "dislike", "less_like_this"):
            raise ValueError("Feedback must be one of: 'like', 'dislike', 'less_like_this'.")
        return clean


class DiscoveryFeedbackResponse(BaseModel):
    """Response payload for POST /api/discovery/feedback."""

    model_config = ConfigDict(extra="forbid")

    status: str = "success"
    game_id: str
    feedback: str
    message: str


class DiscoverySearchRequest(BaseModel):
    """Inbound search request payload for POST /api/discovery/search."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Natural language game search query or concept description",
    )
    limit: int = Field(
        default=12,
        ge=1,
        le=50,
        description="Maximum number of games to return",
    )
    filters: Optional[DiscoveryFilters] = None
    mode: Optional[str] = Field(
        default="BEST_MATCH",
        description="Discovery ranking mode: 'BEST_MATCH', 'DISCOVER', 'HIDDEN_GEMS', 'POPULAR'",
    )
    session_context: Optional[DiscoverySessionContext] = Field(
        default=None,
        description="Optional session-scoped context, refinements, and temporary negative preferences",
    )



class MoreLikeThisRequest(BaseModel):
    """Request payload for POST /api/discovery/more-like-this."""

    model_config = ConfigDict(extra="ignore")

    game_ids: Optional[List[str]] = Field(
        default=None,
        max_length=10,
        description="List of canonical game IDs or Steam App IDs to find similar games for",
    )
    seed_game_ids: Optional[List[str]] = Field(
        default=None,
        max_length=10,
        description="Alias for game_ids",
    )
    limit: int = Field(
        default=12,
        ge=1,
        le=50,
        description="Maximum number of recommended games to return",
    )
    filters: Optional[DiscoveryFilters] = None

    def get_ids(self) -> List[str]:
        return self.game_ids or self.seed_game_ids or []


class CompareGamesRequest(BaseModel):
    """Request payload for comparing 2-3 games side-by-side."""

    model_config = ConfigDict(extra="forbid")

    game_ids: List[str] = Field(
        ...,
        min_length=2,
        max_length=3,
        description="2 to 3 game IDs to compare side-by-side",
    )


class CompareGamesResponse(BaseModel):
    """Response payload with normalized game items for comparison."""

    model_config = ConfigDict(extra="forbid")

    games: List["GameDiscoveryItem"] = Field(default_factory=list)
    common_genres: List[str] = Field(default_factory=list)
    common_tags: List[str] = Field(default_factory=list)
    common_modes: List[str] = Field(default_factory=list)
    differentiating_tags: List[str] = Field(default_factory=list)



class GameEnrichment(BaseModel):
    """Optional IGDB enrichment metadata for a game."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field(
        default="UNAVAILABLE",
        description="Status of IGDB enrichment: AVAILABLE, UNAVAILABLE, NOT_FOUND, STALE",
    )
    cover_url: Optional[str] = None
    screenshot_urls: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    developer: Optional[str] = None
    publisher: Optional[str] = None
    themes: List[str] = Field(default_factory=list)
    franchise: Optional[str] = None
    igdb_id: Optional[int] = None
    igdb_url: Optional[str] = None


class GameDiscoveryItem(BaseModel):
    """Normalized game metadata in search results with three-layer metadata separation."""

    model_config = ConfigDict(extra="ignore")

    id: str
    external_id: str
    source: str = "steam"
    title: str
    display_title: Optional[str] = None
    description: str
    display_description: Optional[str] = None
    original_description: Optional[str] = None
    description_language: str = "en"
    description_source: str = "steam"  # "steam" | "normalized" | "igdb" | "original"
    genres: List[str] = Field(default_factory=list)
    display_genres: List[str] = Field(default_factory=list)
    original_genres: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    display_tags: List[str] = Field(default_factory=list)
    original_tags: List[str] = Field(default_factory=list)
    player_modes: List[str] = Field(default_factory=list)
    platforms: List[str] = Field(default_factory=list)
    release_year: int = 0
    is_free: bool = False
    total_reviews: Optional[int] = 0
    positive_percent: Optional[float] = 0.0
    review_score_desc: Optional[str] = ""
    enrichment: Optional[GameEnrichment] = None

    # Visual Experience V1 fields
    cover_image_url: Optional[str] = None
    hero_image_url: Optional[str] = None
    screenshots: List[str] = Field(default_factory=list)
    storefronts: List[StorefrontItem] = Field(default_factory=list)
    developer: Optional[str] = None
    publisher: Optional[str] = None


class DiscoverySearchResult(BaseModel):
    """Single ranked search match item with explanation and highlights."""

    model_config = ConfigDict(extra="forbid")

    game: GameDiscoveryItem
    score: float = Field(..., ge=0.0, le=1.0, description="Calibrated relevance score (0.0 - 1.0)")
    match_highlights: List[str] = Field(default_factory=list, description="Specific matched tags, modes, and genres")
    explanation: str = Field(..., description="Deterministic explanation of why this game matches")
    is_hidden_gem: bool = Field(default=False, description="Whether this title satisfies the hidden gem criteria")
    trade_offs: List[str] = Field(default_factory=list, description="Explicit grounded trade-offs, e.g. 'More combat than requested'")
    personalization_reasons: List[str] = Field(default_factory=list, description="Explicit reasons grounded in user profile, e.g. 'Because you like RPG'")


class DiscoverySearchResponse(BaseModel):
    """Response envelope for POST /api/discovery/search and recommendations."""

    model_config = ConfigDict(extra="forbid")

    query: str
    match_count: int
    no_strong_match: bool
    query_type: Optional[str] = "CONCEPT"
    target_entity: Optional[str] = None
    mode: str = "BEST_MATCH"
    why_these: Optional[str] = None
    personalized: bool = False
    personalization_evidence: List[str] = Field(default_factory=list)
    results: List[DiscoverySearchResult]



class BuildInspirationResponse(BaseModel):
    """Structured design metadata extracted from a canonical game for the /build pipeline."""

    model_config = ConfigDict(extra="forbid")

    source_game_id: str
    title: str
    inferred_archetype: str = Field(..., description="2D Prototype Archetype: survival, shooter, platformer, collector")
    inferred_theme: str
    recommended_prompt: str
    suggested_art_density: int = Field(default=50, ge=0, le=100)
    suggested_physics: int = Field(default=50, ge=0, le=100)
    suggested_modules: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    genres: List[str] = Field(default_factory=list)
    player_modes: List[str] = Field(default_factory=list)
