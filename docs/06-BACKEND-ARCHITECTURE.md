# 06 — Backend Architecture

## Directory Structure
```text
backend/
  app/
    main.py
    config.py
    dependencies.py
    api/              # Thin FastAPI route handlers
    schemas/          # Pydantic v2 validation models (DesignSpec, GameDSL, Playtest, Improvements)
    models/           # SQLAlchemy 2.0 ORM models (User, Project, ProjectVersion, PlaytestSession, BuildJob, BuildLog)
    repositories/     # Data access boundaries
    services/         # Business logic (ProjectService, BuildService, GameGenerationService, DiscoveryService, AuthService)
    ai/               # AI prompts & provider router (Gemini 3 Flash Preview: gemini-3-flash-preview)
    generation/       # GameDSL, GameDesignSpec, GameplayQualityValidator, PRNG & Procedural logic
    search/           # Hybrid semantic (FAISS) + lexical (BM25) discovery with IGDB enrichment
    runtime/          # Capability matrix & compatibility validator
    db/               # SessionLocal & SQLite DB engine
  alembic/            # Database schema migrations
  data/               # Normalized Steam catalog, IGDB mapping & FAISS index
  scripts/            # Maintenance & index-building scripts
  tests/              # Comprehensive pytest regression suite (140+ tests)
```

## API Controllers
- `api/auth.py`: Registration, login, profile (`/me`), avatar upload/delete/serve.
- `api/projects.py`: Project CRUD, Playtest session submission & listing, AI Playtest Critique analysis, Versioned Improvement application, Blueprint derivation, Remix, Version history listing.
- `api/builds.py`: Async build job submission, authoritative status polling, SSE token issuance, live SSE log event streaming, cancellation.
- `api/discovery.py`: Hybrid search, similar games, more-like-this, and build-inspiration extraction.
- `api/saved_discoveries.py`: User-scoped bookmarks.
- `api/profile.py`: XP/level progression status, behavioral genre preferences.
- `api/health.py`: Healthcheck probe (process-alive only, no dependency checks, by design).

## Services
- `ProjectService`: Manages projects, playtest sessions, version revisions, blueprint derivation, remix application, and IDOR validation.
- `BuildService`: Orchestrates async build worker lifecycle, streams SSE events, executes generation pipeline, persists project on success.
- `GameGenerationService`: Generates dual `GameDesignSpec` + `GameDSL`, orchestrates schema + gameplay quality validation, bounded AI repair, playtest critique, DSL patching, and remix application.
- `DiscoveryService`: Multilingual normalized hybrid FAISS vector + BM25 lexical discovery, with optional IGDB enrichment.
- `AuthService`: Argon2 password hashing and JWT token issuance.
- `AvatarService`: Profile picture upload validation (PNG/JPEG/WebP, 2MB max) and file serving.
- `PreferenceService`: Computes behavioral genre-affinity distribution (Game DNA) from user activity.
- `ProgressionService`: Server-authoritative XP grants, level calculation, and milestone evaluation/unlocking.

## Database & Migrations
- `users`: User identity, level, and avatar.
- `projects`: Projects with `design_spec`, `game_dsl`, `current_version`, `runtime_metadata`, `scale`, `world_mode`.
- `playtest_sessions`: Game telemetry metrics & cached AI critique.
- `project_versions`: Immutable revision history for each project version, including remix intents.
- `build_jobs`: Async build jobs and terminal status.
- `build_logs`: Sequenced compile logs.
- `saved_discoveries`: User-saved catalog bookmarks.
- `user_progress`, `xp_events`, `user_milestones`: Creator Progression (XP, level, milestone unlocks).
- `user_genre_preferences`: Game DNA behavioral genre-affinity scores.

