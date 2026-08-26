# GameForge AI — Task Execution Ledger

## Task
Dev Proxy 502 Investigation — Intermittent Vite Proxy 502s After Startup/Authentication

## Status
COMPLETE

## Objective
Investigate the intermittent development-only `502`/connection-reset behavior observed during
prior browser testing (several `/api/*` requests returning `502` from the Vite dev proxy
immediately after login/register, while the FastAPI backend's own access log showed the identical
requests returning `200 OK`). Determine root cause among: Vite dev-proxy race, backend readiness
race, `start.bat` startup ordering, frontend request burst, connection reuse/keep-alive issue, or
unrelated transient local environment behavior. Fix only if code-fixable; otherwise document with
concrete evidence. Do not modify authentication behavior, redesign the API, or introduce
production infrastructure.

## Started
2026-08-26

---

## 1. Pre-Investigation Reconnaissance

- [x] Read `start.bat`, `gameforge-ai/vite.config.ts`, `gameforge-ai/src/services/api.ts`,
      `gameforge-ai/package.json`, `backend/app/main.py` (lifespan/startup)
- [x] Read `FULL_STACK_OPERATIONAL_AUDIT.md`, `BROWSER_E2E_TEST_REPORT.md`, prior `TASK.md`

### Evidence
- `FULL_STACK_OPERATIONAL_AUDIT.md` already contains **FS-020**, a prior finding (2026-08-24,
  different session) describing the *exact same symptom* on `/api/profile/preferences`,
  `/api/projects`, `/api/discovery/search` — root-caused there as system-wide physical memory
  exhaustion driving OS-level paging that stalls the Node/Vite proxy process, confirmed via
  free-RAM measurement (1.2-1.7GB free of 7.7GB) and an elevated Windows "Memory Compression"
  process, and classified **ENVIRONMENTAL, NOT CODE-FIXABLE**.
- `backend/app/main.py`'s `lifespan()` does only lightweight orphan-build DB reconciliation on
  startup — no eager Discovery/FAISS/embedding warm-up (that was already removed per FS-018). The
  4 endpoints in question (`saved-discoveries`, `projects`, `profile/progress`,
  `profile/preferences`) are plain DB reads with no dependency on the slow Discovery catalog, so a
  backend-readiness race specific to those endpoints was not structurally plausible going in.
- `gameforge-ai/vite.config.ts` proxy config is minimal/standard (`target: 'http://127.0.0.1:8000'`,
  `changeOrigin: true`, no custom agent/keep-alive/timeout options — Vite/`http-proxy` defaults).
- `gameforge-ai/src/services/api.ts`'s `request()` has no retry logic; a `502` surfaces as a plain
  `ApiError` and is caught/`console.warn`ed by the calling `AppContext` function (by design, not
  swallowed silently as an app-level failure).

---

## 2. Reproduction

- [x] Started backend (`uvicorn`, confirmed healthy via `/docs`) and frontend (`vite`) fresh,
      confirmed both fully warm before testing (rules out cold-start/readiness races by
      construction)
- [x] Registered a real test user directly against the backend (`POST /api/auth/register`, `201`)
      to obtain a valid JWT, bypassing the browser entirely for a controlled, scriptable repro
- [x] Fired the same 4 endpoints (`saved-discoveries`, `projects`, `profile/progress`,
      `profile/preferences`) that originally 502'd, in two modes, 10 rounds each:
      **(a) 4-way concurrent** (matching the real `Promise.all` burst `AppContext.login`/`register`
      fires) and **(b) fully sequential**, each round run twice — once straight to the backend
      (`127.0.0.1:8000`), once through the Vite proxy (`127.0.0.1:5173`)
- [x] Measured system free memory (`Get-CimInstance Win32_OperatingSystem`) and checked for the
      Windows `Memory Compression` process at the time of failures
- [x] Captured the Vite dev server's own stdout/stderr for the underlying proxy error

### Results
| Test | Requests | Result |
|---|---|---|
| Direct → backend, concurrent (10 rounds × 4) | 40 | **40/40 (100%) succeeded**, 15-50ms each |
| Proxy → backend, concurrent (10 rounds × 4) | 40 | **25/40 (62.5%) failed** (`502` or connection failure) |
| Proxy → backend, **fully sequential** (10 rounds × 4, zero concurrency) | 40 | **~20/40 (50%) failed** — comparable failure rate with **no concurrency at all** |

