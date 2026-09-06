# 08 — API Contract

## Principles

- REST for ordinary operations.
- SSE for build events.
- Pydantic-defined contracts.
- Consistent safe error envelopes.
- Backend-authoritative build outcomes.
- JWT Bearer authentication.
- Server-side ownership/IDOR protection.
- Explicit idempotency/conflict semantics where needed.

## Authentication

### Registration

`POST /api/auth/register`

Creates an account.

Rate limited.

Identity is server-generated.

### Login

`POST /api/auth/login`

Authenticates credentials and returns a bearer token.

Unknown-user and wrong-password failures use the same public error semantics.

### Current User

`GET /api/auth/me`

Returns the authenticated user's public account state.

### Profile

`PATCH /api/auth/profile`

Updates allowed profile fields for the authenticated user.

Username uniqueness is enforced server-side and must remain race-safe.

### Password Change

`POST /api/auth/change-password`

Verifies the current password, changes the password, and invalidates prior credentials according to the token-version policy.

### Avatar

`POST /api/auth/avatar`

Upload/replace PNG/JPEG/WebP avatar within the documented size limit.

`DELETE /api/auth/avatar`

Remove the custom avatar.

`GET /api/auth/avatar/{filename}`

Publicly serves an unguessable server-generated avatar asset. It does not expose directory listing or arbitrary filesystem access.

## Health

`GET /api/health`

Returns a process liveness response.

It is not a dependency readiness check.

## Projects

All project endpoints require authentication.

- `GET /api/projects`
- `GET /api/projects/{id}`
- `PATCH /api/projects/{id}`
- `POST /api/projects/{id}/playtests`
- `GET /api/projects/{id}/playtests`
- `POST /api/projects/{id}/analyze-playtest`
- `POST /api/projects/{id}/improvements`
- `GET /api/projects/{id}/blueprint`
- `POST /api/projects/{id}/remix`
- `GET /api/projects/{id}/versions`

Unauthorized ownership access returns `404`.

Project creation is an internal consequence of successful backend build completion rather than an arbitrary client-side persistence operation.

## Builds

All build endpoints require authentication.

- `POST /api/builds`
- `GET /api/builds/{id}`
- `GET /api/builds/{id}/logs`
- `POST /api/builds/{id}/sse-token`
- `GET /api/builds/{id}/events`

`POST /api/builds` returns `202 Accepted`.

The server determines authoritative build state.

SSE may use the short-lived build-specific SSE credential or an authenticated bearer mechanism supported by the current transport.

Do not place long-lived bearer credentials into URLs.

## Discovery

Discovery search is public unless a specific endpoint's contract states otherwise.

- `POST /api/discovery/search`
- `POST /api/discovery/feedback`
- `GET /api/discovery/similar/{steam_app_id}`
- `POST /api/discovery/more-like-this`
- `GET /api/discovery/build-inspiration/{steam_app_id}`
- `POST /api/discovery/compare`

Discovery must preserve hard constraints and explicit avoidances.

## Saved Discoveries

Authenticated:

- `GET /api/saved-discoveries`
- `POST /api/saved-discoveries`
- `DELETE /api/saved-discoveries/{id}`

Duplicate saves return `409 Conflict`.

## Profile / Game DNA

Authenticated:

- `GET /api/profile/progress`
- `GET /api/profile/preferences`
- `POST /api/profile/preferences/onboard`
- `POST /api/profile/preferences/reset`

Preference mutation limits are combined across reset/onboard according to the current security policy.

## Error Envelope

Use:

```json
{
  "error": {
    "code": "PROJECT_NOT_FOUND",
    "message": "Safe error description",
    "request_id": "uuid-string"
  }
}
```

Rules:

- Never expose tracebacks.
- Never expose provider credentials or internal secrets.
- Preserve expected domain/HTTP error semantics.
- Include correlation/request IDs for diagnosability.
- Use `409` for genuine resource/state conflicts.
- Use `422` for validation failures.
- Use `404` for protected-resource ownership mismatches where enumeration resistance is required.

## Compatibility

API changes must consider existing clients.

Do not silently rename fields, change status codes, or alter error semantics relied upon by the current frontend without an intentional compatibility decision.

## Idempotency

Operations that may be retried or duplicated must have deliberate duplicate/conflict semantics.

Do not claim exactly-once behavior without an actual mechanism enforcing it.
