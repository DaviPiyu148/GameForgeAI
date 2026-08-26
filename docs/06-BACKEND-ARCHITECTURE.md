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
- `bc9ae398f146` (head): `scale` and `world_mode` columns on `projects`
