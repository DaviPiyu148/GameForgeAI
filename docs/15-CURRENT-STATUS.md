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

### Current Phase
**Creator Loop & Final UI/UX Visual QA are FEATURE-COMPLETE and VALIDATED.**
All components across Discovery, Game Details, Saved Discoveries, Studio Tabs, Deterministic Synthesis, Diff Review, and Version History have completed rigorous UI/UX interaction and visual auditing with zero critical defects, verified 1024x768 responsive layout safety, and clean console hygiene.

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
| Creator Loop: Discovery → Inspiration → Studio (Steps 1–7: Game DNA, Persistence, Deck, Deterministic Synthesis, Blueprint Apply, Prototype Build, Playtest Analysis & Remix) | COMPLETE |
| Self-Bootstrapping Local Launcher V1 (10-Stage Windows Orchestrator, Python/Node Winget Detection, Lockfile Hash Sync, SentenceTransformer & FAISS Vector Index Self-Bootstrap, Signature-Verified Port Safety) | COMPLETE |
| Final Browser QA & Real Developer Usability Validation (5 Prototype Builds, >60s Live Gameplay, Conflict Diffing, Forward Restore, 0 Console Errors) | COMPLETE |
| Final UI/UX Visual QA, Interaction Audit & Documentation Cleanup (45 controls inspected, 42 exercised PASS, zero horizontal overflow at 1024x768, typography consistency) | COMPLETE |
| Living documentation refresh (this pass) | COMPLETE |
| Exhaustive Browser QA, Interaction, Visual, Route & Existing-Prototype Validation (12 routes visited, 31 mandatory items verified in live browser, existing prototype runtime tested, zero new builds triggered, single Game DNA & border seam verified, responsive viewports 1440/1024/768/375) | COMPLETE |
| Feature Card Interactive Micro-Animations Refinement (All 3 icons stationary at rest and strictly hover-animated: authentic Material Symbol skull with rotating cogwheel on hover, arrow moving towards target goal on hover, and outline bonfire with dancing flames/rising sparks on hover, zero square box artifacts) | COMPLETE |

---

## Current Verification (as of Exhaustive Browser QA & Prototype Validation)

- **Backend tests**: 627/627 passing across all suites via pytest in 189.29s (100% pass rate).
- **TypeScript build & type check**: PASS (`npx tsc --noEmit` and `npm run build` completed with zero errors in 1.86s).
- **Frontend linter**: PASS (`npx oxlint` passed with 0 errors and 0 warnings across 86 files).
- **Frontend unit test suites**: 10/10 suites passing (131 tests across discovery, DNA, synergy, deck, synthesis proposal, apply, playtest remix, and build integration).
- **Production build**: succeeds (`npm run build`).
- **Interactive Control Inventory (Exhaustive Browser QA)**: 152 route-level elements discovered across all 12 routes; 8 non-operable informational/decorative elements excluded (4 governance cards on `#/privacy`, 2 status badges on `#/status/error`, 2 filter chips on `#/discover/no-matches`); 144 meaningful user controls audited: 136 safe controls clicked/exercised with PASS result; 4 expected disabled; 2 destructive controls safely tested (project rename/delete); 2 excluded generation CTAs (`COMPILE SCENE`, `POST /api/projects/{id}/compile`); 0 broken/unresolved controls (136 + 4 + 2 + 2 + 0 = 144; 144 + 8 = 152).
- **Viewport Responsiveness**: Desktop reference baseline (1440 × 900) verified with zero clipping, overflow, or unintended scrollbars; responsive layout verified down to 1024x768, 768x1024, and 375x812 with `hasHorizontalOverflow: false`.
- **Discovery Candidate Pool Distinction**:
  - `games_catalog.json`: Full raw offline Steam catalog containing ~120k titles (448MB).
  - `games_index.faiss` (`DiscoveryCandidatePool.POPULAR_20K`): Configured production vector index containing exactly **20,000** 384-dimensional dense vectors (`all-MiniLM-L6-v2`) prioritized strictly by total review count (`total_reviews`) and tag density (`len(tags)`). It is sorted by popularity and review volume (not quality-ranked; positive review sentiment is evaluated downstream during scoring, not during index slicing).
  - `games_index_reviewed_only.faiss` (`DiscoveryCandidatePool.REVIEWED_ONLY`): Secondary candidate pool containing exactly **87,890** vectors representing all titles with `total_reviews > 0` (i.e. games having at least 1 total review in the Steam catalog, rather than requiring positive sentiment).
  - Earlier informal references to "14,000+ title FAISS index" in draft documentation are officially superseded by the authoritative 20,000 active vector index count.
- **AI Generation vs Deterministic Synthesis Boundary**:
  - Step 4 deterministic design synthesis (`DeterministicSynthesisEngine`), Step 5 blueprint apply (`apply_inspiration_proposal`), diffing, synergy calculation, and all Studio UI operations are 100% deterministic, local, and consume zero LLM tokens.
  - Prototype compilation / game generation (`GameGenerationService`), on the other hand, contains an AI pipeline calling hosted LLMs (Gemini sequential fallback) with an offline deterministic fallback when LLM keys are absent. Authentication and game generation were explicitly excluded from this UI/UX test pass.

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
