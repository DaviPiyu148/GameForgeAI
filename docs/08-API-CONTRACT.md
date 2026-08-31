# 08 — API Contract

## Principles
REST for ordinary operations, SSE for build events, Pydantic schemas, consistent safe errors, backend-authoritative build outcomes, JWT Bearer authentication, and IDOR protection.

---

## Authentication & Identity (IMPLEMENTED — B7, extended Product Expansion V1, Small Product Fixes V2)
- `POST /api/auth/register` -> Register a new account. Body: `{ email, username, password }`. Rate limit: 5/hr/IP. Returns `201 Created` with `{ user, access_token, token_type }`.
- `POST /api/auth/login` -> Authenticate existing user. Body: `{ email, password }`. Rate limit: 10/15min/IP. Returns `200 OK` with `{ user, access_token, token_type }`. Generic error on failure.
- `GET /api/auth/me` -> Fetch profile of current authenticated user. Requires `Authorization: Bearer <token>`. Returns `{ id, email, username, level, avatar_url, created_at, updated_at }`.
- `PATCH /api/auth/me` -> Alias for `PATCH /api/auth/profile` (see below).
- `PATCH /api/auth/profile` -> Update the authenticated user's public display username. Requires `Authorization: Bearer <token>`. Body: `{ username: string }`. Validates: 3–32 chars, alphanumeric/underscore/hyphen, globally unique. Returns `200 OK` with `{ id, email, username, level, avatar_url, created_at, updated_at }`. Conflict returns `409` (`USERNAME_TAKEN`). Validation failure returns `422`.
- `POST /api/auth/change-password` -> Change the authenticated user's password. Requires `Authorization: Bearer <token>`. Body: `{ current_password: string, new_password: string }`. Validates current password via Argon2 verify before hashing new one. Enforces minimum 8-char strength. Returns `200 OK` with `{ success: true, message: string }`. Wrong current password returns `400` (`INVALID_CURRENT_PASSWORD`).
- `POST /api/auth/avatar` -> Upload/replace profile picture. Requires `Authorization: Bearer <token>`. Body: multipart form file (PNG/JPEG/WebP, max 2MB). Returns `200 OK` with `{ avatar_url, message }`. Invalid file returns `422` (`INVALID_AVATAR`).
- `DELETE /api/auth/avatar` -> Remove custom avatar, revert to default placeholder. Requires `Authorization: Bearer <token>`. Returns `200 OK` with `{ avatar_url: null, message }`.
- `GET /api/auth/avatar/{filename}` -> Serve an uploaded avatar image file. No authentication (publicly servable static asset by design — the filename is an unguessable server-generated identifier, not a listing). Returns the image, or `404` (`AVATAR_NOT_FOUND`).

---

## Health (IMPLEMENTED — B0)
- `GET /api/health` -> `{ "status": "ok", "service": "gameforge-api" }`

---

## Projects (IMPLEMENTED — B1, extended B5, B7, G12)
*All routes require `Authorization: Bearer <token>`.*
- `GET /api/projects` -> List authenticated user's projects (ordered newest first, supports `?limit=&offset=`). Returns `gameDsl`, `designSpec`, `currentVersion`, and `runtimeMetadata`.
- `GET /api/projects/{id}` -> Fetch single project by ID (returns 200 or 404). Owner mismatch returns 404.
- `PATCH /api/projects/{id}` -> Update allowed editable fields (`title`, `genre`, `prompt`, `parameters`, `game_dsl`). Owner mismatch returns 404.
- `POST /api/projects/{id}/playtests` -> Submit completed playtest session and telemetry metrics (`duration_seconds`, `score`, `damage_taken`, `enemies_defeated`, `outcome`). Returns `201 Created`.
- `GET /api/projects/{id}/playtests` -> List all playtest sessions for the owned project. Returns `200 OK`.
- `POST /api/projects/{id}/analyze-playtest` -> Run AI Playtest Critique on gameplay telemetry. Returns structured `PlaytestAnalysisResponse` with `fun_rating`, `difficulty_rating`, `clarity_rating`, `strengths`, `problems`, and `recommendations`.
- `POST /api/projects/{id}/improvements` -> Apply approved recommendations to create a new project version revision (`version_number` incremented, `game_dsl` patched). Returns `200 OK`.
- `GET /api/projects/{id}/blueprint` -> Derive and return the nontechnical `GameBlueprint` (title, genre, core loop, levels, objectives, progression, allowlist-derived `supported_mechanics`, finale) purely from the project's already-validated `GameDesignSpec` + `GameDSL`. Returns `200 OK`. Owner mismatch returns 404; unavailable (e.g. missing design_spec) returns `400` (`BLUEPRINT_UNAVAILABLE`).
- `POST /api/projects/{id}/remix` -> Apply 1-3 structured `RemixIntent` objects from a closed catalog (`increase_combat`, `increase_exploration`, `increase_difficulty`, `decrease_difficulty`, `add_levels`, `more_story`, `faster_pace`, `more_enemies`, `change_theme`) to create a new immutable project version, through the same validation/repair pipeline as fresh generation. Body: `{ intents: [{ type, strength? }] }`. Duplicate or mutually-exclusive intents (`increase_difficulty` + `decrease_difficulty`) are rejected with `422` before any AI call. Returns `200 OK` with `{ project_id, version_number, game_dsl, design_spec, blueprint, change_summary, status }`. Owner mismatch returns 404.
- `GET /api/projects/{id}/versions` -> List revision history of the project. Returns `200 OK`.

