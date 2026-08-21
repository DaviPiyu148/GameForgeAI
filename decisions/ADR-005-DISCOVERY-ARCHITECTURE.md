# ADR-005 — Discovery Architecture

**Status:** Accepted

## Decision
Use normalized catalog data + Sentence Transformers embeddings + FAISS retrieval + hard filters + ranking. Optional LLM reranking/explanations operate only on a small top-K candidate set.

## Consequences
Index generation is an offline/preprocessing concern. Search remains server-side.

## Deferred
Large distributed vector databases and advanced collaborative filtering.
