# ADR-007 — Authentication, Authorization, and User Ownership

**Status:** Accepted

## Context

GameForge AI supports persistent users and private projects/builds/saved discoveries.

Multi-user isolation requires server-side identity, authorization, resource ownership, and protection against IDOR/BOLA-style access.

Authentication must be simple enough for the current product while providing password protection, token revocation, and bounded abuse protection.

## Decision

### Authentication

Use JWT Bearer authentication signed with HS256 through `PyJWT`.

Access tokens have a configurable lifetime, currently defaulted to 60 minutes through:

`AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`

The signing secret must come from secure configuration and must never be committed or exposed to the frontend.

### Password hashing

Use Argon2 through `pwdlib[argon2]`.

Plaintext passwords must never be:

- Stored
- Logged
- Serialized
- Returned by APIs

### Server-derived identity

The authoritative `user_id` is derived from the validated JWT through the server-side authentication dependency.

Request bodies and query parameters must not be allowed to override the authenticated user identity.

### Token revocation

JWTs include a server-controlled token-version claim.

The user record stores the corresponding token version.

When credentials change or reset flows require invalidation, increment the server-side token version.

Tokens with a missing/outdated version must be rejected according to the authentication contract.

This provides server-side revocation semantics without requiring a per-token blacklist for the current architecture.

## Ownership

Ownership is enforced server-side.

Current primary ownership fields include:

- `projects.user_id`
- `build_jobs.user_id`

Saved discoveries are scoped by user with a logical uniqueness boundary such as:

`UNIQUE(user_id, steam_app_id)`

Resource deletion that removes owned records must use correct cascading semantics where intentionally defined.

## Authorization

For every private resource:

1. Authenticate the caller.
2. Determine ownership/permission server-side.
3. Reject unauthorized access.
4. Never trust a client-provided owner identifier.

Private cross-user resource access returns `404 Not Found` where appropriate to avoid resource enumeration.

Authorization applies to:

- Project reads/mutations
- Build reads/streaming/deletion
- Saved discoveries
- Other private resources added later

New private resource types must define ownership explicitly before implementation.

## Public vs Protected APIs

Discovery search may remain public.

Operations that create or mutate user-owned project/build state or private saved data require authentication.

The exact endpoint protection matrix belongs in the API contract/current status documentation and must remain consistent with this ADR.

## Rate Limiting

Authentication and sensitive mutation endpoints require rate limiting.

The current baseline uses in-memory sliding-window rate limiting.

Process-local limits must be understood as process-local. If the deployment becomes multi-worker or multi-instance, shared rate-limit state requires an explicit architecture decision.

Do not claim global rate limiting while using process-local memory.

Rate-limit policies for different product operations should be documented separately rather than silently coupled.

## Frontend Session Storage

The current frontend persists authentication/session state in browser storage for session continuity.

Because browser storage is exposed to JavaScript running in the origin, this decision carries an XSS tradeoff.

Production frontend changes must therefore preserve strong input/output handling and CSP/security controls where appropriate.

A migration to more restrictive cookie/session handling would be a separate security/architecture decision and must account for CSRF, API behavior, and deployment topology.

## Security Requirements

Never:

- Accept `user_id` as authoritative client input.
- Return another user's private resource.
- Leak password hashes.
- Log credentials/tokens.
- Expose JWT signing secrets.
- Treat authentication as authorization.
- Convert authentication/database failures into anonymous access.
- Depend on frontend checks for ownership protection.

## Consequences

### Positive

- Clear multi-user isolation boundary.
- Simple server-side authorization model.
- Passwords are strongly hashed.
- Credential changes can revoke prior tokens.
- `404` behavior reduces private-resource enumeration.

### Negative

- HS256 requires secure secret management.
- In-memory rate limiting is not globally shared.
- Browser storage increases the impact of an XSS vulnerability.
- JWTs require careful revocation/versioning semantics.

## Deferred

- Distributed rate limiting
- PostgreSQL-backed security infrastructure
- External identity providers
- More complex session management

These require concrete product/security requirements and an explicit architecture/security decision.

## Security Testing Requirements

Authentication/authorization changes should test at least:

- Invalid credentials
- Expired tokens
- Missing/invalid token
- Outdated token version
- Cross-user project access
- Cross-user build access
- Cross-user stream access
- Cross-user saved-discovery access
- Duplicate ownership-bound records
- Rate-limit boundaries
- Database/infrastructure failure behavior
