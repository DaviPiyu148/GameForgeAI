# ADR-007 — Authentication, Authorization, and User Ownership

**Status:** Accepted

## Context
Prior to Phase B7, GameForge AI had no persistent user accounts; projects and builds were unowned, and the frontend relied on mock identities. To support multi-user isolation, secure access control, persistent saved discoveries, and IDOR protection, a lightweight, production-grade authentication and authorization mechanism is required.

## Decision
1. **Authentication Framework**: JWT Bearer authentication signed with HS256 (`PyJWT`), with access token lifetimes set to 60 minutes (`AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`).
2. **Password Hashing**: Argon2 password hashing via `pwdlib[argon2]`. Plaintext passwords are never stored, logged, or serialized.
3. **User Identification**: `user_id` is always derived on the server side via `Depends(get_current_user)` from the validated JWT token. Request bodies and query parameters are forbidden from supplying or overriding `user_id`.
4. **Ownership Model**:
   - `projects.user_id` and `build_jobs.user_id` establish resource ownership.
   - `saved_discoveries` table stores bookmark keys (`steam_app_id`) scoped per user with `UNIQUE(user_id, steam_app_id)` and cascade deletion on user removal.
   - All private resources return `404 Not Found` (rather than `403 Forbidden`) on unauthorized/cross-user access to prevent IDOR resource enumeration.
5. **Rate Limiting**: In-memory sliding window rate limiting for authentication endpoints (`POST /api/auth/login`, `POST /api/auth/register`) and bookmarking (`POST /api/saved-discoveries`). Redis is deferred to Phase B8.
6. **Frontend Integration**: An in-context modal (`AuthModal`) handles login and registration without adding secondary routing, preserving the frozen 7-primary-route architecture invariant. Token storage is held in `localStorage` for session persistence.

## Consequences
- Multi-user isolation is enforced server-side.
- User A cannot view, mutate, stream logs from, or delete User B's projects, builds, or saved discoveries.
- Discovery search (`POST /api/discovery/search`) remains public with zero authentication required.
- Building prototypes and saving discoveries requires an active authenticated session.
