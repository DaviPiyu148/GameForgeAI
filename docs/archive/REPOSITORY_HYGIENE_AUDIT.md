# GameForge AI — Full Repository Hygiene & Dead-Code Audit V1

**Date:** 2026-08-26
**Scope:** Entire tracked repository (294 files, 282 after cleanup) — frontend, backend, tests, migrations, scripts, config, dependencies, assets, CSS, and documentation.
**Status:** Audit complete (Phases 0-20). **Cleanup complete** — the 12 HIGH-confidence files below plus the favicon fix were approved and executed; see "Cleanup Results" for evidence. All deferred/uncertain candidates remain untouched, exactly as scoped.

---

# Audit Methodology & a Correction Made Mid-Audit

The investigative work (frontend, backend, scripts/config/deps/docs) was split across three parallel research agents, two of which were launched with git-worktree isolation. That isolation defaulted to a worktree pinned at commit `1c4b098` — **9 commits behind** the real current HEAD (`fc504c3`) at audit time. Those 9 commits happen to include this session's entire UI Motion System (`toastBus.ts`, `ToastContainer.tsx`, `UI_MOTION_SYSTEM.md`), the `urlUtils.ts` fix + its test, the UI Copy Audit, and three other root-level audit docs (`HARDCODED_LITERAL_AUDIT.md`, `DYNAMIC_SOURCE_OF_TRUTH_AUDIT.md`, `UI_COPY_AUDIT.md`) plus `backend/pytest.ini`.

This was caught by cross-checking the agents' "file does not exist" claims directly against the real working tree (`ls`/`git ls-files` at actual HEAD) before trusting them. Concretely:
- `git diff --stat 1c4b098 fc504c3` was run for `gameforge-ai/`, `backend/`, and root/docs to get the *exact* list of what the stale snapshot missed (27 files total: 18 in `gameforge-ai/`, 9 in `backend/`, 8 at root — see below).
- Every "dead"/"doesn't exist" claim touching one of those 27 files was independently re-verified against real HEAD (via `Read`/`Grep`/`ls`) before being included or excluded here.
- Everything the agents reported about files **outside** that changed set (the large majority of the repository) is trusted as-is — those files are byte-identical between the stale snapshot and real HEAD.

This correction is why the findings below sometimes note "confirmed independently" or "corrected from agent report" — that's this reconciliation, not agents disagreeing with each other. Full diffs for the record:

- `gameforge-ai/`: `App.tsx`, `AuthModal.tsx`, `PrototypeModal.tsx`, `ToastContainer.tsx` (new), `AppContext.tsx`, `BuilderPage.tsx`, `DashboardPage.tsx`, `ErrorStatusPage.tsx`, `HomePage.tsx`, `NoMatchesPage.tsx`, `ProfilePage.tsx`, `SuccessStatusPage.tsx`, `GameScene.ts`, `urlUtils.test.ts` (new), `builds.ts`, `toastBus.ts` (new), `urlUtils.ts` (new), `styles/index.css`.
- `backend/`: `app/ai/prompts.py`, `app/generation/blueprint.py`, `app/generation/dsl_models.py`, `app/services/game_generation_service.py`, `app/services/progression_service.py`, `pytest.ini` (new), `tests/test_dynamic_source_of_truth.py` (new), `tests/test_game_generation.py`, `tests/test_playtest_telemetry_v2.py`.
- Root: `BROWSER_E2E_TEST_REPORT.md`, `DYNAMIC_SOURCE_OF_TRUTH_AUDIT.md` (new), `FULL_STACK_OPERATIONAL_AUDIT.md`, `HARDCODED_LITERAL_AUDIT.md` (new), `TASK.md`, `UI_COPY_AUDIT.md` (new), `UI_MOTION_SYSTEM.md` (new), `start.bat`.

**Practical effect on this report's reliability**: the reference-graph findings for components, pages, runtime modules, services, backend routes/services/models, scripts, config, and dependencies are unaffected (none of those files are in the changed set) and are reported at full confidence. Anything specifically about the 27 changed/new files above was independently re-verified by me against real HEAD.

---

# Inventory

294 tracked files total.

| Category | Count |
|---|---|
| Root-level `.md` docs/reports | 12 |
| `docs/*.md` | 16 |
| `decisions/ADR-*.md` | 7 |
| `stitch_gameforge_ai/` (design reference: 7×`code.html`+`screen.png`, 1×`DESIGN.md`) | 15 |
| Backend `app/**/*.py` (source) | 79 |
| Backend `tests/**/*.py` | 48 |
| Backend `scripts/**/*.py` | 15 |
| Backend `alembic/versions/*.py` (migrations) | 12 |
| Backend config (`alembic.ini`, `pytest.ini`, `requirements.txt`, `.env.example`, `.gitignore`) | 5 |
| Backend `data/*.md` (dataset provenance docs) | 3 |
| Frontend `src/**/*.{ts,tsx}` | 56 |
| Frontend `src/**/*.css` | 2 |
| Frontend config (`package.json`, lockfile, `vite.config.ts`, 3×`tsconfig*.json`, `.oxlintrc.json`, `.gitignore`, `index.html`) | 9 |
| Frontend `public/*` assets | 2 |
| Frontend `src/assets/*` | 3 |
| Root scripts | `start.bat` (1), `test_generation_live.py` (1) |

