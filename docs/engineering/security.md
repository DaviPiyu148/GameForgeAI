# 13 — Security

## Security Principle

Security is a system property.

Do not rely on frontend checks, hidden routes, client-supplied ownership, or model behavior for security-critical guarantees.

## Secrets

Server-side only:

- AI provider credentials
- JWT signing secret
- Database credentials/paths
- Deployment credentials

Rules:

- Validate required secrets at startup.
- Never expose backend secrets through frontend build variables.
- Never commit credentials to Git.
- Never log secrets or bearer tokens.

## Authentication

Current model:

- JWT Bearer
- HS256
- Configurable access-token lifetime
- Token-version revocation
- Argon2id password hashing

Password rules:

- Minimum documented length: 8
- Maximum documented length: 128
- Plaintext passwords are never stored, logged, or returned

Login should avoid user enumeration by keeping credential-failure responses generic.

## Authorization / IDOR

Authenticated `user_id` is resolved server-side.

Private ownership applies to:

- Projects
- Builds/logs
- Saved discoveries
- Playtests
- Playtest analysis
- Improvements
- Blueprint/remix
- Project versions
- Profile/personalization
- Avatar mutation

Cross-user access returns `404` where enumeration resistance requires it.

## AI Security Boundary

Never:

- Generate arbitrary executable JavaScript
- Use `eval()`
- Use `new Function()`
- Trust raw LLM output
- Allow model output to bypass DSL validation

All generated structured data passes schema validation and gameplay/runtime safety gates.

Text/schema security validation must remain aligned with the actual supported input and output model; marker lists alone are not a complete security boundary.

## Provider Security

The frontend never receives LLM provider credentials.

Provider-specific SDK/API details remain behind the provider abstraction.

Provider timeouts/retries must be bounded.

Prompts/responses must not be logged indiscriminately if they may contain sensitive user data.

## Rate Limiting

Current process-local policies include:

- Login
- Registration
- Saved discovery mutations
- Combined Game DNA preference mutations

Process-local limits are valid only under the current single-worker deployment topology.

Global/distributed rate limiting requires shared storage and an explicit scaling decision.

## Error Security

Use structured safe errors.

Never expose:

- Tracebacks
- SQL errors
- Internal paths
- Credentials
- Provider secrets
- Sensitive user data

Keep detailed diagnostic data server-side.

## File Upload Security

Avatar handling must enforce:

- Allowlisted image formats
- Size limits
- Generated server-side filenames
- No path traversal
- No arbitrary filesystem writes
- No directory listing

Public serving of avatar files must not imply public filesystem access.

## Proxy Security

Never trust `X-Forwarded-For` blindly.

Trust forwarded client IP information only when the ASGI/deployment layer explicitly trusts the connecting proxy.

Application endpoints must not implement ad-hoc forwarded-header parsing.

## Production Hardening Requirements

Before internet-facing production, evaluate:

- TLS
- Secure headers
- CSP where applicable
- CORS allowlist
- CSRF strategy where cookie authentication is used
- Secret rotation
- Backup security
- Dependency scanning
- Supply-chain controls
- Audit logging
- Alerting
- Abuse detection

Only claim these controls as implemented when verified in the deployed environment.
