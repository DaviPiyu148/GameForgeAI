# GameForge AI — Full-Stack Operational Health Audit V1

**Date:** 2026-08-24
**Scope:** Can a fresh user clone the repo, run `start.bat`, open the app, and use it without hidden failures, broken connections, request loops, or silent backend failures?
**Method:** `start.bat` was actually executed (multiple full clean-start and restart cycles) via `Start-Process` + live health polling, not just read. All API/auth/discovery/build/SSE claims below were exercised with real HTTP requests (curl) against the live running stack, not inferred from source alone.

## Tooling limitation (read this before the findings)

No browser-automation tool was available in this environment. Phases requiring literal DevTools/Network-panel/Phaser-canvas inspection (frontend page rendering, click-through UI flows, runtime FPS/console errors) were **not** executed and are marked **NOT VERIFIED (browser-level)** below — see FS-014. Everything else in this report — start.bat execution, process/port state, backend logs, database, and all API/SSE traffic — was independently exercised against the live stack, not just read from source.

---

# Executive Summary

The application **does** start, connect, persist data, and complete a real AI generation → SSE → project → restart cycle correctly — but three **CRITICAL** defects would have broken that experience for a real fresh user, and were only found by actually running the system rather than reading it:

1. `start.bat`'s port-clearing step was attempting to force-kill arbitrary/stale PIDs — including the Windows `System` process (PID 4) — on every single run. This is the direct, confirmed cause of a black-screen incident observed live during this audit.
2. The Discovery search feature's first-ever request after any backend start freezes the **entire application** (every endpoint, including `/api/health`) for 20-56 seconds, because a slow one-time catalog/model load runs synchronously on the async event loop. This also explains a previously-unexplained `502 Bad Gateway`/`ECONNRESET` seen in an earlier session's browser log.
3. Build SSE streams silently drop log events under real timing conditions — proven by a live open-world generation where 11 of 28 persisted log lines never reached the connected client, due to an event-ordering race in the broadcaster.

All three, plus 6 further confirmed defects (2 HIGH, 3 MEDIUM/LOW, 1 introduced-and-caught-within-session), were root-caused, fixed at the smallest correct layer, and verified — either live against the running stack or via new/extended regression tests where live re-verification was blocked by real external Gemini API instability. Full backend suite: **328 passed, 0 failed**. Frontend: `tsc` 0 errors, `oxlint` 0 errors, production build succeeds.

**Verdict: PASS WITH MINOR ISSUES** (see Final Verdict section — the "minor" issues remaining are documentation drift and un-verifiable browser-level layers, not functional defects).

---

# Start.bat

**Executed, not just read**, across two full clean-start cycles plus numerous restarts during fix verification.

- **6-step preflight** (venv check → package smoke-test → `.env` presence/placeholder checks → Node/npm + `node_modules` → `alembic upgrade head` → port clearance) all behave correctly: clear errors, no false "started successfully," no silent continuation past a real failure.
- **Path handling**: the repo path (`C:\Users\Piyush148\Documents\AI Game`) contains a space, and every path in `start.bat` is correctly double-quoted — confirmed working, not just inspected.
- **Process ownership**: launches exactly one backend (`cmd /k` → uvicorn `--reload`) and one frontend (`cmd /k` → `npm run dev`) window, plus opens the browser. Verified via full process-tree inspection (parent/child PIDs) after a clean run — no duplicate reloaders, no orphans. One process that looked like a stray (`cmd.exe`, PID 11312) turned out to be Chrome's own AdGuard extension helper, correctly parented under the Chrome window `start.bat` itself opened — not a leak.
- **Startup time**: backend + frontend both healthy/ready in ~20 seconds from launch across both clean-start cycles.
- **CRITICAL defect found and fixed** — see FS-001 below.

---

# Backend

- FastAPI `lifespan` orphan-build reconciliation, structured `RequestValidationError`/`HTTPException` envelopes, and router registration all verified correct via live requests and log inspection.
- `GET /api/health` is a pure `{"status": "ok", "service": "gameforge-api"}` with **zero dependency checks** (no DB ping, no Gemini reachability, no FAISS readiness). This is not itself a defect — the audit brief explicitly says not to fabricate false depth here — but it means `start.bat`'s health gate, and anyone else polling this endpoint, gets no signal about whether the app can actually serve real requests. Documented as INFO (FS-013).
- **CRITICAL defect found and fixed** — see FS-002 below (this is also a backend defect, filed under API/Performance for cross-reference).

