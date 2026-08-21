# GameForge AI — Backend

This directory contains the FastAPI modular monolith backend for GameForge AI.

## Current Phase: B5 — Phaser Playable Prototypes (Complete)

Phase B5 establishes the deterministic Phaser 3.88.2 Arcade Physics runtime, backend runtime compatibility validation engine, deterministic runtime metadata persistence, and interactive prototype modal viewer.

Key capabilities established:
- **Phaser 3.88.2 Runtime**: Built-in Arcade Physics handling 2D collisions, locomotion, and physics without arbitrary code execution.
- **Procedural Vector Textures**: Clean vector-styled canvas rendering for player avatars, enemy drones, collectible gems, plasma projectiles, solid platforms, hazard spikes, and victory exit portals with zero external CDN/network assets.
- **Deterministic Mulberry32 PRNG**: Seeded random generation to ensure 100% reproducible prototype runs.
- **Safe Allowlisted Rule Engine**: Deterministic trigger-to-action interpretation (`add_score`, `damage_player`, `heal_player`, `win_game`, `lose_game`, `speed_boost`, `spawn_entity`) prohibiting `eval()` or dynamic JavaScript strings.
- **Backend Compatibility Validator**: `RuntimeCompatibilityValidator` checks archetype boundaries, entity capacity (<=30), rule capacity (<=20), and coordinates.
- **Deterministic Runtime Metadata**: `Project.runtime_metadata` persists engine versions and seeds (`rendererVersion`, `phaserVersion`, `dslSchemaVersion`, `seed`).
- **Comprehensive Test Suite**: 61 unit and integration tests passing covering runtime compatibility, metadata, preprocessing, embedder, FAISS index, ranker, API endpoints, builds, DSL validation, and projects.

---

## Directory Structure

