# ADR-004 — Backend-Owned Build Jobs

**Status:** Accepted

## Decision
Builds are backend-owned asynchronous jobs. `POST /api/builds` creates the job; the backend runs the pipeline, streams logs through SSE, persists the successful project, and reports terminal status.

## Initial execution
FastAPI-compatible async/background execution. Do not add Celery/Redis initially.

## Consequence
The browser is not responsible for declaring server-side success or creating the project after success.

## Historical Exception (SUPERSEDED — resolved as of Phase B2)

*The paragraphs below are preserved as historical decision record. They describe a temporary state that no longer exists — the frontend now calls the real backend-owned build pipeline this ADR describes (`POST /api/builds` → SSE → project persistence). See `docs/05-FRONTEND-ARCHITECTURE.md` and `docs/08-API-CONTRACT.md` for the current, real integration.*

### Original text (historical)
During the completed frontend prototype phases F0–F5, the frontend mock `compileProject()` temporarily creates `GameProject` objects locally and stores them in React Context/localStorage.

This is intentional temporary behavior.

It MUST be removed/replaced during backend phase B2 when backend-owned build jobs become active.

This exception does NOT change the architectural decision.

