# 06 — Backend Architecture

## Architectural Style

The backend is a modular monolith.

```text
backend/
  app/
    main.py
    config.py
    dependencies.py
    api/
    schemas/
    models/
    repositories/
    services/
    ai/
    generation/
    search/
    runtime/
    db/
  alembic/
  data/
  scripts/
  tests/
```

## Responsibilities

### API Layer

FastAPI route handlers should remain thin.

They should:

- Parse/validate inputs
- Resolve dependencies
- Enforce authentication dependencies
- Call domain/application services
- Translate expected exceptions into API responses

Business logic should not accumulate inside route handlers.

### Schemas

Pydantic models define boundary contracts.

Keep API schemas separate from SQLAlchemy models and Game DSL schemas.

### Models

SQLAlchemy models represent persistent data.

Database constraints should enforce important invariants where appropriate.

### Repositories

Repositories provide explicit data-access boundaries where they improve isolation and testability.

### Services

Core services include:

- `ProjectService`
- `BuildService`
- `GameGenerationService`
- `DiscoveryService`
- `AuthService`
- `AvatarService`
- `PreferenceService`
- `ProgressionService`

Services own business workflows; repositories own persistence mechanics.

### AI

The AI layer owns:

- Provider abstraction/router
- Prompt construction
- Provider configuration
- Provider error normalization
- Bounded retry/failover behavior
- Structured-output handling

Vendor-specific SDK/API details must not leak into domain services.

### Generation

The generation layer owns:

- GameDesignSpec
- GameDSL
- Validation
- Quality evaluation
- Reachability
- Procedural generation
- Normalization/repair
- Runtime capability compatibility

### Search

The search layer owns:

- Normalized catalog
- Semantic retrieval
- Lexical retrieval
- Ranking/fusion
- Constraint preservation
- Enrichment/cache integration

## Database Entities

Current entities include:

- `users`
- `projects`
- `project_versions`
- `build_jobs`
- `build_logs`
- `playtest_sessions`
- `saved_discoveries`
- `user_progress`
- `xp_events`
- `user_milestones`
- `user_genre_preferences`

See [`docs/architecture/data-model.md`](data-model.md) for authoritative schema semantics.

## Database/Migration Discipline

Schema changes use Alembic.

Migrations must:

- Preserve existing data unless deletion is explicitly intended
- Validate preconditions
- Be safe for existing rows
- Consider SQLite DDL constraints
- Verify schema after upgrade
- Verify data identities/relationships where historical preservation matters
- Test downgrade/re-upgrade when the project supports downgrade verification

Never silently delete orphaned or historical data to make a migration pass.

## Async Work

Build jobs are backend-owned.

Synchronous CPU-heavy work must not unnecessarily block the FastAPI event loop.

The current in-process build-event broadcaster and rate limiter are process-local.

Therefore the current deployment topology is single-worker.

## Error Handling

Unexpected exceptions must not leak internal details.

Expected domain/HTTP errors remain intact.

Database/infrastructure failures must not be silently downgraded into successful or anonymous business behavior.

## Observability

Important service operations should expose safe structured logs and useful correlation/job identifiers.

Production hardening must eventually add appropriate metrics, tracing, and alerts.

## Migration Chain

The repository currently documents a single Alembic head. The exact migration IDs belong to the current migration tree and should be verified with:

```bash
alembic heads
alembic history
```

Do not hard-code migration truth in a document after the repository changes without refreshing the document.
