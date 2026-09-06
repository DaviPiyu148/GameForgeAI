# ADR-002 — Backend Stack and Service Architecture

**Status:** Accepted

## Context

GameForge AI requires APIs, authentication, persistence, discovery retrieval, asynchronous build jobs, streaming build events, AI-provider integration, and project/version lifecycle management.

The system needs a low-operational-overhead architecture that remains easy to run locally and can evolve without prematurely adopting distributed infrastructure.

## Decision

Use a **Python modular monolith** built with:

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- SQLite
- Alembic

Organize the backend by clear responsibilities and domain/service boundaries rather than by prematurely distributed services.

## Architectural Principles

### Modular monolith first

Keep related capabilities inside one deployable application while maintaining clear module boundaries.

Extract a service only when there is a concrete operational, scaling, ownership, or isolation requirement that justifies the additional complexity.

### FastAPI

FastAPI owns:

- HTTP routing
- Request/response handling
- Dependency injection
- Authentication/authorization integration
- Async request lifecycle

Blocking CPU- or I/O-heavy work must not unnecessarily block the async event loop. Synchronous workloads that are safe to offload should use an explicit worker/thread boundary or an appropriate asynchronous implementation.

### Pydantic

Pydantic is the boundary-validation mechanism for:

- API requests/responses where applicable
- Configuration
- Structured AI output
- Game DSL schemas
- Important domain contracts

Validation must not be treated as an alternative to authorization.

### SQLAlchemy

SQLAlchemy owns database interaction.

Database invariants that matter to correctness should be represented through database constraints where appropriate, not only application checks.

### SQLite

SQLite is the current persistence engine.

SQLite-specific behavior, including DDL/migration limitations, locking, concurrency, and connection handling, must be considered explicitly.

A future move to PostgreSQL is not an automatic "production upgrade"; it requires a concrete requirement and an explicit architecture decision.

### Alembic

All schema changes must use explicit migrations.

Migrations must account for existing data, upgrade/downgrade behavior where supported, compatibility, and recovery implications.

## Async and Background Work

Asynchronous build processing remains backend-owned.

The application may use FastAPI-compatible background/worker mechanisms appropriate to the current deployment topology.

Do not introduce Celery, Redis, Kafka, or similar infrastructure merely to make the architecture look more scalable.

If horizontal worker scaling becomes necessary, the cross-worker state/event implications must be addressed explicitly.

## Error and Failure Boundaries

The backend must:

- Return safe, consistent API errors.
- Preserve intended HTTP/domain errors.
- Avoid leaking stack traces or internal infrastructure details.
- Use bounded timeouts/retries for external calls.
- Preserve data integrity under concurrent requests.

## Observability

Production backend changes should consider:

- Structured logs
- Request/job correlation IDs
- Health/readiness checks
- Metrics
- Error tracking
- Important job/database/dependency failure signals

## Consequences

### Positive

- Low infrastructure overhead.
- Fast iteration.
- Strong Python AI/data ecosystem.
- Clear validation boundaries.
- Simple local deployment.
- Easier reasoning about transactions and application state.

### Negative

- A modular monolith requires discipline to prevent coupling.
- SQLite has concurrency/scaling limitations.
- In-process background/event mechanisms constrain horizontal scaling.

## Deferred

The following require explicit justification and a new architecture decision:

- PostgreSQL
- Redis
- Celery
- Kafka
- Microservices
- Kubernetes
- Service meshes
- Other major orchestration/distributed infrastructure

## Non-Goals

Do not introduce distributed infrastructure to solve a hypothetical future problem.

Do not convert synchronous work into asynchronous code merely for style; identify actual blocking behavior and choose the smallest correct execution boundary.