Alembic migrations (verified against `backend/alembic/versions/` and `alembic heads`, single unbroken chain, one head):
- `57a6f0ac8836`: Create projects table (initial baseline)
- `1fe395775e52`: Create build_jobs and build_logs tables
- `efcb82ffe8c4`: Add game_dsl column to build_jobs table
- `7b8c9d0e1f2a`: Add game_dsl and runtime_metadata to projects table
- `a1b2c3d4e5f6`: B7 — users, ownership fields, and saved_discoveries
- `c3d4e5f6a7b8`: Game Generation V2 (`design_spec`, `current_version`, `playtest_sessions`, `project_versions`)
- `d4e5f6a7b8c9`: Product Expansion V1 (`avatar_url`, `user_progress`, `xp_events`, `user_genre_preferences`)
- `e5f6a7b8c9d0`: Creator Progression V1 (`user_milestones`)
- `f6a7b8c9d0e1`: Phase 4 — Blueprint/Remix (`remix_intent` column on `project_versions`)
- `a2b3c4d5e6f7`: Phase 5 — `scale` column on `build_jobs`
- `b3c4d5e6f7a8`: Phase 6 — `world_mode` column on `build_jobs`
- `bc9ae398f146`: `scale` and `world_mode` columns on `projects`
- `c1d2e3f4a5b6`: Add `token_version` column to `users` table for session revocation (ADV-SEC-003)
- `e1f2a3b4c5d6`: Add `ForeignKey("build_jobs.id", ondelete="CASCADE")` to `build_logs` table (ADV-DB-001)
- `f2a3b4c5d6e7` (head): Drop redundant explicit unique indexes `ix_users_email` and `ix_users_username` from `users` table; uniqueness enforced via named table-level `UniqueConstraint` only (ADV-DB-002)

## Concurrency, Streaming & Worker Topology (ADV-ARCH-001)

### Single Application Worker Constraint
The backend utilizes an in-process, in-memory event broadcaster ([`BuildEventBroadcaster`](file:///C:/Users/Piyush148/Documents/AI%20Game/backend/app/services/build_service.py#L38-L79)) to route live Server-Sent Events (SSE) during async game generation. The broadcaster maintains subscriber queues in an in-memory dictionary (`self._subscribers: Dict[str, Set[asyncio.Queue]]`).

Consequently, the deployment topology is strictly constrained to **one application worker per server instance**:
- The launcher (`start.bat:338`) starts Uvicorn with `--reload` and no `--workers` flag, running exactly one application worker (supervised by the reloader process).
- The in-process broadcaster and the sliding-window rate limiter ([`SlidingWindowRateLimiter`](file:///C:/Users/Piyush148/Documents/AI%20Game/backend/app/auth/rate_limit.py#L22)) are process-local.
- If multiple application workers were deployed (`uvicorn --workers > 1`), an SSE client connection served by Worker B would not receive events published by the background compilation worker running on Worker A.

### Horizontal Scaling & Distributed Message Broker Roadmap
Per **ADR-004** (*"FastAPI-compatible async/background execution. Do not add Celery/Redis initially"*) and project constitutional rules (*"Avoid premature complexity"*), external message brokers (Redis, RabbitMQ, Celery) are omitted from current phases.

When horizontal multi-worker scaling is approved under a future ADR:
1. **Pub/Sub Broadcaster**: The in-memory `BuildEventBroadcaster` will be swapped for a distributed message broker (Redis Pub/Sub). The `stream_events()` SSE generator interface and client-side SSE protocol will remain 100% unchanged.
2. **Distributed Rate Limiting**: The process-local `SlidingWindowRateLimiter` will be backed by a shared Redis sorted-set window.
3. **Database Concurrency**: The SQLite database will transition to PostgreSQL to support concurrent multi-process writes.

### Rate Limiting (ADV-SEC-001, ADV-SEC-005)
The in-memory [`SlidingWindowRateLimiter`](file:///C:/Users/Piyush148/Documents/AI%20Game/backend/app/auth/rate_limit.py#L22) protects all sensitive write endpoints:
- `login:{ip}` — 10 attempts/IP/15 min
- `register:{ip}` — 5 attempts/IP/hour
- `save:{user_id}` — 50 saves/user/hour
- `preference_mutate:{user_id}` — 20 Game DNA preference operations/user/hour (combined `POST /preferences/reset` + `POST /preferences/onboard`) (ADV-SEC-005)

All rate limit buckets are process-local. Under ADR-004 single-worker deployment, this is consistent. Distributed rate limiting is deferred to the horizontal scaling ADR.
