# 15 — Current Status

## Date
2026-08-24

## Current Phase
Phase 6 — Generalized Open World Game System V1 (Complete). Third of the Phases
4-8 master product expansion. Establishes a general-purpose, reusable open-world
runtime capability across schemas, deterministic validation, AI prompts, and
modular Phaser runtime subsystems without game-specific hardcoding.

## Phase 6 Summary
- **Generalized Open World Schemas**: `open_world_models.py` defining `RegionDef`,
  `WorldConnectionDef`, `POIDef`, `ActivityDef`, `ActorDef`, `FactionDef`,
  `VehicleDef`, `ThreatSystemDef`, `WorldTimeDef`, `WorldEventDef`, and `OpenWorldDef`.
- **Architectural Mode Separation**: Preserved `world_mode` (`linear`, `campaign`, `open_world`)
  and `scale` (`prototype`, `standard`, `campaign`) as independent dimensions across
  frontend builder, build jobs, database (`world_mode` column with Alembic migration `b3c4d5e6f7a8`),
  and generation prompts.
- **Deterministic Open World Validation & Repair**: BFS reachability graph validation
  across regions (`reachability.py`), open-world budget enforcement and reference
  integrity (`quality_validator.py`), and robust input normalization with actor behavior
  capability enforcement (`validator.py`).
- **Modular Phaser Open-World Runtime**: 7 standalone managers (`WorldManager`,
  `RegionManager`, `VehicleManager`, `ActivityManager`, `FactionManager`, `ThreatManager`,
  `WorldEventManager`) in `gameforge-ai/src/runtime/` driving vehicle entry/exit (`E`),
  top-down driving physics, district edge transitions, POI discovery, and live HUD.
- **Verification**: 327/327 backend tests passing; frontend `tsc`/`oxlint`/`build` clean;
  live end-to-end API generation with Gemini 3 Flash verified generating playable open-world
  prototypes with multiple regions, vehicles, factions, and activities.
- Real server-side scale tiers (`prototype`/`standard`/`campaign`) threaded from
  `BuilderPage.tsx` through `BuildJob.scale` into `generate_game_dsl()` and the
  generation prompt -- previously a frontend-only cosmetic dropdown.
- Floor-only budget validation (`GameplayQualityValidator.validate_scale_budget()`)
  gives an under-target generation exactly one bounded-repair nudge; still-short
  results are accepted with a warning rather than hard-failing the build.
- Fixed the Phaser runtime only ever rendering level 0's visuals: `GameScene.ts`'s
  new `applyLevelConfig()` is the single source of truth for background/theme,
  spawn, entities, and HUD text on both initial load and every level transition,
  so a multi-level campaign now actually looks and plays differently level to
  level. Entity/player DSL `color` fields are now rendered (previously generated
  but ignored). Level transitions use a deterministic 200ms fade instead of an
  instant teleport, plus a bounded spawn-in tween for new entities.
- Bounded boss/finale support: `EntityDef.is_boss/boss_phases/telegraph_ms` and
  `LevelDef.is_finale`, all backward-compatible defaults. Boss fairness and
  telegraph-compatibility are enforced server-side; runtime adds a boss health
  bar/intro banner, one deterministic phase-2 threshold behavior bump, and a
  fixed-duration ranged-attack telegraph cue -- no boss AI state machine.
- Verification: 317/317 backend tests pass (33 new); frontend `tsc`/`oxlint`/`build`
  clean; single Alembic head (`a2b3c4d5e6f7`), migration applied via `alembic
  upgrade head`. Browser E2E not performed this phase.
- Explicitly out of scope: graphical minimap, procedural per-theme texture packs,
  multi-phase boss AI beyond one threshold bump, a separate World/Area sub-model.

## Since the 2026-08-18 Baseline (previously undocumented here)
- **Discovery Visual Experience V1** (commit `9d83d0b`)
- **Game DNA & Personalization V1** (commit `29f7379`): behavioral genre-affinity
  tracking (`preference_service`), fed into generation/remix prompts strictly as
  secondary flavor context, never overriding explicit user intent.
- **Product Expansion V1** (commit `0e89b21`): `GameDSL` schema v3.0 multi-level
  campaign support (`levels: List[LevelDef]`, capped at 5), deterministic
  reachability validator/repair pass, avatar service.
- **Creator Progression V1** (commit `3765d5a`): server-authoritative XP, creator
  levels, milestones, activity rewards, profile progression UI.
- **Gemini API Key Rotation** (commit `60de2d9`): `RotatingGeminiProvider` rotates
  round-robin across a configurable pool of Gemini API keys (`GEMINI_API_KEY` +
  comma-separated `GEMINI_API_KEYS`), spreading load and transparently routing
  around a rate-limited (429) or rejected (401/403) key within the same request.
- **Phase 4 — AI Game Blueprint + Remix**: see below.

## Phase 4 Summary
- `GET /api/projects/{id}/blueprint`: derives a nontechnical `GameBlueprint` purely
  from already-validated `GameDesignSpec` + `GameDSL` data (`app/generation/blueprint.py`).
  `supported_mechanics` is allowlist-derived from real DSL predicates only —
  capabilities that don't exist yet (vehicles, boss fights, wanted systems) can never
  appear, by construction.
- `POST /api/projects/{id}/remix`: closed 9-type structured `RemixIntentType` catalog
  (no free-form prose patches). Reuses the exact validation/quality/reachability/
  bounded-repair pipeline as fresh generation. Creates a new immutable
  `ProjectVersion` (never mutates history), recording the intent(s) that produced it.