*Note: Project creation is internal to the build pipeline upon successful build compilation.*

---

## Builds (IMPLEMENTED — B2, extended B7, Phase 5/6, SecFix)
*All routes require `Authorization: Bearer <token>`.*
- `POST /api/builds` -> Submit new build job (request contains prompt + parameters including `scale` and `world_mode`; returns HTTP 202 Accepted with server-generated `build_id`, `user_id` bound from token, and initial status).
- `GET /api/builds/{id}` -> Authoritative build status, timestamps, `project_id` (if SUCCESS), or error details (if ERROR). Owner mismatch returns 404.
- `GET /api/builds/{id}/logs` -> Retrieve all persisted logs in ascending sequence order. Owner mismatch returns 404.
- `POST /api/builds/{id}/sse-token` -> Issue a short-lived (90s TTL) SSE credential bound to `{id}` for secure EventSource streaming without exposing long-lived JWT bearer tokens in URLs. Returns `{ "sse_token": "...", "expires_in_seconds": 90 }`.
- `GET /api/builds/{id}/events` -> Server-Sent Events (`text/event-stream`) streaming live logs and status transitions until terminal state. Authenticated via `?sse_token=<short-lived-token>` or `Authorization: Bearer <token>`. Owner mismatch returns 404 before stream starts.
## Discovery & Recommendations (IMPLEMENTED — B6, Discovery 2.2, Discovery Intelligence V1)
- `POST /api/discovery/search` -> Search games using natural language descriptions, entity names, or concepts. Optional filters, modes (`BEST_MATCH`, `DISCOVER`, `HIDDEN_GEMS`, `POPULAR`), and session context (`refinements`, `less_like_this_game_ids`, `temporary_avoid_tags`). Returns `DiscoverySearchResponse` with calibrated score, grounded evidence, honest trade-offs, and personalization reasons.
- `POST /api/discovery/feedback` -> Submit user feedback (`like`, `dislike`, `less_like_this`). `like` awards rate-limited anti-spam progression XP; negative feedback refines session context without rewarding exploits. Returns `200 OK` with `{ status, game_id, feedback, message }`.
- `GET /api/discovery/similar/{steam_app_id}` -> Retrieve similar games based on nearest neighbor vectors in FAISS.
- `POST /api/discovery/more-like-this` -> Multi-seed recommendation blend.
- `GET /api/discovery/build-inspiration/{steam_app_id}` -> Extract 2D prototype archetype, modules, and starter prompt.
- `POST /api/discovery/compare` -> Compare 2-3 games side-by-side using catalog metadata. Returns `CompareGamesResponse` with `games`, `common_genres`, `common_tags`, `common_modes`, and `differentiating_tags`.

