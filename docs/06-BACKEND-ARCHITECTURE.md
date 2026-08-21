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
- `api/auth.py`: Registration, login, profile token management.
- `api/projects.py`: Project CRUD, Playtest session submission & listing, AI Playtest Critique analysis, Versioned Improvement application, Version history listing.
- `api/builds.py`: Async build job submission, authoritative status polling, SSE live log event streaming.
- `api/discovery.py`: Hybrid search, similar games, more-like-this, and build-inspiration extraction.
- `api/saved_discoveries.py`: User-scoped bookmarks.
- `api/health.py`: Healthcheck probe.

## Services
- `ProjectService`: Manages projects, playtest sessions, version revisions, and IDOR validation.
- `BuildService`: Orchestrates async build worker lifecycle, streams SSE events, executes generation pipeline, persists project on success.
- `GameGenerationService`: Generates dual `GameDesignSpec` + `GameDSL`, orchestrates schema + gameplay quality validation, bounded AI repair, playtest critique, and DSL patching.
- `DiscoveryService`: Multilingual normalized hybrid FAISS vector + BM25 lexical discovery.
- `AuthService`: Argon2 password hashing and JWT token issuance.

## Database & Migrations
- `users`: User identity & level.
- `projects`: Projects with `design_spec`, `game_dsl`, `current_version`, `runtime_metadata`.
- `playtest_sessions`: Game telemetry metrics & cached AI critique.
- `project_versions`: Immutable revision history for each project version.
- `build_jobs`: Async build jobs and terminal status.
- `build_logs`: Sequenced compile logs.
- `saved_discoveries`: User-saved catalog bookmarks.

Alembic migrations (verified against backend/alembic/versions/, single unbroken chain, one head):
- `57a6f0ac8836`: Create projects table (initial baseline)
- `1fe395775e52`: Create build_jobs and build_logs tables
- `efcb82ffe8c4`: Add game_dsl column to build_jobs table
- `7b8c9d0e1f2a`: Add game_dsl and runtime_metadata to projects table
- `a1b2c3d4e5f6`: B7 — users, ownership fields, and saved_discoveries
- `c3d4e5f6a7b8` (head): Game Generation V2 (`design_spec`, `current_version`, `playtest_sessions`, `project_versions`)