---

# Database

- `alembic current` / `alembic heads`: single head throughout the audit, including after the new migration this audit added (`bc9ae398f146`, chained cleanly onto the prior head `b3c4d5e6f7a8`).
- **Read**: health, `/auth/me`, `/profile/progress`, `/projects`, `/saved-discoveries` all verified returning correct live data.
- **Write + persistence**: registered a real user, saved a real discovery, created a real project via a real Gemini generation — then restarted the backend **twice** and re-verified all three were intact after each restart (SQLite file persistence confirmed, not assumed).
- **Transactions**: `POST /api/saved-discoveries` correctly returns `409 ALREADY_SAVED` on a duplicate without a partial write; build → project creation is wrapped correctly (verified no orphan projects on a build error path in existing test coverage, re-run clean).
- **Schema gap found and fixed** — see FS-006 below.

---

# API

## Endpoint inventory (exercised live where marked ✅; code-reviewed otherwise)

| Subsystem | Endpoint | Auth | Tested |
|---|---|---|---|
| Health | `GET /api/health` | none | ✅ |
| Auth | `POST /api/auth/register` | none | ✅ (201, real JWT) |
| Auth | `POST /api/auth/login` | none | ✅ |
| Auth | `GET /api/auth/me` | required | ✅ |
| Auth | `POST/DELETE/GET /api/auth/avatar*` | required | code-reviewed |
| Profile | `GET /api/profile/progress`, `/preferences` | required | ✅ progress |
| Discovery | `POST /api/discovery/search` | optional | ✅ (incl. cold-start fix) |
| Discovery | `GET /similar/{id}`, `POST /more-like-this`, `GET /build-inspiration/{id}` | optional | code-reviewed + fixed for same cold-start issue |
| Saved Discoveries | `GET/POST/DELETE /api/saved-discoveries` | required | ✅ save, list, duplicate-409, delete-path reviewed |
| Projects | `GET/PATCH /api/projects[/{id}]` | required | ✅ list, PATCH (incl. new scale/worldMode regression test) |
| Projects | playtests, blueprint, remix, versions | required | code-reviewed |
| Builds | `POST /api/builds`, `GET /{id}`, `/logs`, `/cancel` | required | ✅ create (202 fast-return), status, logs |
| Builds | `POST /{id}/sse-token`, `GET /{id}/events` | required | ✅ live SSE, incl. the fix for FS-003 |

## Contract verification

- snake_case/camelCase aliasing (`artDensity`, `worldMode`, etc.) verified working correctly via direct schema tests and live requests.
- Error responses: missing auth → 401 structured envelope; nonexistent/foreign resource → 404 (never a raw 403, confirming the documented IDOR policy); malformed payload → 422 with field-level detail; duplicate action → 409. No raw tracebacks observed anywhere.
- **Found and fixed**: `/api/saved-discoveries` validation errors were mislabeled with the generic `PROJECT_VALIDATION_FAILED` code (FS-008, LOW).
- **Found and fixed**: `Project.parameters.scale`/`worldMode` never actually persisted or round-tripped correctly (FS-006, HIGH).

## Latency observations (Phase 33 framing: NORMAL / NOTICEABLE / PROBLEMATIC / CRITICAL)

