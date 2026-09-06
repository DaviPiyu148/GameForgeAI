# GameForge AI — Backend

FastAPI modular monolith backend for GameForge AI. Fully implemented and running — not a phase-in-progress skeleton.

## Current State

Real AI game generation (Google Gemini), a hybrid FAISS + lexical Discovery engine, JWT + Argon2 authentication with per-user ownership, Game Blueprint + Remix, Creator Progression (XP/levels/milestones), Game DNA behavioral personalization, multi-level generation with bounded boss/finale support, and a generalized Open World system are all implemented and covered by the backend test suite (430 tests passing at the time of writing — run `pytest -v` for the current count, don't trust a hardcoded number in this doc).

Key capabilities:
- **Phaser 3.88.2 runtime compatibility**: `RuntimeCompatibilityValidator` checks archetype boundaries, entity/rule capacity, and coordinates before a DSL is ever handed to the frontend.
- **Deterministic Mulberry32 PRNG**: seeded generation for 100% reproducible prototype runs.
- **Safe allowlisted rule engine**: deterministic trigger-to-action interpretation — no `eval()`, no dynamic JavaScript strings, ever.
- **Structured AI generation pipeline**: `GameDesignSpec` → `GameDSL` → Pydantic schema validation → deterministic gameplay-quality validation → bounded AI repair (max 2 retries) → SSE-streamed compile logs.
- **Hybrid Discovery**: dense semantic (FAISS) + lexical retrieval, calibrated match scoring, optional IGDB enrichment.
- **Auth & ownership**: JWT (HS256) + Argon2 password hashing; every private resource enforces per-user ownership, returning 404 (never 403) on mismatch.

---

## Directory Structure

```text
backend/
├── alembic/                  # Migration scripts and environment (single linear chain, one head)
│   └── versions/              # 12 migrations — see `alembic heads` for the current one
├── app/
│   ├── main.py                # FastAPI app, router registration, error envelope handlers
│   ├── config.py              # pydantic-settings Settings (env-driven)
│   ├── dependencies.py        # Shared FastAPI dependencies (get_db, get_current_user)
│   ├── ai/                    # Provider abstraction (Gemini primary, Groq fallback) & prompts
│   ├── auth/                  # Password hashing, JWT tokens, rate limiting
│   ├── generation/            # GameDSL/GameDesignSpec/OpenWorld models, structural + gameplay-
│   │                           # quality validators, reachability, scale tiers, blueprint derivation
│   ├── runtime/                # Runtime compatibility validator & metadata generation
│   ├── search/                 # Discovery: catalog, embedder, FAISS index, lexical index,
│   │                           # query parser, ranker
│   ├── api/                    # Route handlers: auth, projects, builds, discovery,
│   │                           # saved_discoveries, profile, health
│   ├── schemas/                 # Pydantic request/response schemas
│   ├── models/                  # SQLAlchemy ORM models (9: User, Project, ProjectVersion,
│   │                           # BuildJob, BuildLog, SavedDiscovery, PlaytestSession,
│   │                           # UserProgress/XPEvent/UserMilestone, UserGenrePreference)
│   ├── repositories/             # Data access layer
│   ├── services/                 # Business logic (Project/Build/GameGeneration/Discovery/
│   │                           # Auth/Avatar/Preference/Progression/SavedDiscovery services)
│   └── db/                      # SQLAlchemy engine & session management
├── data/                      # Discovery dataset & processed artifacts (raw/processed git-ignored)
├── scripts/                   # Offline setup & research scripts (bootstrap/, maintenance/, evaluation/, research/)
├── tests/                     # pytest regression suite (scoped via pytest.ini's `testpaths = tests`)
├── .env.example
├── alembic.ini
├── pytest.ini
├── README.md
└── requirements.txt
```

---

## Setup & Installation

### 1. Create and Activate Virtual Environment

**Windows (PowerShell):**
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment Configuration

```bash
cp .env.example .env
```

Then set `GEMINI_API_KEY` and `AUTH_JWT_SECRET` — the app refuses to start without a real `AUTH_JWT_SECRET`. See `.env.example` for every configurable field (including optional IGDB enrichment and Groq fallback provider settings).

### 4. Apply Database Migrations

```bash
alembic upgrade head
```

### 5. Ingest Catalog & Build Discovery Index

```bash
python scripts/bootstrap/ingest_catalog.py
python scripts/bootstrap/build_index.py --max-records 20000
```

See the repo-root `SETUP.md` for the full first-time dataset download instructions.

---

## Running the Development Server

```bash
uvicorn app.main:app --reload --port 8000
```

- API Base: `http://127.0.0.1:8000`
- Interactive Swagger UI: `http://127.0.0.1:8000/docs`
- Health Endpoint: `GET /api/health`

## API Endpoints

Full contract with request/response shapes: `docs/08-API-CONTRACT.md`. Router-level summary:

- `api/auth.py` — registration, login, profile (`/me`), avatar upload/delete/serve.
- `api/projects.py` — project CRUD, playtests, AI playtest analysis, improvements, blueprint, remix, version history.
- `api/builds.py` — async build submission, status/logs polling, SSE token issuance, live SSE event stream, cancellation.
- `api/discovery.py` — hybrid search, similar games, more-like-this, build-inspiration extraction.
- `api/saved_discoveries.py` — user-scoped bookmarks.
- `api/profile.py` — XP/level progression status, behavioral genre preferences.
- `api/health.py` — health probe (no auth, no dependency checks by design).

---

## Running Tests

```bash
pytest -v
```

`pytest.ini` scopes discovery to `tests/` only (`testpaths = tests`) — the historical R&D/evaluation scripts in `scripts/` that happen to be named `test_*.py` are intentionally not part of this suite.

---

## Explicitly Not Yet Implemented

- Production deployment hardening, observability, and rate-limit tuning beyond the current in-process sliding-window limiter (single-worker assumption — see `docs/06-BACKEND-ARCHITECTURE.md`).
- An "AI Game Director" adaptive-difficulty/narrative layer (future phase — not started).
- Monetization / bring-your-own-key (BYOK) provider selection (future phase — not started).
