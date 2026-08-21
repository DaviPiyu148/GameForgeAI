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

## Development
```bash
npm install
npm run dev
npx tsc --noEmit
npm run build
npm run lint
```

## Documentation
Read `AGENTS.md` first, then the documents in `docs/`. Accepted architectural decisions live in `decisions/`.

## Security Boundary
LLM output must become structured Game DSL, be validated, and only then be rendered by a controlled runtime. Never execute arbitrary model-generated JavaScript.