| Endpoint | Observed | Classification |
|---|---|---|
| `/api/health` | 10-40ms | NORMAL |
| `/api/auth/login`, `/auth/me` | <50ms | NORMAL |
| `/api/discovery/search` (warm) | ~0.3-0.6s | NORMAL |
| `/api/discovery/search` (cold, pre-fix) | 60s+ and froze the whole app | CRITICAL — fixed |
| `/api/discovery/search` (cold, post-fix) | 20-26s, but app stays responsive | NOTICEABLE, acceptable (one-time cost, doesn't block other users) |
| `POST /api/builds` | <0.7s to 202 | NORMAL (correctly async — doesn't block on generation) |
| Gemini generation itself | 5-56s depending on repair-loop attempts | Legitimate AI inference cost, not flagged as a bug per the audit's own guidance |

---

# Frontend ↔ Backend

- **Base URL**: `VITE_API_URL` env var with `/api` relative-path fallback, proxied by Vite in dev — confirmed correct.
- **Found and fixed**: Vite's dev server bound only to `::1` (IPv6), unreachable at the `127.0.0.1` URL `start.bat` actually opens (FS-004, HIGH).
- **Found and fixed**: backend `CORS_ORIGINS` default didn't include `http://127.0.0.1:5173`, the real serving origin — reproduced live as a `400 Disallowed CORS origin` on a genuine preflight request, currently masked in normal dev use only because Vite's proxy keeps API calls same-origin (FS-005, HIGH).
- No duplicate-request loops observed in the flows exercised (register→login→me, discovery search, save, build creation, SSE) — each action produced exactly the expected number of backend log lines.

---

# SSE

- Token flow verified: `POST /builds/{id}/sse-token` (90s-scoped credential, distinct token type, never the long-lived JWT) → `GET /builds/{id}/events?sse_token=...` → correct `text/event-stream` framing, ordered `sequence` numbers, correct terminal-event handling (`SUCCESS`/`ERROR`/`CANCELLED` closes the stream).
- **CRITICAL defect found and fixed**: live event loss under real timing — see FS-003.
- Reconnect/replay path (`stream_events()`'s DB-replay-then-live-tail design) verified structurally sound after the fix; no duplicate events observed in any successful capture.

---

# Phaser Runtime / Open World / AI Analysis / Telemetry

**NOT VERIFIED at the browser/canvas level** — see the tooling-limitation note at the top of this report and FS-014.

What **was** verified: a real open-world generation (Gemini 3 Flash, the exact prompt specified in the audit brief) produced a structurally correct `OpenWorldDef` — 3 regions with bidirectional connections, 2 factions, POIs, a vehicle, an activity, a threat system, and a world-time clock, all within the documented budgets (regions≤6, POIs≤25, actors≤50, vehicles≤10, factions≤5, activities≤15). The deterministic validator correctly caught and auto-repaired a real quality violation mid-generation ("Scale tier 'standard' expects at least 8 entities... has 4") — the safety/repair pipeline described in `AGENTS.md` is functioning, not just documented.

Two further live generation attempts hit genuine Gemini API instability (`MODEL_TIMEOUT` after 150s, then `HTTP 503`) — both were correctly surfaced as structured `ERROR` builds with accurate error codes, not silently swallowed or misreported as success. This is external provider variance, not an application defect, per the audit's own guidance not to flag AI latency as a bug.

---

# Performance

- The one genuinely user-visible performance defect found (Discovery cold-start freezing the whole app) is documented above and fixed.
- Frontend production bundle is a single 1.65MB JS chunk (440KB gzip), and the Material Symbols icon font alone is 3.96MB — Vite's own build output already warns about this. Not fixed: this is a code-splitting/asset-scope decision, not a bug, and the audit brief explicitly says not to chase this kind of thing without a concrete user-visible complaint (FS-015, LOW/INFO).

---

# Shutdown / Restart

Executed for real, twice:

`start.bat` → verified running → stopped all processes → confirmed both ports released → `start.bat` again → confirmed healthy again → confirmed all previously-written data (user, saved discovery, project) still present. No corruption, no port collisions, no orphaned processes on either cycle.

---

# Findings Matrix

| ID | Severity | Subsystem | Reproduction | Expected | Actual | Root Cause | Fix | Regression |
|---|---|---|---|---|---|---|---|---|
| FS-001 | CRITICAL | start.bat | Run `start.bat` and observe step `[6/6]` output | Only actual stale python/node listeners on 8000/5173 get killed | Dozens of taskkill attempts against unrelated/stale PIDs, including PID 4 (`System`) — matches an observed black-screen incident | Unanchored `netstat \| findstr ":8000 .*LISTENING"` matched far more than intended, with no PID-ownership or protected-PID check | Replaced with `Get-NetTCPConnection -LocalPort <port> -State Listen`, filtered to verified `python.exe`/`node.exe` owners, PID>4 guard | Manually verified via isolated dummy-server test (exact detection + kill), then twice live via full `start.bat` clean-start cycles |
| FS-002 | CRITICAL | performance / backend | Restart backend fresh, immediately `POST /api/discovery/search` | Search completes without affecting other requests | Entire app (incl. `/api/health`) unresponsive for the full 20-56s cold-load duration — 4/4 concurrent 10s health-check timeouts observed | `CatalogManager`/FAISS/embedder lazy singletons loaded synchronously inside `async def` routes, blocking the single-threaded event loop | Offloaded via `asyncio.to_thread`; also eagerly warmed in a background task at app startup | Live concurrency test: 8/8 health checks stayed instant (<0.35s) during a 24.8s cold load, before/after compared |
| FS-003 | CRITICAL | SSE | Live open-world build; connect to SSE while build is running | All persisted log events reach the client before the terminal status | 11 of 28 persisted `BuildLog` rows (repair-success, Phaser-validation logs) never reached the SSE client, though correctly in the DB | Fire-and-forget `asyncio.create_task()` broadcasts (from sync `emit_log`/`set_status` callbacks) could be overtaken by a directly-awaited terminal status broadcast, which made `stream_events()` unsubscribe before the pending log broadcasts ever ran | Made `BuildEventBroadcaster` fully synchronous (no `async`/lock needed — it never awaited anything) | New test `test_broadcaster_preserves_order_for_sync_callback_pattern`; live retest attempts blocked by real Gemini instability but unit test directly encodes the exact failure mode and passes |
| FS-004 | HIGH | frontend / startup | `curl http://127.0.0.1:5173/` after `start.bat` | 200 OK | Connection refused — Vite bound `::1` only | Vite's default `host: 'localhost'` resolves to IPv6-only on this machine (Node `dns` verbatim ordering); `start.bat` opens/reports `127.0.0.1` | Added `server.host: '127.0.0.1'` to `vite.config.ts` | Live: confirmed 200 on 127.0.0.1 after fix, both in isolation and in a full clean `start.bat` run |
| FS-005 | HIGH | CORS / configuration | CORS preflight with `Origin: http://127.0.0.1:5173` directly against backend | 200, origin allowed | `400 Disallowed CORS origin` | `CORS_ORIGINS` default only listed `http://localhost:5173`, not the `127.0.0.1` origin `start.bat`/Vite actually serve from | Default now includes both loopback origins; `.env.example` updated to match | Live: preflight now returns 200 with correct `access-control-allow-origin` |
| FS-006 | HIGH | database / API contract | Create an `open_world` build, inspect the resulting Project's `parameters.worldMode` | `"open_world"` | `"linear"` (schema default) despite the build's own generated `game_dsl` correctly containing full open-world data | `Project` ORM model had **no** `scale`/`world_mode` columns at all; 3 separate call sites (build-completion `BuildParams` reconstruction, `to_response`, PATCH update) silently discarded whatever was requested | Added migration `bc9ae398f146` (2 new columns) + wired through `create_project`/`update_project`/`to_response` | 2 new regression tests (build-creation path, PATCH path), both passing |
| FS-007 | MEDIUM | tests | `pytest tests/test_multilingual_catalog.py` on a memory-constrained machine (this one: 7.7GB total) | Passes reliably | Spurious `MemoryError` decoding the ~450MB catalog file | Test used naive `json.load()` on the whole file instead of the app's own streaming `CatalogManager` loader | Switched the test to `CatalogManager` (also improves fidelity to the real production load path) | Reran in isolation (8.2s, passed) and inside the full 328-test suite |
| FS-008 | LOW | API contract | Send an invalid `POST /api/saved-discoveries` payload | `SAVED_DISCOVERY_VALIDATION_FAILED` | `PROJECT_VALIDATION_FAILED` (fallback default) | No dedicated branch for `/saved-discoveries` in the path-based error-code selector | Added the branch | Live: confirmed correct code returned after fix |
| FS-009 | MEDIUM | backend (self-introduced, caught same session) | App shutdown / TestClient teardown while the FS-002 warm-up task is still running | Clean shutdown | `Exception in callback` — `CancelledError` raised from `Task.exception()` | `Task.exception()` raises rather than returns for a cancelled task; the done-callback added for FS-002 didn't check `cancelled()` first | Added the `cancelled()` guard | Caught by, and fixed via, the very next full-suite run |
| FS-010 | LOW / INFO | documentation | Compare `docs/06-BACKEND-ARCHITECTURE.md`'s migration list to `alembic heads` | In sync | Doc stops 4 migrations short of actual head | Doc drift, not updated after Phases 4-6 | Not fixed (doc-only, out of audit's code-fix scope) | — |
| FS-011 | LOW / INFO | documentation | `SETUP.md` "Verify Everything Works" table | Matches current test count | Says "61 tests passing"; actual is 328 | Doc drift | Not fixed | — |
| FS-012 | LOW / INFO | documentation | Compare `docs/08-API-CONTRACT.md` to actual routers | All endpoints documented | Missing `builds/cancel`, `auth/avatar*`, `profile/*`, `projects/.../playtests/{id}` | Doc drift | Not fixed | — |
| FS-013 | INFO | health/config | `GET /api/health` | — | Confirms process-alive only; no DB/AI/FAISS check | By design, not a defect | Documented per the audit's own instruction not to overstate health | — |
| FS-014 | INFO | tooling | Attempt any DevTools/canvas-level check | Browser tool available | None available in this environment | Environment limitation | N/A — documented as NOT VERIFIED throughout this report | — |
| FS-015 | LOW / INFO | performance / frontend | `npm run build` output | — | 1.65MB single JS chunk, 3.96MB icon font, Vite's own size warning | No code-splitting configured | Not fixed — scope/feature decision, not a defect | — |
| FS-016 | INFO | architecture | Code review of `BuildEventBroadcaster`, `SlidingWindowRateLimiter` | — | Both are in-process, single-worker-only by design | Correct given `start.bat` launches exactly one uvicorn worker; pre-existing, documented risk if ever run with `--workers > 1` | Not fixed (not a defect under current deployment) | — |
| FS-017 | INFO | documentation | Look for `gameforge-ai/.env.example` | Present | Absent — only `VITE_API_URL` inferable from source | Doc gap | Not fixed | — |

---

# Fixes (summary)

Nine confirmed defects fixed at the smallest correct layer, each independently verified (live re-test where an external dependency didn't block it; a new or extended regression test otherwise):

1. `start.bat` — precise, safe port clearing.
2. `backend/app/services/discovery_service.py`, `backend/app/api/discovery.py`, `backend/app/main.py` — discovery cold-start no longer freezes the app; warmed at startup.
3. `gameforge-ai/vite.config.ts` — bind to `127.0.0.1`.
4. `backend/app/config.py`, `backend/.env.example` — correct CORS default.
5. `backend/app/services/build_service.py` — synchronous SSE broadcaster (fixes real event loss).
6. `backend/app/models/project.py`, `backend/app/services/project_service.py`, `backend/app/services/build_service.py`, migration `bc9ae398f146` — `scale`/`world_mode` now persist correctly.
7. `backend/app/main.py` — fixed a bug introduced by fix #2, caught by the suite before this report was written.
8. `backend/app/main.py` — correct error code for saved-discoveries validation.
9. `backend/tests/test_multilingual_catalog.py` — no longer spuriously OOMs on memory-constrained machines.

# Regression

- Full backend suite: **328 passed, 0 failed** (was 327 passed / 1 spurious-failed at audit start; +1 new test, 2 existing tests extended with new assertions).
- `npx tsc --noEmit`: 0 errors.
- `npx oxlint`: 0 errors, 0 warnings.
- `npm run build`: succeeds.
- `alembic current` / `alembic heads`: single head (`bc9ae398f146`).
- Two full `start.bat` clean-start/restart cycles: all green, data persisted, ports released cleanly both times.

# Remaining Risks

- **Browser/Phaser/telemetry/AI-analysis layers were not verified** in this session (no browser tool available). The generated data these layers consume was independently verified correct; the layers themselves were not exercised.
- SSE broadcaster and the in-process rate limiter remain single-worker-only by architecture — correct today, but would silently misbehave if `start.bat` (or any future deployment) were changed to launch multiple uvicorn workers.
- Documentation drift (FS-010, FS-011, FS-012) is real but cosmetic — none of it caused a functional failure during this audit, only confusion for anyone trusting the stale numbers/lists.
- Discovery's first-search latency is now non-blocking but still ~20-26s on a cold cache; acceptable per the audit's own performance framing, but worth knowing if a future change makes the catalog file larger.

# Final Verdict

| Area | Status |
|---|---|
| AUTOMATED VERIFIED | Backend suite (328/328), `tsc`, `oxlint`, `npm run build`, `alembic current`/`heads` |
| MANUAL SYSTEM VERIFIED | `start.bat` (2 clean-start + 2 restart cycles), process lifecycle, port release, live AI generation, live SSE, live auth/discovery/build/persistence via direct HTTP |
| BROWSER VERIFIED | None — no browser tool available this session |
| NOT VERIFIED | Phaser canvas rendering/input/cleanup, Playtest UI, Profile/Game DNA pages, AI-analysis UI, any visual glitch or DOM-level check |

**PASS WITH MINOR ISSUES.** Three CRITICAL defects were found and fixed that would have materially broken the experience for a real fresh user (one of them — the black screen — was directly observed happening); the remaining open items are either external-provider variance, documentation drift, or an environment limitation on this audit's own tooling, not application defects.
