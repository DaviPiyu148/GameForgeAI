# 08 — API Contract

## Principles
REST for ordinary operations, SSE for build events, Pydantic schemas, consistent safe errors, backend-authoritative build outcomes, JWT Bearer authentication, and IDOR protection.

---

## Authentication & Identity (IMPLEMENTED — B7)
- `POST /api/auth/register` -> Register a new account. Body: `{ email, username, password }`. Rate limit: 5/hr/IP. Returns `201 Created` with `{ user, access_token, token_type }`.
- `POST /api/auth/login` -> Authenticate existing user. Body: `{ email, password }`. Rate limit: 10/15min/IP. Returns `200 OK` with `{ user, access_token, token_type }`. Generic error on failure.
- `GET /api/auth/me` -> Fetch profile of current authenticated user. Requires `Authorization: Bearer <token>`. Returns `{ id, email, username, level, created_at, updated_at }`.

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
- `GET /api/projects/{id}/versions` -> List revision history of the project. Returns `200 OK`.

*Note: Project creation is internal to the build pipeline upon successful build compilation.*

---

## Builds (IMPLEMENTED — B2, extended B7, SecFix)
*All routes require `Authorization: Bearer <token>`.*
- `POST /api/builds` -> Submit new build job (request contains prompt + parameters; returns HTTP 202 Accepted with server-generated `build_id`, `user_id` bound from token, and initial status).
- `GET /api/builds/{id}` -> Authoritative build status, timestamps, `project_id` (if SUCCESS), or error details (if ERROR). Owner mismatch returns 404.
- `GET /api/builds/{id}/logs` -> Retrieve all persisted logs in ascending sequence order. Owner mismatch returns 404.
- `POST /api/builds/{id}/sse-token` -> Issue a short-lived (90s TTL) SSE credential bound to `{id}` for secure EventSource streaming without exposing long-lived JWT bearer tokens in URLs. Returns `{ "sse_token": "...", "expires_in_seconds": 90 }`.
- `GET /api/builds/{id}/events` -> Server-Sent Events (`text/event-stream`) streaming live logs and status transitions until terminal state. Authenticated via `?sse_token=<short-lived-token>` or `Authorization: Bearer <token>`. Owner mismatch returns 404 before stream starts.

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

Standard codes supported: `UNAUTHORIZED`, `INVALID_CREDENTIALS`, `EMAIL_ALREADY_EXISTS`, `USERNAME_TAKEN`, `RATE_LIMITED`, `PROJECT_NOT_FOUND`, `BUILD_NOT_FOUND`, `SAVED_DISCOVERY_NOT_FOUND`, `ALREADY_SAVED`, `VALIDATION_FAILED`.
Do not expose tracebacks. Do not let clients arbitrarily mutate build status or bypass ownership.
