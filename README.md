# GameForge AI

GameForge AI is an AI-powered game discovery and game-prototyping platform. Users describe the game they want in natural language; the system understands intent, discovers existing games from a hybrid semantic + lexical catalog search, and turns unmatched ideas into validated, playable browser prototypes — backed by a real, structured AI generation pipeline (no arbitrary code execution).

## Current State

Full-stack, implemented and running: React/TypeScript/Vite frontend, FastAPI/SQLAlchemy/SQLite backend, real Google Gemini AI generation, hybrid FAISS + lexical discovery, and a Phaser 2D runtime. This is not a mock/prototype-only build — every feature below is real, tested, and end-to-end wired.

## Architecture

```text
Browser / React (HashRouter, React Context, Tailwind, Phaser 3.88.2)
      | REST + SSE
      v
FastAPI modular monolith
  | Auth (JWT + Argon2) / Project / Build / Discovery / Profile services
  + SQLite (Alembic-migrated)
  + Google Gemini (hosted AI provider, structured JSON output)
  + Sentence Transformers + FAISS + lexical index (hybrid Discovery Engine)
  + Game DSL schema validation + deterministic gameplay-quality checks
          |
          v
       Phaser 3.88.2 (deterministic, allowlisted rule interpreter — never eval()'d model output)
```

## Seven Primary Routes
`#/`, `#/discover/no-matches`, `#/build`, `#/status/success`, `#/status/error`, `#/dashboard`, `#/profile`.

## Current Capabilities

- **AI game generation**: natural-language prompt → structured `GameDesignSpec` → `GameDSL` (schema v3.0) → deterministic validation → gameplay-quality checks → bounded AI repair (max 2 retries) → playable Phaser prototype, streamed live over SSE.
- **Game Blueprint**: a nontechnical, allowlist-derived summary of what a generated project actually supports — never claims a capability the DSL doesn't back.
- **Remix**: apply 1-3 structured intents (more combat, harder, add levels, etc.) from a closed vocabulary to create a new immutable project version, through the same validation pipeline as fresh generation.
- **Discovery**: hybrid dense semantic (FAISS) + lexical retrieval over a normalized Steam catalog, calibrated match scoring, explainable results, and optional IGDB enrichment.
- **Game DNA**: implicit behavioral genre-affinity tracking (search/save/build/play) that informs — never overrides — future generation and remix prompts.
- **Creator Progression**: server-authoritative XP, creator levels, and unlockable milestones.
- **Multi-level generation** (up to 5 levels), **bounded boss/finale encounters**, and **scale tiers** (`prototype`/`standard`/`campaign`) that flow into the generation budget.
- **Generalized Open World mode**: multi-region worlds with vehicles, factions, POIs, activities, and a threat/alert system — a general-purpose capability, not hardcoded to one genre.
- **Playtesting + AI analysis**: in-game telemetry capture, then a post-game AI critique with selectable, targeted DSL-patch recommendations.
- **Authentication & ownership**: JWT + Argon2, per-user project/build/discovery ownership with IDOR-safe 404s (never 403s).
- **UI motion system**: a cohesive cyberpunk motion/effects layer (page transitions, glow language, toast notifications, ambient effects) across the whole frontend, with `prefers-reduced-motion` respected throughout.

## Development Setup

See **[SETUP.md](./SETUP.md)** for the complete step-by-step guide, including the Python venv, Gemini API key, database migrations, and Discovery index build.

**Backend** (inside `backend/`, with `.venv` active):
```bash
pip install -r requirements.txt      # first time only
python -m alembic upgrade head       # apply migrations
python -m uvicorn app.main:app --reload --port 8000
pytest -v                            # run tests
```

**Frontend** (inside `gameforge-ai/`):
```bash
npm install         # first time only
npm run dev         # dev server on :5173
npx tsc --noEmit    # type-check
npm run build        # production build
npm run lint         # lint
```

**Required environment variables** (`backend/.env`, copy from `backend/.env.example`): `GEMINI_API_KEY` and `AUTH_JWT_SECRET` are required; everything else has a working local default. See `SETUP.md` for the full reference.

**One-click launch (Windows)**: run `start.bat` from the repo root — it verifies prerequisites, applies migrations, starts both servers, and opens the browser.

## Documentation
Read `AGENTS.md` first (the AI development constitution), then `docs/README.md` for the full documentation index. Accepted architectural decisions live in `decisions/`. `docs/15-CURRENT-STATUS.md` is the living status document — read it for what's actually shipped as of today.

## Security Boundary
LLM output must become structured Game DSL, be validated, and only then be rendered by a controlled runtime. Never execute arbitrary model-generated JavaScript. See `docs/13-SECURITY.md`.
