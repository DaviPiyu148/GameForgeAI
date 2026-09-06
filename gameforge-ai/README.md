# GameForge AI — Frontend

React + TypeScript + Vite + Tailwind CSS frontend for GameForge AI. Talks to the real FastAPI backend in `../backend/` — not a mock/standalone prototype.

## Role

Renders the 7 primary routes (`#/`, `#/discover/no-matches`, `#/build`, `#/status/success`, `#/status/error`, `#/dashboard`, `#/profile`) via `react-router-dom`'s `HashRouter`, holds transient UI state in a single `AppContext` (React Context), and embeds a Phaser 3.88.2 canvas for playable prototype runs. Backend/database remain authoritative for persistent business state — see `AGENTS.md` and `docs/architecture/frontend.md`.

## Stack

React 19, TypeScript, Vite, Tailwind CSS v4, `react-router-dom` (HashRouter), React Context, Phaser 3.88.2 (Arcade Physics).

## Development Commands

```bash
npm install         # first time only
npm run dev          # dev server on :5173, proxies /api -> http://127.0.0.1:8000
npx tsc --noEmit     # type-check
npm run build         # production build
npm run lint          # oxlint
```

## API Configuration

`src/services/api.ts` calls a relative `/api` path by default, proxied to the backend by Vite's dev-server proxy (see `vite.config.ts`). Set `VITE_API_URL` to override for a non-proxied setup (e.g. a separately-hosted backend).

## Runtime Architecture Notes

- **Auth token**: stored in `localStorage`, attached as a Bearer header by `services/api.ts`; a `gameforge:auth-expired` event fires on 401 to let `AppContext` react.
- **Build SSE**: `services/builds.ts` opens an `EventSource` against a short-lived, build-scoped SSE token (never the long-lived JWT) for live compiler log streaming.
- **Phaser runtime**: `runtime/GameScene.ts` is the single source of truth for applying a level's config (background, spawn, entities, HUD) on both initial load and every level transition. Seven standalone managers (`WorldManager`, `RegionManager`, `VehicleManager`, `ActivityManager`, `FactionManager`, `ThreatManager`, `WorldEventManager`) handle Open World mode. The runtime never evaluates model-generated strings as code — DSL fields only ever select from a closed, allowlisted set of behaviors/effects.
- **Motion system**: a shared token/utility-class system in `src/styles/index.css` (motion durations, easing, glow language, toast animations) — reuse it rather than inventing new one-off animations. `prefers-reduced-motion: reduce` is respected globally.
- **Toasts**: `services/toastBus.ts` is a plain pub/sub, decoupled from `AppContext`'s state shape, rendered by `components/Shared/ToastContainer.tsx` (mounted once in `App.tsx`).

## Build / Lint / Typecheck

`npm run build` runs `tsc -b && vite build` — a failing type-check fails the build. `npm run lint` runs `oxlint` (config: `.oxlintrc.json`). Neither is optional before considering a change complete; see `AGENTS.md`'s testing rules.
