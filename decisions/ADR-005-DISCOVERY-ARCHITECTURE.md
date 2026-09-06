# ADR-005 — Discovery Architecture

**Status:** Accepted

## Context

GameForge AI must retrieve relevant games from a large catalog using natural-language descriptions while preserving hard constraints, predictable behavior, and reasonable latency.

Pure lexical search misses semantic similarity.

Pure semantic retrieval can violate explicit constraints or surface poor candidates.

An LLM should not be placed in the critical path as a substitute for a proper retrieval system.

## Decision

Use:

```text
Normalized catalog
      ↓
Semantic embeddings / Sentence Transformers
      ↓
FAISS retrieval
      +
Lexical retrieval
      ↓
Hard filters / constraints
      ↓
Fusion + ranking
      ↓
Final ranked results
```

Search remains server-side.

Index generation is an offline/preprocessing concern.

## Retrieval and Ranking Invariants

Hard constraints and explicit avoidances are authoritative.

Ranking improvements must not override explicit exclusions.

Candidate generation and ranking must remain deterministic enough to support regression testing and offline benchmarking.

The current Discovery V1 retrieval/ranking configuration is a product-level operating point. Its exact candidate pools, thresholds, weights, and exposure policies belong in current status/configuration documentation rather than becoming permanently embedded in this architectural ADR.

Do not retune frozen Discovery behavior during unrelated engineering work.

## Optional LLM Usage

LLM-assisted reranking or explanations may be used only where explicitly approved and only over a small top-K candidate set.

The core retrieval system must not depend on an LLM being available unless a later architecture decision intentionally changes that requirement.

LLM output must never bypass hard filters.

## Personalization Boundary

Personalization is a separate ranking layer from core retrieval.

Personalization must:

- Respect hard constraints and explicit avoidances.
- Preserve cold-start neutrality.
- Remain within its latency budget.
- Avoid unnecessary LLM calls.
- Be independently measurable and reversible.

Changes to Discovery ranking and Personalization should not be mixed casually because they affect distinct risk domains.

## Performance

Synchronous CPU-heavy retrieval work must not unnecessarily block the async application event loop.

Where the underlying libraries are synchronous, use an explicit worker/thread boundary and verify ranking equivalence.

## Quality Guardrails

Discovery changes should be validated against:

- Candidate IDs
- Semantic similarity scores
- Lexical result sets
- Fusion scores
- Final ranking order
- Constraint preservation
- Latency
- Error/fallback behavior

For frozen behavior, regression benchmarks should prove that an unrelated performance/reliability change did not alter ranking.

## Rejected / Deferred

- Large distributed vector databases without demonstrated need
- Advanced collaborative filtering without sufficient behavioral data
- Replacing retrieval with unrestricted LLM generation
- Applying LLM output after hard constraints in a way that can reintroduce excluded candidates

## Consequences

### Positive

- Strong semantic retrieval.
- Clear constraint enforcement.
- Efficient local/server-side index lookup.
- Testable ranking pipeline.
- Optional bounded AI augmentation without making the entire system LLM-dependent.

### Negative

- Index freshness requires an explicit preprocessing/update process.
- Ranking complexity requires careful regression tests.
- FAISS remains subject to memory/runtime constraints.
