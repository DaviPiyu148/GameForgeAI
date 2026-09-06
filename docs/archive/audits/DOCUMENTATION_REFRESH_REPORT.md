# GameForge AI — Living Documentation Refresh V1

**Date:** 2026-08-26
**Scope:** Documentation-only. No application code, API contracts, database schema, or runtime behavior changed. Verified via full regression (below) — everything that passed before this pass still passes identically.

---

# Files Updated

| File | What changed |
|---|---|
| `README.md` | Full rewrite. Removed "Backend and AI are not yet implemented" and the aspirational "Future Architecture" framing (backend is fully implemented and consumed). Added a current capabilities list, current architecture diagram, and accurate dev-setup instructions. |
| `backend/README.md` | Full rewrite. Removed "Current Phase: B5" and "61 unit and integration tests passing". Replaced with an accurate current-state summary, a directory structure reflecting all current modules (`ai/`, `auth/`, `generation/`, `runtime/`, `search/`, `api/`, `schemas/`, `models/`, `repositories/`, `services/`), and a "run `pytest -v` for the current count" instruction instead of a hardcoded number that will drift again. |
| `gameforge-ai/README.md` | Full rewrite. Was unmodified Vite/React template boilerplate — replaced with a concise GameForge-specific frontend README (role, stack, dev commands, API proxy config, runtime architecture notes for auth tokens/SSE/Phaser/motion system/toasts). |
| `docs/02-PRODUCT-SPEC.md` | One targeted fix: "Persistent objects eventually include..." → accurate current entity list, noting there's no separate `GameArtifact`/`Discovery` table (the artifact is `Project.game_dsl` + `runtime_metadata`; the catalog is an offline dataset, not a per-user entity). Product vision/principles sections left untouched, as instructed. |
| `docs/06-BACKEND-ARCHITECTURE.md` | Updated the migration list from 6 to all 12 current migrations. Added `api/profile.py` and the newer `projects.py` routes (blueprint/remix) to the API Controllers list. Added `AvatarService`, `PreferenceService`, `ProgressionService` to the Services list (previously undocumented). Added the 4 Creator Progression / Game DNA tables to the Database list. Architecture content itself was already accurate — not redesigned. |
| `docs/07-DATA-MODEL.md` | Added `scale`/`world_mode` to the documented `Project` entity (both existed in the actual model, both were missing from the doc). Added `avatar_url` to `User`. Added `world_mode` to `BuildJob` (previously only `scale` was documented there). **Added 4 entirely undocumented tables**: `UserProgress`, `XPEvent`, `UserMilestone`, `UserGenrePreference` — the whole Creator Progression / Game DNA persistence layer had no data-model documentation at all before this pass. |
| `docs/08-API-CONTRACT.md` | Added 6 previously-undocumented, real, tested, frontend-wired routes: `POST/DELETE/GET /api/auth/avatar[...]` (3 routes), `POST /api/projects/{id}/blueprint`→ actually `GET`, `POST /api/projects/{id}/remix`, `POST /api/builds/{id}/cancel`. **Added an entirely new "Profile & Personalization" section** for `GET /api/profile/progress` and `GET /api/profile/preferences`, with exact response field lists pulled directly from `app/schemas/profile.py`. Extended the standard error-code list with 7 codes used by the new routes. |
| `docs/13-SECURITY.md` | Added `/api/projects/{id}/blueprint`, `/api/projects/{id}/remix`, `/api/profile/*`, and `/api/auth/avatar/*` to the ownership-protected resource list, with a note on why the avatar-serve route is intentionally unauthenticated (unguessable server-generated filename backing plain `<img>` tags, not a directory listing). Core security principles left untouched. |
| `docs/15-CURRENT-STATUS.md` | Complete refresh, dated 2026-08-26. Now reflects every workstream completed in this session (security audit, hardcoded-literal audit, dynamic-source-of-truth audit, browser verification, UI Motion System, UI Copy Audit, dev-proxy investigation, repository hygiene cleanup) that the prior version (dated 2026-08-24) predated entirely. Explicit roadmap table with COMPLETE/NOT STARTED status per phase — Phase 7 (AI Game Director) and Phase 8 (Monetization/BYOK) both explicitly marked **NOT STARTED**, not silently omitted or implied-complete. |
| `docs/DOCUMENTATION-MAP.md` | One-line fix: `06-BACKEND-ARCHITECTURE.md`'s role label changed from "Planned backend" to "Backend architecture (implemented)". All other labels reviewed — none else were stale. |
| `decisions/ADR-004-BUILD-JOBS.md` | The stale "Current Phase Exception" section (describing a long-superseded frontend-mock `compileProject()`) is now headed "Historical Exception (SUPERSEDED — resolved as of Phase B2)" with a note explaining the real pipeline that replaced it and pointers to the current docs. **The original historical text is preserved verbatim underneath, unedited** — this is a relabeling, not a rewrite of the decision history. |
| `backend/.env.example` | Added the genuinely-live-but-undocumented config fields, verified one-by-one against `app/config.py`'s actual `Settings` class before adding anything: `GROQ_API_KEY`/`GROQ_MODEL`/`GROQ_BASE_URL` (fallback provider), `AI_MODEL`/`AI_API_KEY`/`AI_BASE_URL` (generic provider override), `HF_TOKEN`, `DB_ECHO_SQL`, and `IGDB_CLIENT_ID`/`IGDB_CLIENT_SECRET`/`IGDB_CACHE_TTL_DAYS`. All added as commented-out placeholders (nothing enabled by default, no real secrets, nothing speculative — every field added has a confirmed read site in `config.py`). |
| `SETUP.md` | One targeted fix found during the validation pass (not originally in the brief's edit list, but caught by the required stale-phrase search): "expects 61 tests passing" → "335 passing at time of writing... trust the actual run". |

---

# Files Intentionally Left Historical

Per the brief's explicit instruction and the audit's own prior classification, **not modified**:
- `BROWSER_E2E_TEST_REPORT.md`, `FULL_STACK_OPERATIONAL_AUDIT.md`, `FORENSIC_REVIEW_REPORT.md`, `HARDCODED_LITERAL_AUDIT.md`, `DYNAMIC_SOURCE_OF_TRUTH_AUDIT.md`, `UI_COPY_AUDIT.md`, `UI_MOTION_SYSTEM.md`, `REPOSITORY_HYGIENE_AUDIT.md` — one-time point-in-time reports with genuine forensic/evidentiary value, correctly describing the state of the system at the time they were written.
- `decisions/ADR-001`, `ADR-002`, `ADR-003`, `ADR-005`, `ADR-006`, `ADR-007` — all still accurately describe accepted, current decisions; nothing stale found in any of them.
- `docs/01-PROJECT.md`, `docs/03-TECH-STACK.md`, `docs/04-SYSTEM-ARCHITECTURE.md`, `docs/05-FRONTEND-ARCHITECTURE.md`, `docs/09-AI-GAME-GENERATION.md`, `docs/10-DISCOVERY-ENGINE.md`, `docs/11-IMPLEMENTATION-PHASES.md`, `docs/12-TESTING-QA.md`, `docs/14-DEPLOYMENT.md` — read and spot-checked against actual code; all already accurate, nothing changed.
- `DESIGN.md` and `stitch_gameforge_ai/` — read for context; both are explicitly the "visual source of truth" per `AGENTS.md` and already correctly describe their own relationship (root `DESIGN.md` documents deviations from the original Stitch spec). No staleness found.
- All Alembic migration files, all source code, all tests — untouched, as instructed.
- `TASK.md` — a living execution ledger by design, not in scope for "staleness" classification; updated separately below with this task's own entry.

**One discrepancy worth flagging, not fixed**: this task's own brief references `FULL_STACK_SECURITY_ASSESSMENT.md` as where historical security findings live — **this file does not exist anywhere in the tracked repository** (`git ls-files` confirms, and `docs/13-SECURITY.md`'s actual current text does not itself reference this filename either, before or after this pass). The comprehensive security audit that ran earlier this session was delivered as a Claude Artifact (a published web report), not committed to the repo under that filename. I did not fabricate this file or add any reference to it anywhere; a human should decide whether to commit that audit's findings as a real file under that name, or treat the Artifact as the permanent record.

