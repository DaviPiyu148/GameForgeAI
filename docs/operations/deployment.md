# 14 — Deployment

## Current Topology

```text
Browser
  ├── Vite-built frontend
  └── FastAPI backend
         ├── SQLite
         ├── Hosted LLM provider
         └── Local FAISS/catalog
```

The project is currently optimized for a simple, single-application deployment model.

## Frontend

Build:

```bash
npm run build
```

The result is a static frontend artifact suitable for the selected hosting environment.

Never expose backend secrets through Vite-exposed variables.

## Backend

Development uses Uvicorn directly on loopback.

The current launcher uses a single application worker.

Development reload behavior must not be treated as production process supervision.

## Worker Constraint

The current architecture has process-local:

- SSE build-event subscribers
- Sliding-window rate-limit state

Therefore the current deployment topology is:

**one application worker per server instance.**

Do not deploy multiple application workers without first replacing or redesigning those process-local boundaries.

## Horizontal Scaling Roadmap

Only after an explicit architecture decision:

1. Replace in-process event distribution with shared messaging/pub-sub.
2. Replace process-local rate limiting with shared state.
3. Move SQLite to a database designed for the required concurrent deployment model.
4. Revalidate connection pooling, migrations, transactions, and observability.

Redis/PostgreSQL/Celery are not automatic production requirements.

## Reverse Proxy / Trusted Headers

If production sits behind Nginx, ALB, Cloudflare, Traefik, or another trusted proxy:

- Configure trusted proxy addresses explicitly.
- Enable ASGI proxy-header processing appropriately.
- Do not parse `X-Forwarded-For` inside endpoint code.
- Verify trusted-proxy behavior with both trusted and untrusted peers.

An untrusted client must not be able to spoof its source IP to bypass rate limits.

## Configuration

Representative configuration includes:

- `VITE_API_URL`
- `DATABASE_URL`
- `APP_ENV`
- `CORS_ORIGINS`
- AI provider/model configuration
- JWT secret

Use deployment secret/configuration management.

Do not hardcode ports, hosts, secrets, or environment-specific assumptions into business code.

## Database

Current database:

**SQLite**

Before production:

- Verify backup strategy.
- Verify restore procedure.
- Verify migration process.
- Verify locking/concurrency expectations.
- Verify retention policy.
- Verify filesystem durability.

A move to PostgreSQL should be driven by actual deployment/concurrency requirements.

## AI Provider

Use the hosted AI provider abstraction.

The production system must have:

- Provider credentials securely configured
- Explicit timeout
- Bounded retry/failover behavior
- Safe error handling
- Usage/cost visibility where appropriate

No local LLM fallback is required.

## Health and Readiness

Current `/api/health` is a process-liveness probe.

Before production, define a separate readiness/dependency model if needed.

Do not make the liveness endpoint fail simply because an optional external enrichment provider is unavailable unless that dependency is actually required for serving traffic.

## Observability

Production requires:

- Structured logs
- Correlation IDs
- Build/job IDs
- Error tracking
- Request latency/error metrics
- Build queue/job metrics
- Dependency latency/error metrics
- Alerting

## Release Process

A production release should follow:

```text
verify code
→ run tests
→ build
→ verify migrations
→ deploy backward-compatible application/schema order
→ smoke test
→ observe
→ continue/rollback
```

For risky changes, use a staged/flagged rollout where appropriate.

## Rollback

A rollback plan must account for both application code and persisted data.

Do not assume reverting a binary/container automatically reverts a database migration.

## Backups / Recovery

Before declaring production-ready, establish:

- Backup schedule
- Retention
- Restore procedure
- Recovery owner
- Recovery verification
- Migration recovery process

## Current Status

No claim of actual production deployment should be made until a real deployment and smoke verification have occurred.

The current project status records production deployment hardening as future work.
