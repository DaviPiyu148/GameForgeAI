# Discovery Intelligence V1 — Technical Specification & Verification Report

## Executive Summary
Discovery Intelligence V1 evolves GameForge AI's existing hybrid retrieval engine (FAISS dense vector index + 121,625-game lexical catalog + IGDB enrichment) into a multi-signal, intent-driven, diverse, and interactive recommendation system.

The system remains:
- **100% Deterministic & Local**: Zero Gemini or hosted LLM API calls for discovery.
- **Cost-Free & Zero External Infra**: No Redis, Celery, Kafka, vector databases, or GPU requirements.
- **Explainable & Grounded**: Why-matches explanations and trade-offs are grounded exclusively in catalog metadata or verified user profile DNA.
- **Fast & Scalable**: O(1) FAISS vector retrieval using a mapped internal dictionary, sub-second latency.
- **Preserved Architecture**: RRF fusion, deterministic filters, and display normalization remain intact.

---

## 1. Core Architectural Pillars

### A. Centralized Ranking Configuration (`ranking_config.py`)
All retrieval bounds, component weights, mode multipliers, diversity penalties, and calibration thresholds reside in a single canonical configuration module:
- `TOP_K_DENSE = 50`, `TOP_K_LEXICAL = 50`, `RRF_K = 60.0`
- `DIRECT_SCORE_WEIGHT = 0.60`, `RRF_SCORE_WEIGHT = 0.40`
- `PERSONALIZATION_GENRE_WEIGHT = 0.12`, `PERSONALIZATION_VECTOR_WEIGHT = 0.10` (max boost 0.20)
- `SOFT_NEGATIVE_TAG_PENALTY = 0.18`, `SOFT_NEGATIVE_GENRE_PENALTY = 0.15` (max penalty 0.35)
- `SAME_FRANCHISE_PENALTY = 0.15` (soft penalty applied to 3rd+ candidate of same family, unless explicit query)
- `HIDDEN_GEM_MIN_POSITIVE_PCT = 80.0%`, `HIDDEN_GEM_MIN_REVIEWS = 50`, `HIDDEN_GEM_MAX_REVIEWS = 15000`

### B. O(1) FAISS Vector Lookup (`index.py`)
FAISS `IndexFlatIP` does not maintain a native ID dictionary. On startup, `FAISSIndexManager` indexes Steam App IDs into `self._id_to_pos: Dict[str, int]`. Calling `get_vector(game_id)` or `get_vectors(game_ids)` performs instant reconstruction via `index.reconstruct(pos)` in <1ms without any list scanning.

### C. Rich Intent Understanding (`query_parser.py`)
The query parser deterministically identifies:
- **Query Type**: `ENTITY`, `SIMILARITY`, `TOPIC_TAG`, `MIXED`, `CONCEPT`
- **Hard Constraints**: `is_free`, `avoid_genres`, `avoid_tags`, `avoid_modes` (triggered by "no", "without", "never", "exclude")
- **Soft Preferences**: Moods (`relaxing`, `intense`, `dark`, `scary`, `atmospheric`), session duration (`short` for 15-45 mins, `medium`, `long`), combat preferences (`low` vs `high`), difficulty preferences
- **Positive Semantic Cleanup**: Strips negative clauses so sentence transformer embedding represents the true positive intent.

### D. Multi-Signal Hybrid Ranker (`ranker.py`)
Modular scoring formula:
$$\text{Score} = (\text{CoreRelevance} \times \text{ModeRelevanceMult}) + \text{Quality} + \text{Novelty} + \text{Personalization} - \text{NegativePenalty}$$

- **Core Relevance**: Blends normalized RRF ($k=60$) with query-type dynamic weights ($w_{sem}, w_{lex}, w_{pop}$).
- **Quality & Acclaim**: Log-scaled review count $\times$ positive percentage.
- **Novelty & Hidden Gems**: Boosts games with $\ge 80\%$ positive acclaim and $50 - 15,000$ reviews.
- **Personalization**: Grounded additive bonus based on authenticated user's Game DNA top genres and cosine similarity with saved game embeddings. Zero penalty on cold-start users.
- **Soft Franchise Diversity**: Maximum 2 games per franchise family by default; 3rd+ receives soft score penalty. Queries that explicitly name a franchise are exempt.
- **Grounded Explanations**: Generates deterministic "Why This Matches" evidence, honest trade-offs (e.g. "Contains moderate action/combat"), and personalization reasons ("Matches your affinity for RPG").

### E. Interactive Discovery Modes
1. **BEST_MATCH**: Maximum relevance and intent match (relevance mult: 1.0).
2. **DISCOVER**: Broader diversity, higher exploration, and novelty (diversity mult: 1.5, novelty mult: 1.2).
3. **HIDDEN_GEMS**: Prioritizes acclaimed games with fewer reviews (novelty mult: 2.2, quality mult: 1.4).
4. **POPULAR**: Focuses on community favorites and high review volume (quality mult: 2.0).

### F. Interactive Feedback & Anti-Spam Progression
- Endpoint: `POST /api/discovery/feedback` (`game_id`, `feedback: 'like' | 'dislike' | 'less_like_this'`)
- `Like` grants rate-limited progression XP via `ProgressionService` deduplication.
- `Dislike` and `Less Like This` update behavioral preferences and session exclusions without granting XP, preventing progression exploits.

---

## 2. Benchmark Evaluation Results
Evaluated on `backend/tests/data/discovery_benchmark.json` (30 curated queries across 8 categories):

| Benchmark Metric | Result | Target / Standard |
|---|---|---|
| **Total Benchmark Queries** | 30 | 30 |
| **Intent Classification Accuracy** | **90.0%** (27/30) | $\ge 85\%$ |
| **Hard Constraint Violations** | **0** | Zero tolerance |
| **Mean Precision@5** | **0.907** | $\ge 0.85$ |
| **Mean Search Latency** | **367.4 ms** (full hybrid cold-warm) | Sub-second |
| **Core In-Memory Search Latency** | **< 25 ms** | Sub-50ms |

---

## 3. Automated Test Verification
- **Full Discovery Suite**: 36/36 passed in 65s (`test_discovery_2.py`, `test_discovery_ranker.py`, `test_preference_service.py`, `test_saved_discoveries.py`, `test_multilingual_search.py`).
- **Frontend Production Build**: `tsc -b && vite build` passed with 0 errors in 1.48s.
- **Alembic**: Unchanged single head `bc9ae398f146`.