---

# API Contract Changes

Documentation only — zero actual API behavior changed. `docs/08-API-CONTRACT.md` now documents 6 routes that were already live, tested, and frontend-wired but undocumented: 3 avatar routes, blueprint, remix, and build cancellation. Plus a new "Profile & Personalization" section for the 2 profile routes. See the "Files Updated" table above for detail. All response shapes were taken directly from the actual Pydantic schemas (`app/schemas/profile.py`, `app/schemas/remix.py`), not guessed.

# Data Model Documentation Changes

Documentation only. `docs/07-DATA-MODEL.md` now matches `app/models/*.py` exactly: added 2 missing columns to `Project` (`scale`, `world_mode`), 1 missing column to `User` (`avatar_url`), 1 missing column to `BuildJob` (`world_mode`), and 4 entirely undocumented tables (`UserProgress`, `XPEvent`, `UserMilestone`, `UserGenrePreference`). No transient/non-persisted fields were added as if they were DB columns.

# Current Status Changes

`docs/15-CURRENT-STATUS.md` fully refreshed and re-dated to 2026-08-26. Now lists every completed workstream through this session (previously stopped at the 2026-08-24 Open World milestone), an explicit roadmap table distinguishing COMPLETE from NOT STARTED, a "Current Repository State" section reflecting the hygiene cleanup's before/after counts, and an accurate account of the FS-034 dev-proxy limitation (explicitly labeled development-host-specific and not production-applicable).

# README Changes

