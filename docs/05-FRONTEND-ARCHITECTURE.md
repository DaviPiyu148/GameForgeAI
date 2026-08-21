# 05 — Frontend Architecture

## Current Truth
The frontend is integrated with the real backend API service layer (FastAPI, SQLite, SSE, Discovery, and Phaser runtime).

## Routes
Exactly seven: `#/`, `#/discover/no-matches`, `#/build`, `#/status/success`, `#/status/error`, `#/dashboard`, `#/profile`.

## State Ownership & Architecture
`AppContext` provides state management across the 7 primary routes:
- **`myGames`**: Backend authoritative; hydrated on mount via `GET /api/projects` and updated when a build completes.
- **`currentPrompt`**: Ephemeral / local draft in `localStorage['gameforge_ai_state']`.
- **`currentBuildParams`**: Ephemeral / local draft in `localStorage['gameforge_ai_state']`.
- **`savedDiscoveries`**: Local state in `localStorage['gameforge_ai_state']` (deferred to B7 for backend bookmarking).
- **`currentUser`**: Local mock user (deferred to B7 for authentication).
- **`buildStatus`**: Backend authoritative during active builds (`IDLE`, `COMPILING`, `SUCCESS`, `ERROR`).
- **`compilerLogs`**: Backend SSE authoritative (`GET /api/builds/{build_id}/events`).

## API Service Layer (`src/services/`)
- **`api.ts`**: Centralized HTTP client wrapper handling `fetch`, `/api` dev proxy, JSON parsing, and normalized error responses (`ApiError`).
- **`projects.ts`**: `getProjects()`, `getProject(id)`, `updateProject(id, data)`.
- **`builds.ts`**: `createBuild(prompt, params)`, `getBuild(id)`, `getBuildLogs(id)`, `subscribeBuildEvents(id, handlers)` via standard `EventSource`.
- **`discovery.ts`**: `searchGames(prompt, limit, filters)`.

## Prototype Runtime Integration
`PrototypeModal` accepts `project?: GameProject` and extracts `project.gameDsl` and `project.runtimeMetadata.seed` directly into `<PhaserCanvas gameDsl={...} seed={...} />`. The parent layer feeds the validated DSL snapshot without arbitrary script execution or runtime fetch calls.
