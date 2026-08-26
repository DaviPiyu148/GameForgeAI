# 13 — Security

## Secrets Management
- Server-side only: AI provider credentials (Gemini, Groq), JWT signing key (`AUTH_JWT_SECRET`), database paths.
- Application startup rejects missing JWT secrets.
- Secrets are never exposed to the frontend or written to git.

## Authentication & Password Hashing
- Passwords hashed with Argon2id via `pwdlib[argon2]`. Plaintext passwords are never stored, logged, or serialized.
- Minimum password length: 8 characters; maximum length: 128 characters.
- JWT Access tokens signed via PyJWT with HS256 algorithm and 60-minute expiration.
- User enumeration prevention: `POST /api/auth/login` returns identical generic error messages for unknown email vs wrong password.

## Authorization & IDOR Protection
- `user_id` is always resolved server-side from `get_current_user` JWT dependency; never trusted from client payloads.
- Strict ownership checks on all private resources:
  - Projects (`/api/projects/{id}`)
  - Build Jobs & Logs (`/api/builds/{id}`)
  - Saved Discoveries (`/api/saved-discoveries/{id}`)
  - Playtest Sessions (`/api/projects/{id}/playtests`)
  - AI Playtest Analysis (`/api/projects/{id}/analyze-playtest`)
  - Improvements (`/api/projects/{id}/improvements`)
  - Blueprint & Remix (`/api/projects/{id}/blueprint`, `/api/projects/{id}/remix`)
  - Project Versions (`/api/projects/{id}/versions`)
  - Profile & Personalization (`/api/profile/progress`, `/api/profile/preferences`) — `user_id` resolved from the JWT, no cross-user query path exists
  - Avatar upload/delete (`/api/auth/avatar`) — scoped to the authenticated user; the public `GET /api/auth/avatar/{filename}` serve route is intentionally unauthenticated (an unguessable server-generated filename, not a directory listing) since it backs plain `<img>` tags
- Cross-user access returns HTTP 404 (never 403) to prevent resource ID enumeration.

## Game Generation V2 AI Safety Boundary
- **Zero Arbitrary Execution**: Never generate raw JavaScript strings, `eval()`, or `new Function()`.
- **Closed Capability Set**: Gemini outputs structured JSON (`GameDesignSpec` + `GameDSL`) matching strict Pydantic v2 schemas.
- **Script Injection Sanitization**: All text and string fields are scanned against prohibited injection markers (`<script>`, `javascript:`, `eval(`, `new Function`, `__proto__`, `process.`, `require(`, `import `).
- **Bounded AI Repair**: Retries are strictly capped at 2 iterations to avoid unbounded token consumption or runaway generation loops.
- **Gameplay Quality Gate**: Prevents unplayable spawns (< 60px hazard clearance) or broken rule triggers from reaching the player.

## Rate Limiting & Safe Error Handling
- Sensitive endpoints protected by sliding window rate limiters.
- Standard error envelope (`{ "error": { "code": "...", "message": "...", "request_id": "..." } }`) prevents stack trace leakage.