All three READMEs (`README.md`, `backend/README.md`, `gameforge-ai/README.md`) rewritten. The two most significant fixes: root `README.md` no longer claims the backend/AI are unimplemented, and `gameforge-ai/README.md` is no longer generic Vite scaffolding text.

# Configuration Example Changes

`backend/.env.example` gained 10 new commented-out fields, every one individually verified against a live read site in `app/config.py` before being added. No secrets were added or exposed — every new line is either a comment or an empty/placeholder assignment.

# ADR Historical Clarifications

`decisions/ADR-004-BUILD-JOBS.md`'s stale exception section was relabeled as historical/superseded with an explanatory note and a pointer to current docs. The original decision text was preserved verbatim, not rewritten — this satisfies "do not rewrite historical reasoning" while still preventing a reader from mistaking a 2-phase-old temporary exception for current behavior.

---

# Consistency Checks

Performed cross-checks as instructed:

| Check | Result |
|---|---|
| `docs/08` API routes vs actual `app/api/*.py` routers | Now matches — all 30 routes documented (confirmed against the full route inventory gathered during the repository hygiene audit, re-verified for the 6 newly-added ones directly against the route handler source) |
| `docs/07` data model vs actual SQLAlchemy models | Now matches — all 9 models, all persisted fields, all FK/constraint notes verified by reading each model file directly |
| `.env.example` vs `app/config.py` | Now matches — every field in `Settings` either already documented or added this pass; nothing in `.env.example` that isn't a real, read `Settings` field |
| `README.md` vs `SETUP.md` | Consistent — both now describe the same real, implemented setup flow; no contradiction between "backend not implemented" (old README) and SETUP's detailed backend setup instructions (that contradiction is what's fixed) |
| `docs/15` current-status vs `TASK.md` / actual implementation | Consistent — `docs/15` now reflects the same workstream list `TASK.md`'s change log shows, and the same commit hashes |

**Stale-phrase validation search** (ran across all living docs, historical reports excluded by design):
- `"not yet implemented"` — 1 hit, in `backend/README.md`'s new "Explicitly Not Yet Implemented" heading, which is itself legitimate/accurate (lists genuinely-unimplemented Phase 7/8/deployment items). No stale hit.
- `"Current Phase: B5"` — 0 hits.
- `"61 tests"` — 1 hit found and fixed (`SETUP.md`, not in the original brief's file list — caught by this validation step, which is exactly what it's for).
- `"planned backend"` — 0 hits.
- `"eventually include"` — 0 hits.

No document claims Phase 7 or Phase 8 functionality exists.

---

# Remaining Documentation Debt

- The `FULL_STACK_SECURITY_ASSESSMENT.md` reference discrepancy noted above (file doesn't exist in the repo; the audit it would describe was delivered as an Artifact instead).
- `docs/12-TESTING-QA.md`'s test count/examples weren't independently re-verified line-by-line against the current 335-test suite in this pass (spot-checked as plausible/specific during the repository hygiene audit; a full line-by-line reconciliation would be a reasonable future pass but wasn't in this task's explicit scope).
- The R&D script naming ambiguity in `backend/scripts/` (misleadingly `test_`-prefixed files) and `test_generation_live.py`'s undocumented status — both already flagged as deferred in `REPOSITORY_HYGIENE_AUDIT.md`, unchanged by this documentation-only pass.
- `gameforge-ai/public/icons.svg`'s uncertain future-use status — same, already flagged, unchanged.

---

# Verification

| Check | Result |
|---|---|
| Backend tests (`pytest tests/ -q`) | **335 passed**, 130.03s |
| TypeScript (`tsc --noEmit`) | **0 errors** |
| Lint (`oxlint`) | **0 errors, 0 warnings** |
| Production build (`npm run build`) | **Succeeded** |
| Alembic (`current`/`heads`) | **`bc9ae398f146` (head)** — single head, unchanged |
| Browser smoke test | Not performed this pass — no code changed (documentation-only diff), so there is no runtime behavior for a browser test to exercise that wasn't already verified in the immediately-preceding repository hygiene cleanup pass on this same code. Not claiming browser behavior changed as a result of these documentation edits. |

**13 files changed, 339 insertions(+), 340 deletions(-). Zero source code, zero migrations, zero package versions, zero test files, zero `start.bat` behavior changed** — confirmed via `git diff --stat` before commit.

---

# Final Verdict

CURRENT documents now describe the CURRENT system: both READMEs, `SETUP.md`, and `docs/02/06/07/08/13/15`/`DOCUMENTATION-MAP.md` all verified against actual code and corrected where stale. HISTORICAL documents remain clearly historical: no audit report, forensic report, or accepted ADR's original reasoning was rewritten — only one ADR's presentation was clarified with an explicit "superseded" label around unchanged original text. ROADMAP items remain clearly future: Phase 7 and Phase 8 are explicitly marked NOT STARTED everywhere they're mentioned, nowhere implied complete.