- Frontend: `GameBlueprintPanel` and `RemixPanel` wired into the existing
  `PrototypeModal` — no new primary route.
- Verification: 284/284 backend tests pass; frontend `tsc`/`oxlint`/`build` clean;
  single Alembic head (`f6a7b8c9d0e1`). Browser E2E not performed this phase.

## Prior: Forensic Audit Bug Fix & Regression Phase (Complete, 2026-08-18 baseline)

## Summary of Completed Forensic Fixes
- **Security**: CRIT-02 valid Argon2 dummy hash (anti-timing attack), CRIT-01 short-lived SSE credentials (`POST /api/builds/{id}/sse-token`) eliminating bearer tokens from URLs.
- **Data Integrity**: HIGH-05 deep copy DSL in improvement patching, HIGH-03 atomic version bump, HIGH-04 atomic v1 project creation.
- **Phaser Runtime**: MED-05 invincibility frames (500ms cooldown) preventing instant death, MED-06 DSL `player.attack_damage` honoring, MED-07 DSL `player.attack_type` and cooldown honoring, LOW-07 modern iteration API.
- **SSE & API Contracts**: MED-03 zero-race SSE replay, MED-04 PhaserCanvas ref lifecycle, MED-09 navigation cleanup, MED-10 GameEnrichment `AVAILABLE` status contract alignment, MED-01 narrowed prototype constructor injection filter.
- **Performance & Polish**: LOW-01 aligned rule limits, LOW-02 IGDB hot cache TTL eviction, LOW-03 O(1) catalog external_id lookup, LOW-04 centralized auth token constant, LOW-05 timezone-agnostic relative timestamps, LOW-06 DSL schema_version 2.0 default.
- **Deferred**: MED-08 (expanded Phaser entity behaviors) documented as explicitly deferred to upcoming runtime milestone.

## Frontend
- Complete with Discovery 2.0/2.1/2.2 Integration, Phase B7 Real Authentication, and Game Generation V2:
  - **Phaser 2D Canvas**: Embedded Phaser 3.88.2 Arcade Physics engine with smooth drag, dash mobility (`SPACE`/`Shift`), projectile shooting (`Left Click`/`F`), hit flashes, particle bursts, floating damage banners, screen shake, and escalating wave spawner.
  - **Playtest Telemetry Integration**: Non-intrusive runtime telemetry tracker aggregating duration, score, enemies defeated, damage taken, and collectibles gathered.
  - **Interactive AI Improvement Workflow**:
    - "ANALYZE WITH AI" button triggering post-game Gemini critique (`fun_rating`, `difficulty_rating`, `clarity_rating`, strengths, problems).
    - Selectable recommendation checkboxes with targeted DSL change categories.
    - "APPLY IMPROVEMENTS" creating Project Version 2+ and hot-reloading prototype seamlessly.
  - **Natural Logic Builder**: Active Prototype Profile selector ("Top-Down Action", "Arena Survival", "2D Platformer", "Data Collector"), Visual density slider, Physics complexity slider, and Logic Modules toggles.
  - **Production Build**: `npm run build` passing with 0 errors.

## Backend
B0–B7 + Discovery 2.0–2.2 + Game Generation V2 fully operational:
- FastAPI modular monolith with Pydantic v2 schemas and CORS.
- **GameDesignSpec & Expanded Game DSL**:
  - `GameDesignSpec`: Intermediate design spec schema capturing gameplay loop, player role, objectives, abilities, and rationale.
  - `GameDSL`: Schema v2.0 primitives (Player dash, stamina, attack types; Entity patrol/chase/ranged behaviors; Rule triggers & actions; World difficulty scaling).
- **Dual Validation & Bounded AI Repair**:
  - Pydantic v2 type and bound validation + script injection rejection.
  - `GameplayQualityValidator`: Deterministic player spawn clearance (>= 60px), reachability, and rule fairness checks.
  - Bounded AI repair capped at 2 retries with structured compiler log feedback.
- **Database & Versioning**:
  - `playtest_sessions` table recording telemetry metrics.
  - `project_versions` table maintaining immutable revision history for each project.
  - `projects` table extended with `design_spec`, `current_version`, and `game_dsl`.
  - Alembic migration `c3d4e5f6a7b8` applied cleanly.
- **API Endpoints**:
  - `POST /api/projects/{id}/playtests`: Record gameplay session.
  - `GET /api/projects/{id}/playtests`: List playtest sessions.
  - `POST /api/projects/{id}/analyze-playtest`: Trigger AI Playtest Critique.
  - `POST /api/projects/{id}/improvements`: Apply approved recommendations & bump version.
  - `GET /api/projects/{id}/versions`: List version history.

## AI Provider Invariants
Active Provider: Google Gemini (Gemini 3 Flash Preview: `gemini-3-flash-preview`). Zero arbitrary script execution. Closed capability set.

## State Ownership
- `users`: Backend database (`users` table).
- `projects`: Backend database (`projects` table scoped by `user_id`).
- `project_versions`: Backend database (`project_versions` table).
- `playtest_sessions`: Backend database (`playtest_sessions` table).
- `build_jobs` & `build_logs`: Backend database (scoped by `user_id`).
- `savedDiscoveries`: Backend database (`saved_discoveries` table scoped by `user_id`).

## Next Approved Phase
Game Generation V2 completed. Ready for production hardening and deployment (Phase B8).