- `GET /api/profile/progress` -> Server-authoritative XP/level/milestone status. Returns `200 OK` with `{ user_id, total_xp, current_level, creator_title, current_level_base_xp, next_level_xp, xp_into_level, xp_needed_for_next, progress_percentage, milestones: [{ milestone_key, title, description, icon, xp_bonus, is_unlocked, unlocked_at }], unlocked_milestone_count, total_milestone_count, recent_events: [{ id, event_type, xp_amount, source_reference, created_at }] }`.
- `GET /api/profile/preferences` -> Behavioral genre-affinity distribution ("Game DNA") derived from search/save/build/play activity. Returns `200 OK` with `{ user_id, top_genres: [{ genre, score, percentage, interaction_count, affinity_tier }], total_interactions, strongest_match, recent_interest, avoidances, suggested_explorations, confidence_level, summary_headline, has_sufficient_data }`.
- `POST /api/profile/preferences/onboard` -> Establish bounded initial Game DNA starter preferences (`genres`, `enjoyments`, `avoidances`). Returns updated `UserPreferencesResponse`.
- `POST /api/profile/preferences/reset` -> Safely wipe Game DNA preference signals without deleting saves, projects, or progression XP. Returns `{ status, message, user_id }`.


---

## Discovery & Recommendations (IMPLEMENTED — Discovery 2.0 & 2.2)
*Public endpoints; no authentication required.*
- `POST /api/discovery/search` -> Hybrid semantic + lexical retrieval with calibrated score bands (`prompt`, `limit`, `filters`).
  - Response envelope: `{ query, match_count, no_strong_match, query_type, target_entity, results: [ { game, score, match_highlights, explanation } ] }`.
  - `game` item contract includes explicit display & provenance fields:
    - `title` / `display_title`: Canonical English title for clean UI rendering.
    - `description` / `display_description`: Human-readable English description (native English, normalized English synopsis, or IGDB summary).
    - `description_language`: ISO code (`"en"`, `"ru"`, `"zh"`, `"es"`, `"fr"`, etc.).
    - `description_source`: Provenance indicator (`"steam"`, `"normalized"`, `"igdb"`, `"original"`).
    - `genres` / `display_genres`: Standardized English canonical genres.
    - `original_genres`: Raw source genre taxonomy.
    - `tags` / `display_tags`: High-signal gameplay community tags.
    - `original_description`: Immutable raw source description text.
    - `enrichment`: Optional IGDB media cover and screenshot URLs.
- `GET /api/discovery/similar/{steam_app_id}` -> Find games similar to a given canonical game seed (`limit`).
- `POST /api/discovery/more-like-this` -> Blended multi-seed discovery recommendation (`game_ids` or `seed_game_ids`, `limit`, `filters`).
- `GET /api/discovery/build-inspiration/{steam_app_id}` -> Extract Game DNA blueprint parameters (`inferred_archetype`, `inferred_theme`, `recommended_prompt`, `suggested_modules`, `suggested_art_density`, `suggested_physics`) for compiler pipeline.

---

## Saved Discoveries (IMPLEMENTED — B7)
*All routes require `Authorization: Bearer <token>`.*
- `GET /api/saved-discoveries` -> List authenticated user's saved game discoveries with catalog metadata (title, genres) resolved server-side.
- `POST /api/saved-discoveries` -> Save a game discovery. Body: `{ steam_app_id }`. Rate limit: 50/hr/user. Returns `201 Created`. Duplicate save returns `409 Conflict`.
- `DELETE /api/saved-discoveries/{id}` -> Remove a saved discovery bookmark. Owner mismatch returns 404. Returns `204 No Content`.

---

## Error Envelope Format
```json
{
  "error": {
    "code": "PROJECT_NOT_FOUND",
    "message": "Safe error description",
    "request_id": "uuid-string"
  }
}
```

Standard codes supported: `UNAUTHORIZED`, `INVALID_CREDENTIALS`, `EMAIL_ALREADY_EXISTS`, `USERNAME_TAKEN`, `RATE_LIMITED`, `PROJECT_NOT_FOUND`, `BUILD_NOT_FOUND`, `SAVED_DISCOVERY_NOT_FOUND`, `ALREADY_SAVED`, `VALIDATION_FAILED`, `BLUEPRINT_UNAVAILABLE`, `REMIX_FAILED`, `IMPROVEMENT_FAILED`, `INVALID_AVATAR`, `AVATAR_UPLOAD_FAILED`, `AVATAR_DELETE_FAILED`, `AVATAR_NOT_FOUND`.
Do not expose tracebacks. Do not let clients arbitrarily mutate build status or bypass ownership.
