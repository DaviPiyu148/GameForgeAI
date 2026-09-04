# 15 — Current Status

## Date
2026-09-04

## System Freeze Status
```text
DISCOVERY V1
= FROZEN

PERSONALIZATION V1
= FROZEN AT 25% EXPERIMENTAL EXPOSURE

NO FURTHER RANKING TUNING
UNLESS REAL ORGANIC DATA JUSTIFIES IT
```

## Current Phase
**Personalization V1 is FEATURE-COMPLETE and FROZEN AT 25% EXPERIMENTAL EXPOSURE** (`PERSONALIZATION_TREATMENT_PCT = 25`, mode lambdas: `DISCOVER = 0.05`, `HIDDEN_GEMS = 0.05`, `BEST_MATCH = 0.02`, `POPULAR = 0.00`). No further ranking or candidate-pool sweeps will be conducted unless organic production traffic warrants it.

**Next Milestone Active**: **Creator Loop: Discovery → Inspiration → Studio** (Transforming Discovery from a pure recommendation endpoint into a structured design input system by attaching games as structured inspiration DNA to active projects for Studio blueprint proposals).

**Phase 7 (AI Game Director) and Phase 8 (Monetization/BYOK) are NOT STARTED** — nothing in the codebase implements them; do not treat any document that mentions them as describing current behavior.

---

## Completed

| Workstream | Status |
|---|---|
| Backend foundation (B0-B7): FastAPI, SQLite/Alembic, Auth (JWT+Argon2), Discovery (FAISS), Phaser runtime, full frontend-backend integration | COMPLETE |
| Forensic security remediation (multiple rounds) | COMPLETE |
| Full-stack operational audit (`FULL_STACK_OPERATIONAL_AUDIT.md`) | COMPLETE |
| Discovery Visual Experience, Multilingual 2.1, Display Normalization 2.2 | COMPLETE |
| Discovery Intelligence V1 (Rich Intent, Negatives, Personalization, Diversity, Modes, Grounded Explanations) (`DISCOVERY_INTELLIGENCE_V1.md`) | COMPLETE |
| Game Generation Pipeline V2 (Depth, Design Quality, Capability Allowlist, Quality Gates, Evaluator) (`GAME_GENERATION_V2.md`) | COMPLETE |
| Generated Game Quality V3 (Real Output Improvement: Design Patterns, Composition Matrix, Palettes) (`GENERATION_OUTPUT_QUALITY_V3.md`) | COMPLETE |
| Game Runtime Experience V1 (Visual Identity, Game Feel, VFX, Props, HUD) (`GAME_RUNTIME_EXPERIENCE_V1.md`) | COMPLETE |
| Generation/Runtime Integration V1 (System Usage, Dead-Rule Detection, Active Loops) (`GENERATION_RUNTIME_INTEGRATION.md`) | COMPLETE |
| Gameplay Experience V1 (Beats, Pacing, Deadlock Detection, Failure Clarity) (`GAMEPLAY_EXPERIENCE_V1.md`) | COMPLETE |
| Discovery Experience V2 (Game DNA Onboarding, Reset, Comparison, Tuning, Mood Explorer) (`DISCOVERY_EXPERIENCE_V2.md`) | COMPLETE |
| Game DNA / behavioral personalization | COMPLETE |
| Personalization V1 (Developer Profile, Project Context Blending, Explanations, 25% Treatment Exposure) | COMPLETE (FROZEN AT 25%) |





