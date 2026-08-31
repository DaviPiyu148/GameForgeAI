# 10 — Discovery Engine & Discovery Experience V2

## Implementation Status (IMPLEMENTED — Discovery Experience V2)
The Discovery Engine features hybrid semantic + lexical retrieval, deterministic rich intent parsing (moods, session lengths, combat/difficulty preferences, hard/soft negations), centralized ranking configuration (`ranking_config.py`), O(1) FAISS vector retrieval, multi-signal ranking with bounded Game DNA personalization, soft franchise diversity reranking, interactive discovery modes (`BEST_MATCH`, `DISCOVER`, `HIDDEN_GEMS`, `POPULAR`), interactive feedback API (`POST /api/discovery/feedback`), grounded explanations, honest trade-offs, and clean English display normalization.

Discovery Experience V2 elevates this with cold-start Game DNA onboarding (`POST /api/profile/preferences/onboard`), safe preferences reset (`POST /api/profile/preferences/reset`), multi-game side-by-side comparison (`POST /api/discovery/compare`), session-scoped tuning panel without database pollution, and interactive quick mood discovery.



## User-Facing English Display Normalization (Discovery 2.2)
- **Three-Layer Decoupling**:
  1. *ORIGINAL Layer*: `original_title`, `original_description`, `original_genres`, `original_tags`, `original_categories` preserve 100% immutable Steam source provenance.
  2. *SEARCH Layer*: `canonical_genres`, `search_tags`, `search_description`, `semantic_profile` provide multilingual token inverted indexes and 384-dimensional dense vectors.
  3. *DISPLAY Layer*: `display_title`, `display_description`, `display_genres`, `display_tags`, `description_language`, `description_source` guarantee clean human-readable UI presentation.
- **Display Description Hierarchy**:
  1. *Native English Source (`description_source="steam"`, `description_language="en"`)*: Used directly when Steam metadata is English.
  2. *Normalized English Synopsis (`description_source="normalized"`, `description_language="en"`)*: Structured, informative synopsis constructed offline from canonical metadata for non-English source games (*Stardew Valley*, *Terraria*, *Hollow Knight*, *ELDEN RING*, *The Witcher 3*).
  3. *Enriched IGDB Summary (`description_source="igdb"`, `description_language="en"`)*: When a verified IGDB mapping exists, the official English summary elevates the card synopsis.
  4. *Labeled Localized Fallback (`description_source="original"`, `description_language="ru"|"zh"|...`)*: If a game has no English metadata, the original text is displayed with a subtle localized language badge (`[RU]`, `[ZH]`).
- **Zero Runtime Translation Overhead**: All text normalization runs offline during catalog ingestion; no external translation API or LLM calls are invoked during search.

## Hybrid Retrieval Pipeline
```text
User Search Prompt (POST /api/discovery/search)
         ↓
Deterministic Multilingual Query Parser (ENTITY, SIMILARITY, TOPIC_TAG, CONCEPT, MIXED)
     ┌────┴───────────────────────────────┐
     ↓                                    ↓
Dense Semantic Vector Retrieval       Full Inverted Lexical Index
(FAISS IndexFlatIP, 20k games)        (121,625 games, multi-token tags & genres)
     └────┬───────────────────────────────┘
          ↓
Reciprocal Rank Fusion (RRF k=60) with Dynamic Intent Weights
          ↓
Deterministic Hard Constraints Filtering (platforms, modes, genres, tags, year, price)
          ↓
S-Curve Calibrated Score Bands (Strong >=85%, Good 70-84%, Possible 50-69%)
          ↓
Deterministic Evidence Highlights & Grounded Explanation Generation
          ↓
Non-Blocking Multi-Tier IGDB Enrichment (SQLite persistent cache + memory cache)
          ↓
Structured Three-Layer Response Envelope (query_type, target_entity, results)
```

## Recommendation Modes & Endpoints
1. **Search (`POST /api/discovery/search`)**: Hybrid retrieval with calibrated score bands, multilingual support, and clean English display normalization.
2. **Similar To Game (`GET /api/discovery/similar/{steam_app_id}`)**: Semantic profile nearest neighbors excluding seed game.
3. **More Like This (`POST /api/discovery/more-like-this`)**: Multi-seed blend aggregating semantic DNA.
4. **Build Inspiration (`GET /api/discovery/build-inspiration/{steam_app_id}`)**: Extracts 2D prototype archetype, thematic presets, starter prompt, and recommended compiler parameters.

## Benchmark Evaluation Results (98 Comprehensive Benchmark Queries)
| Metric | Pure Semantic Baseline | Discovery 2.2 Hybrid | Improvement |
| :--- | :--- | :--- | :--- |
| **Precision@5** | `0.0980` | **`0.2286`** | **+133.3%** |
| **Recall@10** | `0.2641` | **`0.5141`** | **+94.7%** |
| **MRR** | `0.2641` | **`0.5007`** | **+89.6%** |
| **NDCG@10** | `0.2680` | **`0.5758`** | **+114.9%** |
| **Average Latency** | `27.58 ms` | **`16.95 ms` (core search)** | **High throughput** |

### Landmark Queries
- `cyberpunk 2077`: **`Cyberpunk 2077` #1 (98% match)**
- `stardew valley`: **`Stardew Valley` #1 (98% match, clean English description)**
- `stardew`: **`Stardew Valley` #1 (98% match)**
- `games like Stardew Valley`: **`Stardew Valley` #1, `Wildermyth` #2**
- `soulslike`: **`ELDEN RING` #1, `DARK SOULS™ III` #2**
- `co-op roguelike`: **`Sven Co-op` #1, `Streets of Rogue` #2**
- `уютный симулятор фермы` (Russian): **`Farming Simulator 22` #1, `Farming Simulator 2011` #2, `Garden Life` #3**
- `cozy ферма game` (Mixed): **`Farming Simulator 22` #1, `Garden Life` #2**

## Catalog & Inverted Index Specs
- **Full Catalog**: 121,625 games loaded in memory with three-layer metadata, inverted token dictionaries, multilingual genre translations, compound/hyphen tag normalization, and fast candidate pruning.
- **Dense Vector Index**: 20,000 top games indexed with FAISS `IndexFlatIP` (384 dimensions).
- **IGDB Caching**: SQLite (`backend/data/processed/igdb_cache.sqlite3`) with 7-day TTL and 1.5s timeout; zero disruption if unconfigured or offline.
