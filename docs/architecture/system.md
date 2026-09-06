# 04 — System Architecture

## Architectural Style

**Backend:** FastAPI modular monolith with SQLAlchemy, Pydantic, SQLite, and Alembic.

**Frontend:** React/Vite/Tailwind application with embedded Phaser runtime.

## System View

```text
React Frontend
     │
     ├── REST
     └── SSE
     │
     ▼
FastAPI Modular API
     │
     ├── Auth / Ownership
     ├── Project / Version Service ───► SQLite
     ├── Build Service ───────────────► BuildJob / BuildLog
     │         │
     │         └──► AI Provider ─────► Hosted LLM
     │                    │
     │                    ▼
     │             GameDesignSpec + GameDSL
     │                    │
     │                    ▼
     │             Schema + Quality Validation
     │                    │
     │                    ▼
     │             Phaser Runtime/Compiler
     │
     ├── Discovery Service ───────────► FAISS + lexical index
     │                                     │
     │                                     └── optional IGDB enrichment
     │
     ├── Playtest / Critique
     └── Creator Progression / Game DNA
```

## System Boundaries

### Frontend

Responsible for:

- Presentation
- User input
- UI state
- Navigation
- Phaser canvas embedding
- Runtime controls
- Telemetry emission

### Backend

Responsible for:

- Persistent state
- Authentication/authorization
- Ownership
- Build orchestration
- AI provider access
- Schema validation
- Gameplay quality validation
- Project/version lifecycle
- Playtest persistence
- AI critique
- Progression
- Discovery/personalization

## Generation Boundary

```text
Natural language
      ↓
GameDesignSpec
      ↓
GameDSL
      ↓
Schema validation
      ↓
Gameplay quality validation
      ↓
Deterministic normalization/repair
      ↓
Phaser-compatible artifact/runtime
```

The browser never executes arbitrary LLM-generated code.

## Versioning Boundary

`Project` represents the current working identity/state.

`ProjectVersion` represents an immutable historical snapshot.

Approved remix/improvement operations create a new version.

Historical versions must not be mutated to represent newer behavior.

## Discovery Boundary

Discovery retrieval and ranking are separate from generation.

Discovery should remain functional even when the hosted LLM is unavailable unless a specific feature explicitly depends on LLM inference.

Hard constraints remain authoritative over ranking/personalization.

## Operational Boundary

The current runtime uses process-local SSE event delivery and process-local rate limiting.

This creates a deliberate single-application-worker deployment boundary.

Horizontal scaling requires a future architecture decision covering distributed event delivery, distributed rate limiting, and a database suitable for concurrent multi-worker deployment.

## Health

The current `/api/health` endpoint is a liveness probe.

It must not be interpreted as proof that the database, AI provider, FAISS index, or other dependencies are healthy.

A future readiness/dependency-health model should be introduced only with clear semantics.

## Design Rule

Keep the architecture boring where possible.

Add infrastructure only when workload, reliability, security, organizational ownership, or operational requirements make the added complexity worthwhile.