```
backend/
├── alembic/                  # Alembic migration scripts and environment
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 57a6f0ac8836_create_projects_table.py
│       ├── 1fe395775e52_create_build_jobs_and_build_logs_tables.py
│       ├── efcb82ffe8c4_add_game_dsl_column_to_build_jobs_table.py
│       └── 7b8c9d0e1f2a_add_game_dsl_and_runtime_metadata_to_projects_table.py
├── app/                      # Application modular structure
│   ├── __init__.py
│   ├── main.py               # FastAPI application entry point & router registration
│   ├── config.py             # Settings using pydantic-settings
│   ├── dependencies.py       # Shared FastAPI dependencies (get_db)
│   ├── ai/                   # AI Provider abstraction & prompts
│   │   ├── __init__.py
│   │   ├── provider.py       # AIProvider abstract class & AIError taxonomy
│   │   ├── hosted_provider.py # GeminiProvider (gemma-4-31b-it), GroqProvider, AIProviderRouter
│   │   └── prompts.py        # System, generation, and repair prompt templates
│   ├── generation/           # Game DSL schemas & validation
│   │   ├── __init__.py
│   │   ├── dsl_models.py     # GameDSL Pydantic models
│   │   └── validator.py      # validate_game_dsl function
│   ├── runtime/              # Runtime compatibility & metadata (B5)
│   │   ├── __init__.py
│   │   ├── compatibility.py  # RuntimeCompatibilityValidator
│   │   └── metadata.py       # generate_runtime_metadata
│   ├── search/               # Discovery search components (B4)
│   │   ├── __init__.py
│   │   ├── embedder.py       # QueryEmbedder (SentenceTransformer singleton)
│   │   ├── index.py          # FAISSIndexManager (IndexFlatIP vector search)
│   │   ├── catalog.py        # CatalogManager (in-memory game metadata)
│   │   └── ranker.py         # Ranker (hard filters, highlights, explanations)
│   ├── api/                  # API route handlers
│   │   ├── __init__.py
│   │   ├── health.py         # GET /api/health endpoint
│   │   ├── projects.py       # Project CRUD endpoints
│   │   ├── builds.py         # Build Job & SSE endpoints
│   │   └── discovery.py      # POST /api/discovery/search endpoint
│   ├── schemas/              # Pydantic request/response schemas
│   │   ├── __init__.py
│   │   ├── project.py        # Project & BuildParams schemas
│   │   ├── build.py          # Build job & event schemas
│   │   └── discovery.py      # DiscoverySearchRequest, Response & Result schemas
│   ├── models/               # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── project.py        # Project database model
│   │   ├── build.py          # BuildJob database model (with game_dsl)
│   │   └── build_log.py      # BuildLog database model
│   ├── repositories/         # Database access layer
│   │   ├── __init__.py
│   │   ├── project_repo.py   # ProjectRepository
│   │   └── build_repo.py     # BuildRepository
│   ├── services/             # Business logic layer
│   │   ├── __init__.py
│   │   ├── project_service.py # ProjectService
│   │   ├── build_service.py  # BuildService (worker, SSE, lifecycle)
│   │   ├── game_generation_service.py # GameGenerationService (AI + repair)
│   │   └── discovery_service.py # DiscoveryService (B4 search orchestration)
│   └── db/                   # Database engine & session management
│       ├── __init__.py
│       └── session.py        # SQLAlchemy SQLite engine & sessionmaker
├── data/                     # Discovery dataset & processed artifacts (B4)
│   ├── README.md             # Dataset provenance & download instructions
│   ├── dataset_audit.md      # Field mapping & raw table metrics
│   ├── multi_source_audit.md # Multi-source evaluation & architecture decision
│   ├── raw/                  # Downloaded CSV archives (git-ignored)
│   └── processed/            # Normalized catalog & FAISS index (git-ignored)
│       ├── games_catalog.json
│       ├── games_index.faiss
│       └── index_meta.json
├── scripts/                  # Offline processing & evaluation scripts (B4)
│   ├── ingest_catalog.py     # Ingests & joins raw CSVs into normalized catalog
│   ├── build_index.py        # Builds FAISS IndexFlatIP vector index
│   └── evaluate_discovery.py # Evaluates 15 test queries against live index
├── tests/                    # Backend automated tests (56 tests)
│   ├── __init__.py
│   ├── fixtures/
│   │   └── discovery_queries.json # 15 test queries for evaluation
│   ├── test_ai_provider.py
│   ├── test_dsl.py
│   ├── test_game_generation.py
│   ├── test_health.py
│   ├── test_projects.py
│   ├── test_builds.py
│   ├── test_discovery_preprocessing.py
│   ├── test_discovery_embedder.py
│   ├── test_discovery_faiss.py
│   ├── test_discovery_ranker.py
│   └── test_discovery_api.py
├── .env.example
├── .gitignore
├── alembic.ini
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

### 4. Apply Database Migrations

```bash
alembic upgrade head
```

### 5. Ingest Catalog & Build Discovery Index

```bash
python scripts/ingest_catalog.py
python scripts/build_index.py --max-records 20000
```

---

## Running the Development Server

```bash
uvicorn app.main:app --reload --port 8000
```

- API Base: `http://127.0.0.1:8000`
- Interactive Swagger UI: `http://127.0.0.1:8000/docs`
- Health Endpoint: `GET /api/health`
- Projects Endpoint: `GET /api/projects`
- Builds Endpoint: `POST /api/builds`
- Discovery Endpoint: `POST /api/discovery/search`

---

## API Endpoints

### Discovery (Implemented in B4)
- `POST /api/discovery/search` -> Offline semantic vector search with FAISS retrieval and hard filters (`prompt`, `limit`, `filters`).

### Builds (Implemented in B2 & B3)
- `POST /api/builds` -> Submit new build job (triggers AI generation; returns HTTP 202 Accepted with `build_id`)
- `GET /api/builds/{build_id}` -> Retrieve authoritative build status, project ID, error details, and `game_dsl`
- `GET /api/builds/{build_id}/logs` -> Retrieve persisted logs in ascending sequence order
- `GET /api/builds/{build_id}/events` -> Real-time Server-Sent Events (`text/event-stream`) streaming

### Projects (Implemented in B1)
- `POST /api/projects` -> Create and persist a new game project
- `GET /api/projects` -> List all projects
- `GET /api/projects/{project_id}` -> Retrieve single project by ID
- `PATCH /api/projects/{project_id}` -> Update editable fields

---

## Running Tests

```bash
pytest -v
```

---

## Scope & Functionality NOT Implemented in B5

- **B6**: React frontend integration with backend API, SSE streams, live project fetching
- **B7**: User authentication, JWT tokens, multi-user project ownership
- **B8**: Production deployment, rate limiting, monitoring
