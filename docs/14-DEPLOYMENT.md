# 14 — Deployment

## Initial local topology
```text
Browser
 ├─ Vite frontend
 └─ FastAPI backend
       ├─ SQLite
       ├─ Google Gemini (Hosted API)
       └─ local FAISS/catalog
```

## Frontend
`npm run build` creates the static artifact.

## Backend
Development: `uvicorn app.main:app --reload` (started via `start.bat:338`).
The development orchestrator launches Uvicorn directly on loopback (`127.0.0.1:8000`) without a reverse proxy. Forwarded headers are disabled in development.

## Worker Concurrency Constraint (ADV-ARCH-001)
The backend is architected for **one application worker per server instance**:
- The in-process SSE event broadcaster ([`BuildEventBroadcaster`](file:///C:/Users/Piyush148/Documents/AI%20Game/backend/app/services/build_service.py#L38)) maintains in-memory `asyncio.Queue` instances.
- The sliding-window rate limiter ([`SlidingWindowRateLimiter`](file:///C:/Users/Piyush148/Documents/AI%20Game/backend/app/auth/rate_limit.py#L22)) maintains in-memory `OrderedDict` timestamp windows.
- Both subsystems are process-local. Deploying multiple application workers (`uvicorn --workers > 1`) on a single instance or across multiple instances without a shared message broker causes SSE clients to miss compilation events emitted by other workers.

### Production Horizontal Scaling Roadmap (ADR-004)
When horizontal scaling beyond a single application worker is approved under an Architecture Decision Record:
1. Replace the in-memory `BuildEventBroadcaster` with a distributed message broker (Redis Pub/Sub).
2. Replace the in-memory `SlidingWindowRateLimiter` with a distributed cache (Redis sorted-set sliding window).
3. Migrate the database from SQLite to PostgreSQL.

Until such an ADR is approved, deployment topology remains strictly single-worker.

## Reverse-Proxy Deployment Topology & Trusted Headers (ADV-SEC-002)

### Threat Model & Invariants
1. **IP Spoofing Vulnerability**: If application code naively trusts unvalidated `X-Forwarded-For` headers from any incoming socket, malicious clients can forge client IP headers to bypass sliding-window rate limits (such as registration and login attempt caps) or poison audit logs.
2. **Shared Proxy IP Rate Exhaustion**: If a reverse proxy is deployed in front of the application but forwarded headers are completely ignored, all clients appear to arrive from the reverse proxy's internal IP (e.g. `10.0.0.1` or `127.0.0.1`), causing all users to share a single rate-limit bucket and triggering widespread false-positive HTTP 429 lockouts.
3. **Architectural Separation**: Application endpoint code (e.g. [`auth.py`](file:///C:/Users/Piyush148/Documents/AI%20Game/backend/app/api/auth.py#L64)) must NEVER implement custom/ad-hoc `X-Forwarded-For` parsing. Instead, the application exclusively consumes `request.client.host`. Trust evaluation is strictly the domain of the ASGI server / ASGI middleware layer.

### Verified Deployment Environments
- **Local Development Environment** (`start.bat:338`):
  - Uvicorn runs directly on loopback: `uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`.
  - Zero reverse proxy is present.
  - Forwarded headers are disabled by default. `request.client.host` evaluates strictly to the direct socket peer address (`127.0.0.1`). Any client-supplied `X-Forwarded-For` header is safely ignored.
- **Production Deployment Behind Reverse Proxy** (Nginx, AWS ALB, Cloudflare, Traefik):
  - Production Uvicorn startup must enable proxy header processing with explicit trusted upstream proxy IPs or CIDR blocks:
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.1"
    ```
  - Uvicorn's `ProxyHeadersMiddleware` verifies the connecting TCP peer IP against the configured `--forwarded-allow-ips`. Only if the peer IP matches a trusted host does it parse `X-Forwarded-For` and set `scope["client"]` to the original client IP.
  - Untrusted peers attempting to forge `X-Forwarded-For` are ignored by `ProxyHeadersMiddleware`, leaving `scope["client"]` as the peer's actual IP and preventing rate limit evasion.

## Configuration
Potential environment variables: `VITE_API_URL`, `DATABASE_URL`, `APP_ENV`, `CORS_ORIGINS`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `AUTH_JWT_SECRET`. Never expose backend secrets through Vite variables.

## Database
SQLite first. PostgreSQL is a future decision if deployment/concurrency requires it.

## AI
Google Gemini (Gemini 3 Flash Preview: `gemini-3-flash-preview`) via hosted AI provider abstraction per ADR-006. Zero local LLM dependencies.

## Hackathon principle
Prefer one frontend and one backend deployment rather than multiple infrastructure services.