| Creator Progression (server-authoritative XP, levels, milestones) | COMPLETE |
| AI Blueprint + Remix (Phase 4) | COMPLETE |
| Advanced Game Generation + Game Feel, multi-level campaigns, bounded boss/finale (Phase 5) | COMPLETE |
| Generalized Open World System V1 (Phase 6) | COMPLETE |
| Dynamic source-of-truth parity audit (`DYNAMIC_SOURCE_OF_TRUTH_AUDIT.md`) | COMPLETE |
| Browser E2E / parity verification (`BROWSER_E2E_TEST_REPORT.md`) | COMPLETE |
| Comprehensive security & penetration testing audit (`FULL_STACK_SECURITY_ASSESSMENT.md`) | COMPLETE |
| Hardcoded literal / override audit (`HARDCODED_LITERAL_AUDIT.md`) | COMPLETE |
| UI Motion & Special Effects System V1 (`UI_MOTION_SYSTEM.md`) | COMPLETE |
| Website Content & UI Copy Audit V1 (`UI_COPY_AUDIT.md`) | COMPLETE |
| Dev-proxy 502 investigation (FS-034, `FULL_STACK_OPERATIONAL_AUDIT.md`) | COMPLETE — classified KNOWN DEVELOPMENT-ONLY LIMITATION, not code-fixable |
| Full repository hygiene / dead-code cleanup (`REPOSITORY_HYGIENE_AUDIT.md`) | COMPLETE |
| Product Polish Sprint A (Project Management, Generated Covers, Builder Presets) | COMPLETE |
| Game Generation Hardening V1 (Deterministic Normalization, Repair Timeout, Resilience) (`GENERATION_RESILIENCE.md`) | COMPLETE |
| AI Provider Architecture V2 (Sequential Failover, Gemini 3 Routing, Model Fallback) (`AI_PROVIDER_ARCHITECTURE.md`) | COMPLETE |
| Small Product Fixes & Reliability Polish V2 (Blueprint Recovery, Persistent Build Logs, Fullscreen API, Account Settings, Builder Design Preview) | COMPLETE |
| Browser Audit Remediation V1 (API Transport Normalization, Auth Deduplication, Validation Error JSON Serialization, Discovery Stale Response Guard, Web Speech Voice Input, Modal Portal & Scroll Lock Migration, InfoModal Tabbed Documentation, Copy Output Actions) (`BROWSER_PRODUCT_REMEDIATION_V1.md`) | COMPLETE |
| Deployment & Product Hygiene Fix V1 (Deployment-Safe Swagger URL `getSwaggerDocsUrl()`, Standalone Documentation Pages `#/documentation`, `#/api-access`, `#/community`, `#/support`, `#/privacy`, Footer Navigation, Test Credential Isolation from Production Code) | COMPLETE |
| Direct API Transport Browser Smoke V1 (Direct-Development Origin Transport Verification & FIND-BROWSER-001 Remediation) (`DIRECT_API_BROWSER_SMOKE_V1.md`, `TOAST_RENDER_PHASE_FIX_V1.md`) | COMPLETE |
| Creator Loop V1 (Discovery Inspiration → Builder Context → Playtest XP → Visual AI Critique Pulse → Quick Remix & Evolution → Game DNA Discover More Seed) | COMPLETE |
| Project Studio V1 (Persistent Project Workspace, 3-Tab Architecture, Read-Only Historical Playback, Forward Version Restore, Stale Recommendation Guard) (`PROJECT_STUDIO_V1_PLAN.md`) | COMPLETE |
| Self-Bootstrapping Local Launcher V1 (10-Stage Windows Orchestrator, Python/Node Winget Detection, Lockfile Hash Sync, SentenceTransformer & FAISS Vector Index Self-Bootstrap, Signature-Verified Port Safety) | COMPLETE |
| Living documentation refresh (this pass) | COMPLETE |

---

## Current Verification (as of Self-Bootstrapping Local Launcher V1)

- **Backend tests**: 434/434 passing (100% pass rate across all suites via pytest).
- **TypeScript build & type check**: PASS (`npx tsc --noEmit` and `npm run build` completed with zero errors).
- **Frontend linter**: PASS (`npx oxlint` passed with 0 errors and 0 warnings across 72 files).
- **Discovery seed pure unit tests**: 7/7 passing (`npx tsx src/utils/__tests__/discovery.test.ts`).
- **Progression toasts unit tests**: 11/11 passing (`npx tsx src/services/__tests__/progressionToasts.test.ts`).
- **URL normalization & direct transport unit tests**: 34/34 passing (`npx tsx src/services/__tests__/urlUtils.test.ts`).
- **Production build**: succeeds (`npm run build`).
- **Technical Refinement 1 (Version-Aware Stale Guard)**: Analysis staleness evaluates against `activeVersion.created_at` timestamp rather than `project.updatedAt`, ensuring project renames do not invalidate recommendations while version updates flag stale analysis.
- **Technical Refinement 2 (Restore Concurrency Safety)**: `ProjectVersion` enforces `UniqueConstraint("project_id", "version_number")`, and `restore_project_version` utilizes transactional collision retry proven via multi-threaded test.
- **Zero-AI studio browsing audit**: Verified browsing tabs, viewing blueprint, inspecting versions, and historical playback execute client-side / cache with zero AI quota consumption.
- **Single-invocation progress refresh audit**: Verified exactly 1 `refreshProgress()` per completed playtest/remix/improvement/restore action.
- **Browser verification**: Explicitly NOT PERFORMED for this milestone pending user authorization (`BROWSER TESTING: NOT PERFORMED`).

