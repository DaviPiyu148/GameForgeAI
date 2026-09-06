# 03 — Technology Stack

## Purpose

This document records the established technology baseline. Changing a core technology requires a concrete requirement and appropriate architecture review.

## Frontend

- React 19
- TypeScript
- Vite
- Tailwind CSS v4
- `react-router-dom`
- HashRouter
- React Context
- Phaser 3.88.2 embedded for playable prototypes

## Backend

- Python 3.12
- FastAPI
- Pydantic v2
- SQLAlchemy 2.0
- SQLite
- Alembic

The backend is structured as a modular monolith.

## Authentication & Security

- PyJWT
- HS256 JWT access tokens
- `pwdlib[argon2]` / Argon2 password hashing
- `email-validator`
- In-memory sliding-window rate limiting in the current single-worker topology
- Server-derived authenticated `user_id`
- Token-version-based credential/session revocation

## AI

- Hosted LLM provider architecture
- Google Gemini as the current primary provider path
- Groq fallback path for provider-availability resilience where configured
- Internal provider/router abstraction
- Structured JSON generation
- Pydantic validation
- Bounded repair/retry behavior
- Provider-specific logic isolated behind the AI boundary

There is no local LLM dependency or local-model fallback.

## Discovery

- Sentence Transformers
- `all-MiniLM-L6-v2`
- FAISS `IndexFlatIP`
- Normalized Steam-derived catalog
- Lexical/inverted retrieval
- Deterministic scoring/fusion
- Optional IGDB enrichment through caching

## Runtime

- Phaser 3.88.2
- Arcade Physics
- Procedural vector textures
- Deterministic Mulberry32 PRNG
- Allowlisted rule interpreter
- No arbitrary generated JavaScript execution

## Transport

- REST for ordinary API operations
- SSE for build events/log streaming

## Infrastructure Deliberately Deferred

The following require a concrete requirement plus an approved architecture decision:

- PostgreSQL
- Redis
- Celery
- Kafka
- GraphQL
- Kubernetes
- Microservices
- Service mesh
- Distributed vector infrastructure
- Local LLM inference

## Dependency Rule

Every dependency should solve a concrete problem, reduce meaningful complexity, or materially improve reliability/product behavior.

Do not add dependencies for trivial functionality that existing platform/library capabilities already provide.
