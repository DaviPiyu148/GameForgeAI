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
Development: `uvicorn app.main:app --reload`.

## Configuration
Potential environment variables: `VITE_API_URL`, `DATABASE_URL`, `APP_ENV`, `CORS_ORIGINS`, `GEMINI_API_KEY`, `GEMINI_MODEL`. Never expose backend secrets through Vite variables.

## Database
SQLite first. PostgreSQL is a future decision if deployment/concurrency requires it.

## AI
Google Gemini (Gemma 4 31B: `gemma-4-31b-it`) via hosted AI provider abstraction per ADR-006. Zero local LLM dependencies.

## Hackathon principle
Prefer one frontend and one backend deployment rather than multiple infrastructure services.
