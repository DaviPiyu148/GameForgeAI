# GameForge AI

GameForge AI is an AI-powered game discovery and game-prototyping platform. Users describe the game they want in natural language; the intended system understands intent, discovers existing games, and can turn unmatched ideas into validated playable browser prototypes.

## Current State

Frontend prototype complete under the agreed scope. Backend and AI are not yet implemented. Current frontend stack: React + TypeScript + Vite + Tailwind CSS + HashRouter + React Context + localStorage.

## Seven Primary Routes
`#/`, `#/discover/no-matches`, `#/build`, `#/status/success`, `#/status/error`, `#/dashboard`, `#/profile`.

## Future Architecture
```text
Browser / React
      | REST + SSE
      v
FastAPI modular monolith
  | Project / Build / Discovery services
  + SQLite
  + Hosted AI Provider (Google Gemini)
  + Sentence Transformers / FAISS
  + Game DSL validation
          |
          v
       Phaser
```

## Setup (New Machine)

See **[SETUP.md](./SETUP.md)** for the complete step-by-step guide to get the project running on any PC, including:
- Python venv + backend dependencies
- Gemini API key configuration
- Database migrations
- Discovery index download and build
- Frontend npm install
- Running via `start.bat` or manual commands

## Development

**Frontend** (inside `gameforge-ai/`):
```bash
npm install        # first time only
npm run dev        # dev server on :5173
npx tsc --noEmit  # type-check
npm run build      # production build
npm run lint       # lint
```

**Backend** (inside `backend/`, with `.venv` active):
```bash
pip install -r requirements.txt   # first time only
python -m alembic upgrade head    # apply migrations
python -m uvicorn app.main:app --reload --port 8000
pytest -v                         # run tests
```

## Documentation
Read `AGENTS.md` first, then the documents in `docs/`. Accepted architectural decisions live in `decisions/`.

## Security Boundary
LLM output must become structured Game DSL, be validated, and only then be rendered by a controlled runtime. Never execute arbitrary model-generated JavaScript.