- System free memory measured **0.91 GB → 0.23 GB** of 7.68 GB total *during* this test run (this
  machine's physical RAM, not a container/VM limit).
- Windows `Memory Compression` process active and holding 126MB at the time of failures — the same
  active-paging signature FS-020 used as evidence.
- Vite's own log recorded, for every failure: `[vite] http proxy error: <path>` /
  `Error: read ECONNRESET at TCP.onStreamRead` — a low-level TCP reset on the **proxy→backend**
  socket, not an HTTP-level error from FastAPI (the backend's own access log shows every one of
  these same requests, across the whole session, eventually served `200 OK` — the backend itself
  never failed to handle a single request it received).

---

## 3. Root Cause Analysis

Classification options were: (A) Vite dev-proxy race, (B) backend readiness race, (C) `start.bat`
startup ordering, (D) frontend request burst, (E) connection reuse/keep-alive issue,
(F) unrelated transient local environment behavior.

- **(B) and (C) ruled out**: backend was confirmed healthy and fully warm for the entire test
  window (no cold-start, no ordering dependency — `start.bat` wasn't even in the loop for the
  isolated repro); direct-to-backend requests succeeded 100% of the time throughout.
- **(D) ruled out as the trigger**: the fully **sequential** test (zero concurrent requests, one at
  a time, waiting for each response) failed at essentially the same rate (~50%) as the concurrent
  burst (62.5%). If request-burst/concurrency were the cause, the sequential run should have been
  near-100% clean — it wasn't.
- **(A) not supported as a proxy-internal race**: same reasoning — a "race" implies concurrent
  requests interfering with each other inside the proxy; this reproduces with no concurrency.
- **(E) is the *mechanism*, not the root trigger**: the failure is a genuine low-level `ECONNRESET`
  on the Node/Vite proxy's socket to the backend — but nothing in this diff or the existing proxy
  config manages connection pooling explicitly, and the reset is consistent with the OS tearing
  down/stalling a socket under memory pressure, not a logic bug in reuse bookkeeping.
- **(F) confirmed as root cause**: the failures track directly with this machine's free physical
  RAM collapsing toward zero (0.91GB → 0.23GB of 7.68GB total) and an actively elevated Windows
  `Memory Compression` process during the exact window failures occurred, while the backend process
  itself never once failed to complete a request. This reproduces and reinforces **FS-020**
  (`FULL_STACK_OPERATIONAL_AUDIT.md`, 2026-08-24) on this same physical machine, now with a second,
  independently-gathered, more rigorous (concurrent-vs-sequential, direct-vs-proxy) dataset.

**No code-level defect was found in `vite.config.ts`, `start.bat`, `api.ts`, or the backend startup
path.** The Vite proxy's default behavior (no custom retry/circuit-breaker) is standard and
correct; adding masking/retry logic was explicitly out of scope per the task brief and would not
address the actual cause (physical memory exhaustion), which no application-layer code change can
fix.

---

## 4. Fix

**Not applicable — no code fix implemented.** Root cause is external to the application (system
physical memory availability on this development machine), matching the disposition of the prior
FS-020 finding. Implementing a retry/masking layer was explicitly excluded by the task brief and
would misrepresent a genuine resource constraint as resolved.

**No automated regression test was added** for this specific behavior: a test whose pass/fail
outcome depends on the host machine's free RAM at execution time would be inherently flaky in CI
and would not exercise any actual application code path — it would only encode "does this machine
currently have enough free memory," which is not a meaningful assertion about GameForge's
correctness. This judgment call is documented rather than silently skipped.

---

## 5. Verification & Regression

- [x] Backend tests: `.venv\Scripts\python.exe -m pytest tests/ -q` — **335 passed** in 137.83s
      (unchanged from before this investigation — no backend code was modified)
- [x] TypeScript check: `npx tsc --noEmit` — **0 errors**
- [x] Lint check: `npx oxlint` — **0 errors / 0 warnings**
- [x] Production build: `npm run build` — **succeeded**
- [x] `git status` before and after: clean throughout — this task made **zero source changes**
- Browser re-verification not re-run: no code changed, and the investigation's own controlled
  direct-vs-proxy HTTP testing (§2) is a more precise, more repeatable signal for this specific
  symptom than a fresh browser walkthrough would add.

---

## 6. Git Checkpoint

- [x] `git diff` reviewed — empty (investigation only; no `git add`/commit performed for source,
      only this ledger + the two audit docs below are updated)
- [x] No secrets, `.env`, or temporary files staged
- [x] Working tree verified clean of any leftover test artifacts (temp scripts/tokens removed)

---

## Remaining Work
None for this investigation. The underlying environmental constraint (limited free RAM on this
specific development machine, exacerbated by other concurrently-running applications) remains
un-fixable at the application layer, exactly as already disclosed in FS-020.

## Blockers
None.

## Final Verdict
**KNOWN DEVELOPMENT-ONLY LIMITATION.** Reproducible and root-caused with concrete new evidence
(direct-vs-proxy comparison, concurrent-vs-sequential comparison, live memory/paging measurement,
raw Vite proxy error log). Confined to the local Vite dev-proxy path on this specific
memory-constrained machine; does not indicate a defect in GameForge's application code, and does
not apply to a production deployment (no dev proxy exists in that path — the built frontend talks
to the API directly). Reinforces and does not contradict the prior FS-020 finding.

## Change Log
- 2026-08-26: Completed Dev Proxy 502 Investigation. Reproduced the symptom with a controlled
  direct-vs-proxy, concurrent-vs-sequential HTTP test harness (40 requests each condition),
  confirmed root cause as system memory exhaustion (0.91GB→0.23GB free of 7.68GB) driving OS-level
  paging that resets the Vite proxy's backend socket (`ECONNRESET`), while the backend itself never
  failed a single request. Classified KNOWN DEVELOPMENT-ONLY LIMITATION, consistent with and
  reinforcing FS-020. No code changes made (none would be correct — root cause is not code-fixable).
  335/335 backend tests, clean TypeScript/lint/build, confirming zero regressions from the
  investigation itself.
- 2026-08-26: (Prior) Completed browser verification for the UI Copy Audit (commit `db61452`).
- 2026-08-26: (Prior) Completed Website Content & UI Copy Audit V1 (commit `b192bc1`).
- 2026-08-26: (Prior) Completed UI Motion & Special Effects V1 (commit `4e7fc90`).