- **Dev API Transport (Elimination of FS-034 Dev Proxy Dependency)**: Local development (`start.bat`) automatically supplies `VITE_API_URL=http://127.0.0.1:<BACKEND_PORT>` and `CORS_ORIGINS` when not explicitly set, routing browser REST and SSE traffic directly to FastAPI. This bypasses the development-only Vite proxy hop and permanently eliminates intermittent `ECONNRESET` socket drops in local dev. The Vite proxy remains in place only as a backward-compatible fallback for environments without `VITE_API_URL`.

---

## Current Architecture

React 19 + TypeScript + Vite + Tailwind CSS v4 frontend (HashRouter, single `AppContext`, embedded Phaser 3.88.2 runtime) talking over REST + SSE to a FastAPI modular-monolith backend (SQLAlchemy/SQLite/Alembic, JWT+Argon2 auth, hybrid FAISS+lexical Discovery, Google Gemini as the hosted AI provider with a Groq fallback path). See `docs/04-SYSTEM-ARCHITECTURE.md`, `docs/05-FRONTEND-ARCHITECTURE.md`, and `docs/06-BACKEND-ARCHITECTURE.md` for full detail — all three are current as of this pass.

## Current Repository State

- Tracked files: 283 (after the repository hygiene cleanup removed 12 confirmed-dead frontend files and this documentation pass added/updated the files described below).
- No known HIGH-confidence dead source files remain (see `REPOSITORY_HYGIENE_AUDIT.md`).
- No unused dependencies, frontend or backend.
- Single Alembic migration head: `bc9ae398f146`.
- A handful of LOW/MEDIUM-confidence items remain intentionally deferred (not dead, not urgent): a few historical Discovery R&D scripts in `backend/scripts/`, one undocumented manual smoke-test script (`test_generation_live.py`), one unread `AI_PROVIDER` config field, and `gameforge-ai/public/icons.svg`'s uncertain future-use status. None of these affect current functionality.

---

## Roadmap Status

| Phase | Status |
|---|---|
| Frontend F0-F5 | COMPLETE |
| Backend B0-B7 | COMPLETE |
| Discovery Engine 2.0-2.2 | COMPLETE |
| Game Generation V2 (G1-G16) | COMPLETE |
| Phase 4 — Blueprint + Remix | COMPLETE |
| Phase 5 — Scale Tiers, Boss/Finale, Multi-Level Rendering | COMPLETE |
| Phase 6 — Generalized Open World System V1 | COMPLETE |
| Security / operational / documentation audits (this cycle) | COMPLETE |
| **Phase 7 — AI Game Director** (adaptive difficulty/narrative layer) | **NOT STARTED** |
| **Phase 8 — Monetization / BYOK** (bring-your-own-key provider selection) | **NOT STARTED** |
| Production deployment hardening (observability, multi-worker rate limiting, etc.) | **NOT STARTED** |

## Deferred (Genuinely Future, Not Implemented)

- **Phase 7 — AI Game Director**: no code, schema, or endpoint for this exists anywhere in the repository. Do not describe it as in-progress.
- **Phase 8 — Monetization / BYOK**: same — not started.
- **Production deployment**: `docs/14-DEPLOYMENT.md` describes the plan; nothing has been deployed. The current in-process rate limiter and SSE broadcaster are explicitly single-worker-only by design (see `docs/06-BACKEND-ARCHITECTURE.md`) — this is correct for the current `start.bat`-launched single-uvicorn-worker deployment, but would need revisiting before any multi-worker production deployment.
- Graphical minimap, procedural per-theme texture packs, multi-phase boss AI beyond one threshold bump, a separate World/Area sub-model — all explicitly out of scope per the Phase 5/6 design decisions, not oversights.

## Known Limitations

- **FS-034 / FS-020** (dev-proxy 502s under memory pressure): see "Current Verification" above. Development-host-specific, not a code defect, not reproducible in production.
- **Single-worker assumption**: the in-process `BuildEventBroadcaster` and `SlidingWindowRateLimiter` are correct today (one uvicorn worker via `start.bat`) but would silently misbehave under multiple workers — documented risk, not an active bug.
- **`GET /api/health`** is a pure liveness probe with zero dependency checks (no DB/AI/FAISS reachability) — by design, not a defect; don't infer deeper health from it.