Generated/data artifacts (`backend/gameforge.db`, `backend/data/processed/*`, `backend/data/raw/*.{csv,zip}`, `backend/data/uploads/*`) are **not tracked** — confirmed correctly gitignored via `git check-ignore -v` for every one of them. No cleanup needed there.

**Other branches** (`master`, `backup-before-cleanup`, `remotes/origin/main`) share **no merge-base** with the current `fresh-main` branch — they're an entirely separate, older history. Out of scope for a file/folder hygiene audit (nothing in the working tree references them), but noted as its own category of repo debt at the very end of this report.

---

# Dead Code Candidates — Frontend

All 9 below were confirmed **DEAD** (zero import sites anywhere in `gameforge-ai/src`, verified by an independent agent grep and, for the ones I'd already read personally during the UI Motion System task, corroborated firsthand), re-verified with a fresh whole-repo reference check immediately before deletion, and **have now been deleted**:

| ID | Path | Evidence | Superseded by | Status |
|---|---|---|---|---|
| FE-01 | `src/components/Shared/Button.tsx` | Zero import sites; every page uses raw `<button className="...">` | Inline Tailwind classes per call site | **FIXED (deleted)** |
| FE-02 | `src/components/Shared/DiscoveryCard.tsx` | Zero import sites | Inline card markup in `HomePage.tsx:304-419` (richer — has match-tier badge, cover-image fallback chain, highlights) | **FIXED (deleted)** |
| FE-03 | `src/components/Shared/ProjectCard.tsx` | Zero import sites | Inline card markup in `DashboardPage.tsx:64-131` | **FIXED (deleted)** |
| FE-04 | `src/components/Shared/StatusBadge.tsx` | Zero import sites *except* the also-dead `ProjectCard.tsx` | Inline status-colored badge, e.g. `DashboardPage.tsx` (added this session) | **FIXED (deleted)** |
| FE-05 | `src/components/Shared/TerminalPane.tsx` | Zero import sites *except* the also-dead `ProjectCard.tsx` | Bespoke per-page terminal-styled markup | **FIXED (deleted)** |
| FE-06 | `src/components/Shared/ParameterControl.tsx` | Zero import sites | Raw `type="range"` inputs inline in `BuilderPage.tsx:258,275` | **FIXED (deleted)** |
| FE-07 | `src/components/Shared/ProgressBar.tsx` | Zero import sites | Bespoke inline progress markup per page | **FIXED (deleted)** |
| FE-08 | `src/components/Shared/ScanlineOverlay.tsx` | Zero import sites | Its underlying `.scanline-effect` CSS class *is* used, just applied inline directly (`PageContainer.tsx:13`, `NoMatchesPage.tsx:45`, `BuilderPage.tsx:322`) — only the wrapper component was never wired in | **FIXED (deleted)** |
| FE-09 | `src/components/Shared/SectionHeader.tsx` | Zero import sites | Ad hoc `<h2>/<h3>` per page | **FIXED (deleted)** |

**Confidence: HIGH** for all 9 — confirmed correct. These were self-contained files (FE-04/FE-05 only imported by the also-dead FE-03) with no other consumer; deletion did not break Tailwind's class scanning, routing, tests, or the build (all verified post-deletion — see "Cleanup Results").

**Assets** (also HIGH confidence, confirmed independently by two agents, **now deleted**):

| ID | Path | Evidence | Status |
|---|---|---|---|
| FE-10 | `src/assets/react.svg` | Zero references; Vite/React template scaffolding leftover | **FIXED (deleted)** |
| FE-11 | `src/assets/vite.svg` | Zero references from `src/`; **but see the bug below** — `index.html` references a `/vite.svg` at the *public* root, which is a different, non-existent file | **FIXED (deleted)** |
| FE-12 | `src/assets/hero.png` | Zero references; superseded by dynamic backend-served cover art | **FIXED (deleted)** |

**MEDIUM confidence:**

| ID | Path | Evidence |
|---|---|---|
| FE-13 | `public/icons.svg` | Zero references found (no `<use href="/icons.svg#...">` pattern anywhere). Could be reserved for a future icon-sprite system — not as clear-cut as FE-10/11/12. Recommend **INVESTIGATE FURTHER**, not auto-delete. |

**Not dead-code, but a real bug worth fixing regardless of the cleanup decision:**

`gameforge-ai/index.html:5` referenced `<link rel="icon" href="/vite.svg" />`, but `gameforge-ai/public/` contains no `vite.svg` — only `favicon.svg` and `icons.svg`. The actual custom favicon (`public/favicon.svg`) was never wired up; the browser tab was getting no icon (404 on `/vite.svg`) rather than the intended GameForge icon. **FIXED**: changed the href to `/favicon.svg`. Verified `public/favicon.svg` exists before the fix, and verified post-fix that `GET /favicon.svg` returns `200` from the dev server and the correct `<link>` tag is present in the served HTML.

**No unused frontend npm dependencies found.** Every entry in `package.json` has a confirmed import/config-registration site. `package-lock.json` is in sync.

---

# Dead Code Candidates — Backend

**None found at the file/module level.** Every service, model, schema, repository, generation module, and search-engine module has a confirmed live call site. `validator.py` and `quality_validator.py` (the one pairing that looked duplicate-shaped from the name) are confirmed **complementary**, not redundant: `validator.py` does structural/schema normalization and script-injection rejection; `quality_validator.py` does deterministic gameplay-fairness/budget checks — both run sequentially in the same pipeline (`game_generation_service.py:26-27`). No orphaned "Discovery 1.0" module set exists behind Discovery Engine 2.0-2.2 — evolution happened in place within the same six `app/search/*.py` files.

**No unused backend dependencies found.** All 15 `requirements.txt` entries have confirmed import sites (accounting for package-name vs. import-name differences: `PyJWT`→`jwt`, `faiss-cpu`→`faiss`, `python-multipart`→FastAPI's internal form parser).

**One config field with no read site (MEDIUM confidence, not auto-actionable):**

| ID | Path | Evidence |
|---|---|---|
| BE-01 | `app/config.py` — `AI_PROVIDER` setting | Defined and documented in `.env.example:7`, but `grep -n "settings\.AI_PROVIDER\b" backend` returns zero matches in `app/`. Provider selection currently appears hardcoded to the Gemini path rather than actually switched by this setting. Possibly forward-looking (multi-provider switching), possibly genuinely dead. **Recommend INVESTIGATE FURTHER** — this is a behavioral question (should provider selection actually respect this setting?), not a pure hygiene deletion. |

---

# API / Route Orphan Audit

All 30 routes across all 7 routers are correctly registered (`app/main.py:150-156`). Every route has a test caller. Only two have no frontend caller:

| Route | Status |
|---|---|
| `GET /api/health` | No frontend caller — expected and correct; it's an ops/monitoring probe, not an SPA-consumed endpoint. **KEEP — ACTIVE.** |
| `GET /api/projects/{id}/playtests/{session_id}` | Test-covered, undocumented in `docs/08-API-CONTRACT.md`, no frontend caller. Completes the CRUD surface for a documented sibling list-endpoint. **KEEP — INVESTIGATE FURTHER** (not evidence of dead code; a human should decide if it's future-facing or should be wired to UI). |

`docs/08-API-CONTRACT.md` itself is confirmed **stale** — it predates and is missing: both avatar endpoints, `profile/progress`, `profile/preferences`, `blueprint`, `remix`, and `builds/{id}/cancel`. This is a documentation gap, not evidence any of those routes are dead (all 6 have real frontend callers and tests).

---

# Frontend Route Audit

All 7 pages map 1:1 to the 7 registered routes in `App.tsx`, matching `AGENTS.md`'s "exactly seven primary routes" rule exactly. No orphaned pages, no missing routes, no dead navigation links.

---

# Scripts / Automation Audit

*(Investigative only — see the top-level note on the "Phase 7" naming ambiguity in the original task brief: no product-roadmap "Phase 7" exists anywhere in this repo's docs, so this is read as the audit spec's own internal Phase 7 section, already covered by the user's "audit first" approval, not a forward product phase under `AGENTS.md`'s phase-discipline rule.)*

`start.bat` is the sole launcher in the repo (no Makefile/justfile/CI config exists at all). Every path/endpoint it references (`.venv`, `requirements.txt`, `.env.example`, `GET /api/health`) exists and matches. **KEEP — ACTIVE.**

`gameforge-ai/package.json`'s 4 scripts (`dev`/`build`/`lint`/`preview`) are all standard and self-contained.

**`backend/scripts/*.py` (15 files) — classification:**

| Script | Status | Recommendation |
|---|---|---|
| `ingest_catalog.py` | Referenced by `SETUP.md:129`, `backend/README.md:161` — required fresh-machine setup step | **KEEP — ACTIVE** |
| `build_index.py` | Referenced by `SETUP.md:137`, `backend/README.md:162` — required fresh-machine setup step | **KEEP — ACTIVE** |
| `seed_dev.py` | Referenced by `.env.example:26-27` | **KEEP — ACTIVE** (dev convenience tool) |
| `audit_discovery_corpus.py`, `audit_landmarks.py`, `audit_language_distribution.py`, `diagnose_eval.py`, `evaluate_multilingual_strategies.py`, `test_cross_language_baseline.py` | One-off R&D diagnostics from Discovery-engine tuning; zero doc references | **KEEP — HISTORICAL** (LOW-MEDIUM confidence to delete; genuine historical R&D value if the discovery engine is ever retuned, similar rationale to keeping historical audit reports; not auto-actionable) |
| `evaluate_discovery.py` vs `evaluate_discovery_2.py` | `_2` is a strict superset in scope/rigor (full P@5/R@10/MRR/NDCG vs. simple latency print), different fixture files, neither doc-referenced | **INVESTIGATE FURTHER** — plausible consolidation candidate (retire `_1`), but not a strict duplicate; a human should confirm `_1`'s narrower fixture isn't still meaningful before retiring it |
| `test_baseline_queries.py`, `test_discovery_2_queries.py`, `test_lexical_verify.py`, `test_query_parser_verify.py` | Misleadingly named (`test_` prefix, but not intended as part of the `backend/tests/` suite) | **RECOMMEND RENAME** (e.g. `verify_*`/`check_*`), not deletion — see the pytest-collection finding immediately below for why this used to matter more than it does now |

**Historical finding, already resolved at current HEAD**: the stale-worktree investigation empirically confirmed that, as of commit `1c4b098`, running bare `pytest -v` from `backend/` with no `pytest.ini` accidentally collected 4 of those `test_*`-named scratch scripts alongside the real 328-test suite (332 items collected, 4 from `scripts/`). **I re-ran this myself against real HEAD and confirmed it is already fixed**: `backend/pytest.ini` (added in the commit gap this agent's snapshot missed) sets `testpaths = tests`, and `pytest --collect-only -q` at real HEAD collects exactly 335 items, zero from `scripts/` (verified via `grep -i "scripts/"` on the collect output — zero matches). The rename recommendation above is now a pure naming-clarity nit, not a functional bug.

---

# Configuration Audit

No dead/obsolete configuration found in `vite.config.ts`, the 3 `tsconfig*.json` files, `.oxlintrc.json`, `alembic.ini`, or either `.gitignore`. `backend/app/config.py`'s 17 settings fields all have live read sites except `AI_PROVIDER` (BE-01 above).

**`.env.example` gaps** (documentation, not dead code): `IGDB_CLIENT_ID`/`IGDB_CLIENT_SECRET`/`IGDB_CACHE_TTL_DAYS` and `GROQ_*`/generic-provider fallback fields are live, used settings (confirmed call sites) but absent from `.env.example`, unlike every other configured feature. **Recommend adding them** as a documentation fix — low effort, real value for anyone setting up IGDB enrichment or the Groq fallback provider from scratch.

---

# Dependency Audit

**Frontend**: zero unused dependencies (11 deps + 9 devDeps, all confirmed used).
**Backend**: zero unused dependencies (15 requirements.txt entries, all confirmed used).

No action needed in Phase 23 (dependency cleanup) — there is nothing to remove.

---

# Asset Audit

Covered under "Dead Code Candidates — Frontend" above (FE-10, FE-11, FE-12 dead; FE-13 uncertain). `stitch_gameforge_ai/`'s 7 design-reference subfolders (each `code.html`+`screen.png`) plus `obsidian_forge/DESIGN.md` are explicitly designated **KEEP — the "visual source of truth"** per `AGENTS.md` line 15's exact wording; not a deletion candidate under any confidence level. No stray/accidentally-committed screenshots, logs, or scratch files exist anywhere else in the tracked repo (verified via a repo-wide extension/pattern search).

---

# CSS / Tailwind Dead Code

**None found.** Two CSS files exist: `src/index.css` (a 5-line, self-documented intentional stub — "the design system is defined in `./styles/index.css`... this file intentionally left minimal") and `src/styles/index.css` (the real 391+ line stylesheet, imported by `main.tsx`). Every utility class and every `@keyframes` block in the real stylesheet was checked against `.tsx` usage — all are referenced by at least one component (including the ones added this session: `.toast-enter`/`.toast-enter-emphasis`/`.toast-exit`, `.scan-sweep`, `.milestone-unlock-flash`, `.fullscreen-transition`, all confirmed by me directly since I authored and browser-verified them earlier this session). No orphaned keyframes, no dead theme variables, no leftover pre-motion-system CSS.

---

# Test Audit

**Frontend**: no test runner is configured (`package.json` has no `test` script). `src/services/__tests__/urlUtils.test.ts` exists and is run manually via `npx tsx` (per this session's own FS-028 fix record) — it works, but isn't wired into `npm run build`/CI/any script. **Not dead** — genuinely useful regression coverage for `joinApiUrl()` — but flagged as a process gap: nothing currently guarantees it gets run.

**Backend**: 48 files under `backend/tests/`, all pytest-discovered via `testpaths = tests`, all exercising current code (no test found referencing a removed API, deleted model, or old file path). Full suite: 335 passed (verified multiple times this session, most recently in the dev-proxy investigation).

**Root-level `test_generation_live.py`** (NOT under `backend/tests/`):

| ID | Path | Evidence | Recommendation |
|---|---|---|---|
| RT-01 | `test_generation_live.py` | Manual live-Gemini-API smoke test (`if __name__ == "__main__"`, not pytest-shaped without `@pytest.mark.asyncio`). Zero references from any doc/script anywhere in the repo. Imports `dotenv`, which is **not listed** in `backend/requirements.txt` — not guaranteed to even run in the documented environment. Does not duplicate `backend/tests/test_game_generation.py` (that one uses a fully deterministic mock provider; this one intentionally hits the real API). | **MEDIUM confidence — INVESTIGATE FURTHER**, not auto-delete. It has plausible ongoing value as a manual "is the real Gemini integration actually alive" check, but as-is it's undocumented, unreferenced, and depends on an untracked package. Recommend either: (a) document it in `SETUP.md`/`backend/README.md` and add `python-dotenv` to `requirements.txt`, or (b) move it into `backend/scripts/` for consistency and do the same, or (c) delete it if no one actually uses it manually — this is a judgment call only the project owner can make, not a "clearly dead" file the way FE-01..FE-09 are. |

---

# Alembic / Database Hygiene

**Clean.** Full 12-migration chain reconstructed and verified (both by manual `revision`/`down_revision` tracing and by running `alembic heads`/`alembic history` directly): single linear chain, `57a6f0ac8836` (root) → ... → `bc9ae398f146` (head), zero branches, zero orphaned/unreachable files. **No action recommended or needed.** (Also independently re-confirmed by this session's earlier work: `alembic current`/`heads` both report the single head cleanly.)

---

# Documentation Audit

| File | Classification | Evidence |
|---|---|---|
| `README.md` | **STALE** | Line 6-7 states "Backend and AI are not yet implemented" — flatly contradicted by the fully-implemented 79-file backend, 335 passing tests, and the rest of the repo. The "Future Architecture" diagram presents an already-built, already-consumed backend as aspirational. |
| `backend/README.md` | **STALE (severe)** | Line 5: "Current Phase: B5... 61 tests passing" — actual current state is far past B5 (Phase 6 complete, Blueprint/Remix, Creator Progression, Open World all shipped) with 335 tests. This exact staleness was already independently flagged as `FS-011` in `FULL_STACK_OPERATIONAL_AUDIT.md` from a prior session — still unfixed. |
| `gameforge-ai/README.md` | **STALE (low-value)** | Unmodified Vite/React template boilerplate, never customized for this project. Not harmful, just low-value. |
| `docs/01-PROJECT.md` | **HISTORICAL/CURRENT** | Product brief language, no false implementation-status claims. |
| `docs/02-PRODUCT-SPEC.md` | **STALE (minor)** | "Persistent objects eventually include..." — `User`/`Project`/`ProjectVersion`/`BuildJob`/`SavedDiscovery` are already implemented, not "eventual." |
| `docs/03-TECH-STACK.md` | **CURRENT** | Spot-checked against `requirements.txt`/`package.json` — accurate, including exact `phaser 3.88.2` version match. |
| `docs/04-SYSTEM-ARCHITECTURE.md` | **CURRENT** | Describes the backend as implemented, matching the real `backend/app/` layout. |
| `docs/05-FRONTEND-ARCHITECTURE.md` | **CURRENT** | Correctly states the frontend is integrated with the real backend API layer. |
| `docs/06-BACKEND-ARCHITECTURE.md` | **CURRENT content, STALE label** | Content matches the implemented backend, but `docs/DOCUMENTATION-MAP.md` still labels this file's role as "Planned backend" — that label itself is stale. Migration list in the doc stops at `c3d4e5f6a7b8`, missing the 4 newest migrations. |
| `docs/07-DATA-MODEL.md` | **STALE (incomplete)** | Documented `Project` entity omits real columns `scale` and `world_mode` (Phase 5/6 additions); documented `User` entity omits `avatar_url`. |
| `docs/08-API-CONTRACT.md` | **STALE (incomplete)** | Missing 6 real, tested, frontend-wired routes — see API Audit section above. |
| `docs/09-AI-GAME-GENERATION.md` | **CURRENT** | Matches `app/generation/` module names and Phase 4/5/6 content. |
| `docs/10-DISCOVERY-ENGINE.md` | **CURRENT** | Endpoint list matches `discovery.py` exactly. |
| `docs/11-IMPLEMENTATION-PHASES.md` | **CURRENT** | Matches actual phase history; "Next Phase: B8" framing is accurate as the last unstarted phase. |
| `docs/12-TESTING-QA.md` | **CURRENT** | Named test functions are specific/plausible, consistent with the real suite. |
| `docs/13-SECURITY.md` | **CURRENT (minor gap)** | Accurate for what it covers; doesn't mention the newer (also `get_current_user`-gated) `/api/profile/*` or `/api/auth/avatar/*` routes. |
| `docs/14-DEPLOYMENT.md` | **CURRENT** | Accurate, matches actual commands. |
| `docs/15-CURRENT-STATUS.md` | **STALE (severe, dated 2026-08-24)** | Predates and doesn't mention: the entire UI Motion System, the UI Copy Audit, the Hardcoded Literal Audit, the Dynamic Source-of-Truth parity audit, or the comprehensive security audit — all of which happened 2026-08-26, all committed. This is the single most out-of-date "living status" doc in the repo relative to its own stated purpose. |
| `docs/DOCUMENTATION-MAP.md` | **STALE (one label)** | "Planned backend" label for `06-BACKEND-ARCHITECTURE.md` — see above. |
| `decisions/ADR-001` through `ADR-003`, `ADR-005` through `ADR-007` | **CURRENT/HISTORICAL** | All match actual implementation; correctly treated as durable accepted decisions. |
| `decisions/ADR-004-BUILD-JOBS.md` | **STALE (one section)** | "Current Phase Exception" section describes a frontend-mock `compileProject()` that predates the real `POST /api/builds` integration (confirmed live and wired since B2/B6). Should be reclassified historical/superseded rather than left reading as an active exception. |
| `BROWSER_E2E_TEST_REPORT.md`, `FULL_STACK_OPERATIONAL_AUDIT.md`, `FORENSIC_REVIEW_REPORT.md`, `HARDCODED_LITERAL_AUDIT.md`, `DYNAMIC_SOURCE_OF_TRUTH_AUDIT.md`, `UI_COPY_AUDIT.md`, `UI_MOTION_SYSTEM.md` | **HISTORICAL — KEEP AS EVIDENCE** | One-time point-in-time audit/verification reports, each with genuine forensic value (documents real root-caused bugs and their fixes). Per the audit brief's own instruction, historical reports are not deletion candidates regardless of age. |
| `SETUP.md` | **CURRENT** | Spot-checked against `requirements.txt`, `alembic upgrade head`, `start.bat` structure — accurate. |
| `TASK.md` | **CURRENT (living, by design)** | The mandatory execution ledger per `AGENTS.md` — intentionally living, out of scope for staleness classification. |

**`DESIGN.md` (root) vs `stitch_gameforge_ai/obsidian_forge/DESIGN.md`**: **not duplicates.** Root `DESIGN.md` is the consolidated, current design system and explicitly documents where the shipped UI *deviates* from the original Stitch "Obsidian Forge" spec (color palette, fonts, corner radii). Both are intentionally retained per `AGENTS.md`'s "visual source of truth" designation — no action needed.

**None of the documentation findings above are deletion candidates.** They're content-update recommendations, listed here because the audit brief asked for a full staleness classification. Whether to act on them (i.e. actually edit these docs) is a separate decision from the file-deletion cleanup this pass is scoped to — flagging for your call.

---

# Duplicate Implementation Audit

| Concept | Implementation A | Implementation B | Canonical | Action |
|---|---|---|---|---|
| Discovery result card | `DiscoveryCard.tsx` (dead) | Inline markup, `HomePage.tsx` | B | Delete A (FE-02) |
| My-Games project card | `ProjectCard.tsx` (dead) | Inline markup, `DashboardPage.tsx` | B | Delete A (FE-03), and its sole dependents `StatusBadge.tsx`/`TerminalPane.tsx` (FE-04/05) |
| Scanline visual effect | `ScanlineOverlay.tsx` component (dead) | Inline `.scanline-effect` class usage (3 sites) | B | Delete wrapper component A (FE-08); the CSS class itself stays, it's alive |
| Build-parameter control | `ParameterControl.tsx` (dead) | Inline `type="range"` in `BuilderPage.tsx` | B | Delete A (FE-06) |
| Progress/status display | `ProgressBar.tsx` (dead) | Bespoke inline markup per page | B | Delete A (FE-07) |
| Section heading | `SectionHeader.tsx` (dead) | Ad hoc headings per page | B | Delete A (FE-09) |
| Generic button | `Button.tsx` (dead) | Inline `<button>` per call site | B | Delete A (FE-01) |
| Ownership/IDOR check pattern | Query-level filter (`saved_discovery_repo.py:34-44`) | Post-fetch compare, repeated 4× (`build_service.py`) | Neither strictly wrong | **LOW confidence, optional**: could consolidate `build_service.py`'s 4 repeated post-fetch-compare blocks into one helper for consistency; not urgent, both patterns are individually correct and tested |
| Structural vs. gameplay-quality validation | `validator.py` | `quality_validator.py` | **Both — not duplicates** | No action; confirmed complementary two-stage pipeline |
| Discovery search engine | `app/search/*.py` (single implementation) | — | Single implementation | No action; no orphaned prior version exists |
| Game details modal (catalog game) vs. project details modal (user's build) | `GameDetailsModal.tsx` | `ProjectDetailsModal.tsx` | **Both — not duplicates** | Distinct concepts, both actively used; no action |

---

# Safe Deletions — HIGH Confidence (EXECUTED)

| ID | Path | Type |
|---|---|---|
| FE-01 | `gameforge-ai/src/components/Shared/Button.tsx` | SOURCE (dead component) |
| FE-02 | `gameforge-ai/src/components/Shared/DiscoveryCard.tsx` | SOURCE (dead component) |
| FE-03 | `gameforge-ai/src/components/Shared/ProjectCard.tsx` | SOURCE (dead component) |
| FE-04 | `gameforge-ai/src/components/Shared/StatusBadge.tsx` | SOURCE (dead component, dependent of FE-03) |
| FE-05 | `gameforge-ai/src/components/Shared/TerminalPane.tsx` | SOURCE (dead component, dependent of FE-03) |
| FE-06 | `gameforge-ai/src/components/Shared/ParameterControl.tsx` | SOURCE (dead component) |
| FE-07 | `gameforge-ai/src/components/Shared/ProgressBar.tsx` | SOURCE (dead component) |
| FE-08 | `gameforge-ai/src/components/Shared/ScanlineOverlay.tsx` | SOURCE (dead component) |
| FE-09 | `gameforge-ai/src/components/Shared/SectionHeader.tsx` | SOURCE (dead component) |
| FE-10 | `gameforge-ai/src/assets/react.svg` | ASSET (unused template leftover) |
| FE-11 | `gameforge-ai/src/assets/vite.svg` | ASSET (unused template leftover) |
| FE-12 | `gameforge-ai/src/assets/hero.png` | ASSET (unused, superseded) |

That's **12 files**, all frontend, all independently zero-reference-confirmed. No backend files, no scripts, no docs, no migrations, no dependencies qualify as HIGH confidence — everything else found in this audit is either genuinely active, historical-and-intentionally-kept, or a judgment call that needs your input (below).

**Also recommended alongside the above, as a one-line bug fix (not a deletion):** `gameforge-ai/index.html:5` — change `href="/vite.svg"` to `href="/favicon.svg"` so the browser tab actually gets the intended icon instead of a 404.

---

# Deferred / Uncertain Candidates (not auto-actionable — your call)

| ID | Item | Confidence | Why deferred |
|---|---|---|---|
| FE-13 | `gameforge-ai/public/icons.svg` | MEDIUM | No usage found, but could be reserved for a future icon sprite |
| BE-01 | `AI_PROVIDER` config field | MEDIUM | Possibly forward-looking multi-provider design, not clearly dead |
| RT-01 | `test_generation_live.py` (root) | MEDIUM | Real potential manual-tooling value; needs a `requirements.txt` fix (missing `dotenv`) or doc reference either way |
| — | `backend/scripts/audit_*.py`, `diagnose_eval.py`, `evaluate_multilingual_strategies.py`, `test_cross_language_baseline.py` (6 files) | LOW-MEDIUM | One-off R&D scripts with plausible historical/future re-tuning value; not part of any pipeline but not clearly garbage either |
| — | `evaluate_discovery.py` vs `evaluate_discovery_2.py` | MEDIUM | Plausible consolidation (retire `_1`), but not a strict duplicate — different fixtures/metrics |
| — | 4 misleadingly-named `backend/scripts/test_*.py` files | LOW (rename only) | Naming-clarity nit; the functional pytest-collection bug it used to cause is already fixed via `pytest.ini` |
| — | `GET /api/projects/{id}/playtests/{session_id}` route | LOW | Legitimate CRUD-completeness route, test-covered; not dead code |
| — | 15 documentation staleness findings (see Documentation Audit) | N/A | Content-update recommendations, not deletions; separate decision from file cleanup |
| — | Stale branches `master`, `backup-before-cleanup` | N/A | Branch hygiene, not file hygiene; noted for completeness only |

---

# Cleanup Results

**Executed 2026-08-26**, scoped exactly to the approved list — no second sweep, no uncertain candidates touched, no historical reports/migrations touched.

**Final safety check (immediately before deletion, at real HEAD)**: re-ran a whole-repository reference search for all 12 approved files — every component name and every asset filename — across `gameforge-ai/src`, `gameforge-ai/vite.config.ts`, `gameforge-ai/package.json`, `backend/`, and `start.bat`. Zero live references found for any of the 12 (only self-definitions, unrelated substring matches like `HTMLButtonElement`/`closeBtnRef`, and this audit doc's own prose). No new reference had been introduced since the audit. All 12 cleared for deletion; **none were skipped**.

**Deleted (12 files, via `git rm`):**
1. `gameforge-ai/src/components/Shared/Button.tsx`
2. `gameforge-ai/src/components/Shared/DiscoveryCard.tsx`
3. `gameforge-ai/src/components/Shared/ProjectCard.tsx`
4. `gameforge-ai/src/components/Shared/StatusBadge.tsx`
5. `gameforge-ai/src/components/Shared/TerminalPane.tsx`
6. `gameforge-ai/src/components/Shared/ParameterControl.tsx`
7. `gameforge-ai/src/components/Shared/ProgressBar.tsx`
8. `gameforge-ai/src/components/Shared/ScanlineOverlay.tsx`
9. `gameforge-ai/src/components/Shared/SectionHeader.tsx`
10. `gameforge-ai/src/assets/react.svg`
11. `gameforge-ai/src/assets/vite.svg`
12. `gameforge-ai/src/assets/hero.png`

**Favicon reference fixed:** `gameforge-ai/index.html` line 5, `href="/vite.svg"` → `href="/favicon.svg"`. Asset itself untouched (per instruction); `public/favicon.svg` confirmed present before the edit.

**CSS safety check**: one deleted component (`ParameterControl.tsx`) referenced a class name `slider-thumb-primary` that, on inspection, was **never actually defined anywhere in `styles/index.css`** — a pre-existing dangling reference with zero effect either before or after deletion. No other deleted component owned a CSS class/keyframe without a live consumer elsewhere (already confirmed in the original audit's CSS section). **`styles/index.css` was not modified.**

**No uncertain candidates were removed.** `public/icons.svg`, all `backend/scripts/*.py`, `test_generation_live.py`, the `AI_PROVIDER` config field, `evaluate_discovery.py`/`evaluate_discovery_2.py`, all historical audit reports, all Alembic migrations, `stitch_gameforge_ai/`, and `DESIGN.md` remain exactly as they were — confirmed via the final `git diff --stat` (see Git section) showing only the 12 deletions + `index.html` + this doc + `TASK.md`.

# Regression Results

| Check | Command | Result |
|---|---|---|
| Backend tests | `.venv\Scripts\python.exe -m pytest tests/ -q` | **335 passed**, 1 pre-existing warning, 131.45s |
| TypeScript | `npx tsc --noEmit` | **0 errors** |
| Lint | `npx oxlint` | **0 errors, 0 warnings** |
| Production build | `npm run build` | **Succeeded** in 1.49s. CSS bundle 129.47kB→128.40kB (tiny drop — Tailwind no longer generating utilities that were unique to the deleted files; JS bundle unchanged) |
| Alembic | `alembic current` / `alembic heads` | Both report **`bc9ae398f146` (head)** — exactly one head, untouched (no backend files were part of this cleanup) |

# start.bat / App Startup

Not run via `start.bat` directly (that script opens interactive terminal windows unsuited to this environment), but its two actual steps were independently exercised exactly as it performs them:
- Backend: `uvicorn app.main:app --host 127.0.0.1 --port 8000` → started cleanly, `GET /api/health` returned `{"status":"ok","service":"gameforge-api"}` (the exact response `start.bat`'s own health-poll expects).
- Frontend: `npm run dev -- --port 5173` → started cleanly, served `index.html` with the corrected favicon link, zero import/module-resolution errors in the Vite log.

No missing-file errors, no import errors, no asset-resolution errors. `start.bat` itself was not modified (cleanup did not break anything it depends on).

# Browser Smoke Test

Real headless-Chromium session (Playwright) against the live dev servers, 1440×900, with console/network error listeners attached throughout:

| Page | Result | Regression-specific check |
|---|---|---|
| Home | **PASS** — hero, search bar, suggestion chips, features grid all render | Favicon request confirmed `200` (was `404` pre-fix) |
| Discovery (search flow) | **PASS** (auth flow), search itself returned zero results this run | Pre-existing `FS-034` dev-proxy memory-pressure issue (system free RAM was 1.07GB/7.68GB during this run — same signature as the already-documented, already-investigated finding), unrelated to any deleted file; discovery result cards live in `HomePage.tsx`'s own inline markup, never touched |
| Builder | **PASS** | Range controls (Procedural Visual Density, Physics Complexity) render and are interactive; scanline preview panel (`.scan-sweep`) renders correctly in the Live Preview panel; Compile Scene button and its hover glow intact — screenshot-verified pixel-identical in layout to the pre-cleanup baseline |
| Dashboard | **PASS** | Empty-state project-card section renders correctly via its inline markup (not the deleted `ProjectCard.tsx`/`StatusBadge.tsx`) |
| Profile | **PASS** | Creator Progression bar, all 8 Milestone cards, Game DNA section all render correctly with full arcade-border/glow styling — screenshot-verified |
| Success/Error status (redirect-guarded) | **PASS** | Correctly redirect to `/build` with no active build state, as designed |
| No-Matches | **PASS** | Terminal header, alert, action buttons, both suggestion cards render |
| Game Details modal | Not reached this run | Blocked by the same Discovery-search proxy flakiness above (no results to open a details modal from) — not a deletion regression; this modal (`GameDetailsModal.tsx`) was never touched |

**Console/network audit**: zero console errors or failed asset/CSS/JS requests attributable to the cleanup. The only console errors present were `502`s on `/api/*` calls, matching the pre-existing, already-investigated, already-documented `FS-034` environmental finding — confirmed via a fresh memory check during this exact test run (1.07GB free of 7.68GB, same range as the original investigation).

---

# Before / After Inventory

| | Count |
|---|---|
| Tracked files before cleanup | 294 |
| Deleted | 12 |
| Also changed (not counted as deletions) | `index.html` (favicon href fix), `TASK.md` (ledger), this doc (new) |
| Tracked files after cleanup, before this commit | 282 (`git ls-files \| wc -l`, confirms 294−12 exactly) |
| Tracked files after this commit | 283 (282 + `REPOSITORY_HYGIENE_AUDIT.md` newly tracked) |

The +1 for this doc itself is expected and explained — it's the audit deliverable, not an unaccounted discrepancy. No other count mismatch occurred.

# Remaining Repository Debt (not addressed by this audit's deletion scope)

1. 15 documentation staleness findings above, most notably `README.md`'s and `backend/README.md`'s "not yet implemented"/"Phase B5" claims and `docs/15-CURRENT-STATUS.md` being 2 days and 6 major workstreams out of date.
2. Two stale git branches (`master`, `backup-before-cleanup`) sharing no history with the active `fresh-main` branch.
3. `.env.example` missing documentation for 5 live, used settings fields (IGDB + Groq/generic-provider fallback).
4. Minor duplicate ownership-check pattern in `build_service.py` (4× repeated post-fetch compare, could be one helper) — cosmetic, not a bug.

None of these are part of the file-deletion cleanup this audit was scoped to action; listed for visibility.

---

# Final Verdict

**Audit and approved cleanup both complete.** 12 HIGH-confidence dead frontend files deleted, 1 broken favicon reference fixed, all independently re-verified as zero-reference immediately before deletion. Full regression clean (335/335 backend tests, 0 TypeScript errors, 0 lint errors/warnings, production build succeeds, single Alembic head), `start.bat`'s two components (backend + frontend) verified working end-to-end, and a real browser smoke test across all 7 routes plus Builder/Dashboard/Profile-specific regression checks showed no missing components, no broken CSS/animation, no blank pages, and no console errors attributable to the cleanup (the only console errors observed were the pre-existing, already-documented `FS-034` dev-proxy memory-pressure issue, reconfirmed via a fresh memory check during this exact test run).

Zero backend dead code, zero unused dependencies (frontend or backend), zero migration issues, zero accidentally-committed scratch/temp artifacts, and **zero uncertain candidates were touched** — `public/icons.svg`, all `backend/scripts/*.py`, `test_generation_live.py`, the `AI_PROVIDER` config field, both `evaluate_discovery*.py` scripts, all historical audit reports, all Alembic migrations, `stitch_gameforge_ai/`, and `DESIGN.md` remain exactly as they were, exactly as scoped.

Everything else surfaced (15 documentation staleness findings, R&D script retention questions, one undocumented manual test script, one unread config field, one borderline asset) remains a judgment call flagged for your decision, not auto-actioned — consistent with the brief's instruction not to chase a "zero unused files" result and not to blindly delete.
