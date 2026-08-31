"""
Centralized Discovery Intelligence V1 Ranking Configuration.

All retrieval bounds, component weights, mode adjustments, diversity thresholds,
and scoring parameters reside in this module. No magic numbers scattered across
ranker.py, discovery_service.py, or query_parser.py.
"""
from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class QueryTypeWeights:
    w_sem: float
    w_lex: float
    w_pop: float


# Base component weights per deterministic query understanding classification
QUERY_TYPE_WEIGHTS: Dict[str, QueryTypeWeights] = {
    "ENTITY": QueryTypeWeights(w_sem=0.20, w_lex=0.65, w_pop=0.15),
    "SIMILARITY": QueryTypeWeights(w_sem=0.55, w_lex=0.30, w_pop=0.15),
    "TOPIC_TAG": QueryTypeWeights(w_sem=0.35, w_lex=0.45, w_pop=0.20),
    "MIXED": QueryTypeWeights(w_sem=0.40, w_lex=0.45, w_pop=0.15),
    "CONCEPT": QueryTypeWeights(w_sem=0.55, w_lex=0.35, w_pop=0.10),
}

# Candidate pool retrieval bounds (preserve sub-25ms response time on consumer hardware)
DEFAULT_TOP_K_DENSE: int = 50
DEFAULT_TOP_K_LEXICAL: int = 50
RRF_K: float = 60.0

# Base direct vs RRF score blend
DIRECT_SCORE_WEIGHT: float = 0.60
RRF_SCORE_WEIGHT: float = 0.40

# Personalization weights (bounded contribution; additive, never mandatory)
PERSONALIZATION_GENRE_WEIGHT: float = 0.12
PERSONALIZATION_VECTOR_WEIGHT: float = 0.10
MAX_PERSONALIZATION_BOOST: float = 0.20

# Negative preference penalties (bounded so single dislikes don't destroy entire categories)
SOFT_NEGATIVE_TAG_PENALTY: float = 0.18
SOFT_NEGATIVE_GENRE_PENALTY: float = 0.15
NEGATIVE_VECTOR_PENALTY: float = 0.12
MAX_TOTAL_NEGATIVE_PENALTY: float = 0.35

# Quality & Acclaim signals
QUALITY_WEIGHT: float = 0.08
MAX_STEAM_REVIEWS_LOG: float = 5.0  # Log-scale capped at 100,000 reviews

# Novelty / Hidden Gem configuration
NOVELTY_WEIGHT: float = 0.08
HIDDEN_GEM_MIN_POSITIVE_PCT: float = 80.0
HIDDEN_GEM_MIN_REVIEWS: int = 50
HIDDEN_GEM_MAX_REVIEWS: int = 15000

# Diversity reranking (MMR style; soft franchise limitation)
DIVERSITY_LAMBDA: float = 0.20
MAX_SAME_FRANCHISE: int = 2
SAME_FRANCHISE_PENALTY: float = 0.15  # Soft penalty applied to 3rd+ candidate of same family

# Calibrated relevance score thresholds
MIN_MATCH_SCORE_THRESHOLD: float = 0.30
STRONG_MATCH_THRESHOLD: float = 0.70


@dataclass(frozen=True)
class ModeRankingAdjustment:
    """Multipliers applied to ranking terms depending on user-selected Discovery Mode."""
    relevance_mult: float
    personalization_mult: float
    diversity_mult: float
    novelty_mult: float
    quality_mult: float
    description: str


# Supported deterministic Discovery Modes (POPULAR used instead of TRENDING to honor factual metadata)
DISCOVERY_MODES: Dict[str, ModeRankingAdjustment] = {
    "BEST_MATCH": ModeRankingAdjustment(
        relevance_mult=1.0,
        personalization_mult=1.0,
        diversity_mult=0.5,
        novelty_mult=0.5,
        quality_mult=0.8,
        description="Maximum relevance and intent match.",
    ),
    "DISCOVER": ModeRankingAdjustment(
        relevance_mult=0.85,
        personalization_mult=0.8,
        diversity_mult=1.5,
        novelty_mult=1.2,
        quality_mult=0.8,
        description="Balanced relevance with broader diversity and surprising picks.",
    ),
    "HIDDEN_GEMS": ModeRankingAdjustment(
        relevance_mult=0.80,
        personalization_mult=0.7,
        diversity_mult=1.0,
        novelty_mult=2.2,
        quality_mult=1.4,
        description="High acclaim games with lower mainstream review counts.",
    ),
    "POPULAR": ModeRankingAdjustment(
        relevance_mult=0.85,
        personalization_mult=0.8,
        diversity_mult=0.8,
        novelty_mult=0.2,
        quality_mult=2.0,
        description="Emphasizes critically acclaimed, widely played community favorites.",
    ),
}

DEFAULT_MODE: str = "BEST_MATCH"
