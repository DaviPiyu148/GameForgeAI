# 10 — Discovery Engine & Discovery Experience V2

## System Freeze

```text
DISCOVERY V1
= FROZEN

PERSONALIZATION V1
= FROZEN AT 25% EXPERIMENTAL EXPOSURE

NO FURTHER RANKING TUNING
UNLESS REAL ORGANIC DATA JUSTIFIES IT
```

This document describes the established Discovery architecture. Current production/test state belongs in [`docs/status/current-status.md`](../status/current-status.md).

## Discovery Experience V2

Implemented capabilities include:

- Game DNA onboarding
- Safe preferences reset
- Multi-game comparison
- Session-scoped discovery tuning
- Quick mood discovery
- Similar games
- More-like-this recommendations
- Build-inspiration extraction

## Metadata Architecture

### ORIGINAL

Preserves source provenance:

- `original_title`
- `original_description`
- `original_genres`
- `original_tags`
- `original_categories`

### SEARCH

Optimizes retrieval:

- `canonical_genres`
- `search_tags`
- `search_description`
- `semantic_profile`
- Normalized multilingual tokens

### DISPLAY

Optimizes user presentation:

- `display_title`
- `display_description`
- `display_genres`
- `display_tags`
- `description_language`
- `description_source`

Search/display normalization must not destroy original provenance.

## Display Description Policy

Prefer, in order:

1. Native English source
2. Offline normalized English synopsis
3. Verified IGDB English summary
4. Explicitly labeled original-language fallback

Normalization happens offline during catalog processing.

No runtime translation call is required for ordinary discovery search.

## Hybrid Retrieval

```text
User Query
   ↓
Deterministic query classification
   ↓
Semantic retrieval ─────┐
                        ├──► Reciprocal Rank Fusion
Lexical retrieval ─────┘
   ↓
Hard constraints
   ↓
Calibrated score bands
   ↓
Grounded evidence / explanation
   ↓
Optional non-blocking IGDB enrichment
   ↓
Structured response
```

Current documented intent classes include:

- `ENTITY`
- `SIMILARITY`
- `TOPIC_TAG`
- `CONCEPT`
- `MIXED`

## Candidate Pools

The current documented system distinguishes:

- Full normalized catalog: approximately 121k titles
- Popular vector pool: exactly 20,000 vectors
- Reviewed-only vector pool: 87,890 vectors representing titles with at least one total review

Candidate-pool definitions are configuration/state and should be verified against the actual index artifacts before changing them.

## Ranking and Constraints

Hard constraints and explicit avoidances are authoritative.

Personalization may influence ranking only within those constraints.

Do not let a similarity score, personalization score, or LLM explanation reintroduce excluded candidates.

## Personalization

Current documented operating point:

- Treatment exposure: 25%
- `POPULAR`: 0.00
- `BEST_MATCH`: 0.02
- `DISCOVER`: 0.05
- `HIDDEN_GEMS`: 0.05
- Global/project context weighting: 30% / 70%

These values are frozen operating-policy data.

Do not retune them without organic evidence and an explicit evaluation process.

## Performance

Core synchronous retrieval work must not block the FastAPI event loop.

Where synchronous libraries are used, explicit worker offloading may be used.

Any performance refactor must prove ranking equivalence on the relevant regression set.

## Enrichment

IGDB enrichment is non-blocking where applicable and uses persistent/memory caching.

A discovery search should remain usable if enrichment is unavailable.

## Quality Evidence

The documented 98-query benchmark established strong improvement over the pure semantic baseline.

Those metrics are benchmark evidence, not a guarantee of production user satisfaction.

Future ranking changes should use:

- Offline benchmark results
- Constraint-preservation tests
- Latency measurements
- Organic behavioral metrics once available

Do not treat benchmark gains as permission for endless tuning.

## Freeze Rule

The Discovery and Personalization systems are finished enough for the current product.

Engineering work should move to adjacent product/reliability concerns unless new evidence directly shows a Discovery/Personalization defect.
