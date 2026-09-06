# GameForge AI — Documentation Architecture & Index

This directory is the primary documentation home for GameForge AI. Use this index as the navigation entry point for all product, architecture, engineering, operational, and archived documentation.

---

## 1. Documentation Authority Model

When evaluating requirements, architecture, or system state, consult sources in this priority order:

| Source | Role & Authority |
| :--- | :--- |
| **`AGENTS.md`** (root) | **Engineering & AI Agent Constitution** — Mandatory engineering rules and invariants. |
| **`TASK.md`** (root) | **Task Execution Ledger** — Current active task, subtask tracking, and verification records. |
| **`decisions/`** | **Architectural Decision Records (ADRs)** — Durable, accepted architectural standards. |
| **`docs/`** | **Canonical System & Product Truth** — Current specifications, architecture, and engineering standards. |
| **Source Code** | **Actual Implementation** — Verified against active contracts and schemas. |
| **Test Suites** | **Executable Verification** — Automated proof of system behavior. |
| **`docs/archive/`** | **Historical Evidence** — Completed audits, past QA reports, and closed migration plans. |
| **`references/`** | **Reference Artifacts** — Upstream Stitch UI exports and design captures (non-runtime). |

---

## 2. Canonical Authority (Repository Root)

These control documents at the repository root define the project's vision, design, rules, and setup:

| File | Purpose |
| :--- | :--- |
| [`AGENTS.md`](../AGENTS.md) | AI development constitution and engineering rules for all agents |
| [`README.md`](../README.md) | Repository onboarding, orientation, and development quickstart |
| [`PRODUCT.md`](../PRODUCT.md) | High-level product vision and user journey definition |
| [`DESIGN.md`](../DESIGN.md) | Visual design system source of truth (colors, typography, effects, motion, toasts) |
| [`SETUP.md`](../SETUP.md) | Comprehensive local development, virtualenv, database, and launcher setup |
| [`TASK.md`](../TASK.md) | Active task execution ledger and milestone evidence |

---

## 3. Architecture Decision Records (`decisions/`)

Durable architectural decisions that govern system standards:

| ADR | Decision Title | Scope |
| :--- | :--- | :--- |
| [`ADR-001`](../decisions/ADR-001-FRONTEND-STACK.md) | Frontend Stack | React 18 + Vite + TypeScript + Tailwind CSS |
| [`ADR-002`](../decisions/ADR-002-BACKEND-STACK.md) | Backend Stack | FastAPI modular monolith + SQLAlchemy + SQLite + Alembic |
| [`ADR-003`](../decisions/ADR-003-GAME-DSL.md) | Game DSL Schema | Strict Pydantic schema validation & versioning |
| [`ADR-004`](../decisions/ADR-004-BUILD-JOBS.md) | Build Jobs & SSE | Async background build pipeline & event streaming |
| [`ADR-005`](../decisions/ADR-005-DISCOVERY-ARCHITECTURE.md) | Discovery Architecture | Hybrid dense semantic (FAISS) + lexical retrieval |
| [`ADR-006`](../decisions/ADR-006-HOSTED-LLM-PROVIDER.md) | Hosted LLM Provider | Provider abstraction & zero client-side credentials |
| [`ADR-007`](../decisions/ADR-007-AUTHENTICATION-AND-OWNERSHIP.md) | Auth & Ownership | JWT + Argon2, per-user project isolation & IDOR defense |
| [`ADR-008`](../decisions/ADR-008-GEMINI-INTERACTIONS-AND-FAILOVER.md) | Gemini Interactions & Failover | Sequential credential failover, model chains & deadline budgeting |

---

## 4. Canonical Product Documentation (`docs/product/`)

Defines product requirements, capabilities, and functional specifications:

| Document | Topic & Scope |
| :--- | :--- |
| [`project.md`](product/project.md) | Project mission, target audience, core loop, and architectural boundaries |
| [`product-spec.md`](product/product-spec.md) | Detailed user stories, primary routes, builder controls, and studio experience |

---

## 5. Canonical Architecture Documentation (`docs/architecture/`)

Detailed architectural specifications for all backend, frontend, runtime, and AI subsystems:

| Document | Subsystem & Scope |
| :--- | :--- |
| [`tech-stack.md`](architecture/tech-stack.md) | Full-stack technology choices, runtime dependencies, and toolchain |
| [`system.md`](architecture/system.md) | High-level system architecture, data flow, and trust boundaries |
| [`frontend.md`](architecture/frontend.md) | React component hierarchy, routing, state management, and HUD layout |
| [`backend.md`](architecture/backend.md) | FastAPI service layer, repositories, SSE broadcaster, and single-worker boundary |
| [`data-model.md`](architecture/data-model.md) | Database entities, relationships, indexes, and Alembic migration policies |
| [`api-contract.md`](architecture/api-contract.md) | REST API endpoints, request/response schemas, error formats, and SSE events |
| [`ai-game-generation.md`](architecture/ai-game-generation.md) | 10-stage compiler pipeline, 7-axis quality gates, design patterns & resilience |
| [`discovery-engine.md`](architecture/discovery-engine.md) | Hybrid FAISS+lexical search, ranking, 3-layer catalog metadata, and Game DNA |
| [`ai-provider.md`](architecture/ai-provider.md) | Sequential credential failover, task model chains, error classification & deadlines |
| [`runtime-and-gameplay.md`](architecture/runtime-and-gameplay.md) | Phaser 3.88 runtime, visual profiles, procedural textures, VFX & gameplay beats |

---

## 6. Canonical Engineering & QA Documentation (`docs/engineering/`)

Engineering processes, quality assurance strategies, security posture, and accessibility:

| Document | Topic & Scope |
| :--- | :--- |
| [`roadmap.md`](engineering/roadmap.md) | Implementation roadmap, completed milestones, current phase, and gate criteria |
| [`testing-qa.md`](engineering/testing-qa.md) | Multi-tier testing strategy (unit, integration, regression, benchmarks) |
| [`security.md`](engineering/security.md) | Threat modeling, LLM safety boundaries, auth hardening, and secret handling |
| [`accessibility.md`](engineering/accessibility.md) | WCAG 2.1 AA compliance, modal focus trapping, reduced motion, and landmarks |

---

## 7. Canonical Operational Documentation (`docs/operations/`)

Deployment topologies, environment configuration, and operational procedures:

| Document | Topic & Scope |
| :--- | :--- |
| [`deployment.md`](operations/deployment.md) | Single-worker topology, environment variables, migration execution, and health checks |

---

## 8. Living Status (`docs/status/`)

| Document | Topic & Scope |
| :--- | :--- |
| [`current-status.md`](status/current-status.md) | Living snapshot of implementation completion, frozen subsystems, and current limits |

---

## 9. Historical Archive (`docs/archive/`)

Preserved forensic records, completed audits, past QA reports, and closed implementation plans. **These represent historical snapshots, not current system truth.**

### 9.1 Audits (`docs/archive/audits/`)
- [`ACCESSIBILITY_AUDIT_V1.md`](archive/audits/ACCESSIBILITY_AUDIT_V1.md) — Static AST accessibility audit
- [`DISCOVERY_EXPERIENCE_AUDIT.md`](archive/audits/DISCOVERY_EXPERIENCE_AUDIT.md) — Discovery UI & search audit
- [`DOCUMENTATION_REFRESH_REPORT.md`](archive/audits/DOCUMENTATION_REFRESH_REPORT.md) — Documentation structure review
- [`DYNAMIC_SOURCE_OF_TRUTH_AUDIT.md`](archive/audits/DYNAMIC_SOURCE_OF_TRUTH_AUDIT.md) — Dynamic vs static source audit
- [`FORENSIC_REVIEW_REPORT.md`](archive/audits/FORENSIC_REVIEW_REPORT.md) — Comprehensive forensic review
- [`FULL_STACK_OPERATIONAL_AUDIT.md`](archive/audits/FULL_STACK_OPERATIONAL_AUDIT.md) — Operational readiness audit
- [`GAMEPLAY_EXPERIENCE_AUDIT.md`](archive/audits/GAMEPLAY_EXPERIENCE_AUDIT.md) — Gameplay pacing and feel audit
- [`GENERATION_OUTPUT_AUDIT.md`](archive/audits/GENERATION_OUTPUT_AUDIT.md) — Generated game database audit
- [`GENERATION_RUNTIME_AUDIT.md`](archive/audits/GENERATION_RUNTIME_AUDIT.md) — Runtime compilation audit
- [`HARDCODED_LITERAL_AUDIT.md`](archive/audits/HARDCODED_LITERAL_AUDIT.md) — Hardcoded values scan
- [`REPOSITORY_HYGIENE_AUDIT.md`](archive/audits/REPOSITORY_HYGIENE_AUDIT.md) — Repository structure & cleanliness audit
- [`RUNTIME_VISUAL_AUDIT.md`](archive/audits/RUNTIME_VISUAL_AUDIT.md) — Phaser graphical presentation audit
- [`UI_COPY_AUDIT.md`](archive/audits/UI_COPY_AUDIT.md) — UI copy and terminology audit

### 9.2 Browser QA Reports (`docs/archive/browser-qa/`)
- [`BROWSER_COMPREHENSIVE_QA_V4.md`](archive/browser-qa/BROWSER_COMPREHENSIVE_QA_V4.md) — Full browser QA walkthrough
- [`BROWSER_E2E_TEST_REPORT.md`](archive/browser-qa/BROWSER_E2E_TEST_REPORT.md) — End-to-end browser test report
- [`BROWSER_PRODUCT_AUDIT_V2.md`](archive/browser-qa/BROWSER_PRODUCT_AUDIT_V2.md) — Product flow QA audit
- [`DIRECT_API_BROWSER_SMOKE_V1.md`](archive/browser-qa/DIRECT_API_BROWSER_SMOKE_V1.md) — Direct API browser smoke test

### 9.3 Completed Remediations (`docs/archive/remediation/`)
- [`ACCESSIBILITY_REMEDIATION_PLAN_V1.md`](archive/remediation/ACCESSIBILITY_REMEDIATION_PLAN_V1.md) — Accessibility remediation plan
- [`BROWSER_PRODUCT_REMEDIATION_V1.md`](archive/remediation/BROWSER_PRODUCT_REMEDIATION_V1.md) — Product UI fixes
- [`SMALL_PRODUCT_FIXES_V2.md`](archive/remediation/SMALL_PRODUCT_FIXES_V2.md) — Small polish remediations
- [`TOAST_RENDER_PHASE_FIX_V1.md`](archive/remediation/TOAST_RENDER_PHASE_FIX_V1.md) — Toast lifecycle fix

### 9.4 Closed Plans & Historical Architecture (`docs/archive/plans/`)
- [`GEMINI_INTERACTIONS_MIGRATION_PLAN_V1.md`](archive/plans/GEMINI_INTERACTIONS_MIGRATION_PLAN_V1.md) — Original Interactions migration plan
- [`MODERN_WEB_POLISH_V1_PLAN.md`](archive/plans/MODERN_WEB_POLISH_V1_PLAN.md) — Frontend polish plan
- [`AI_PROVIDER_ARCHITECTURE.md`](archive/plans/AI_PROVIDER_ARCHITECTURE.md) — Superseded V2 provider plan
- [`UI_MOTION_SYSTEM.md`](archive/plans/UI_MOTION_SYSTEM.md) — Motion system specification (absorbed into `DESIGN.md`)

### 9.5 Historical Subsystem Milestones
- **Discovery**: [`DISCOVERY_EXPERIENCE_V2.md`](archive/discovery/DISCOVERY_EXPERIENCE_V2.md), [`DISCOVERY_INTELLIGENCE_V1.md`](archive/discovery/DISCOVERY_INTELLIGENCE_V1.md)
- **Generation**: [`GAME_GENERATION_V2.md`](archive/generation/GAME_GENERATION_V2.md), [`GENERATION_OUTPUT_QUALITY_V3.md`](archive/generation/GENERATION_OUTPUT_QUALITY_V3.md), [`GENERATION_RESILIENCE.md`](archive/generation/GENERATION_RESILIENCE.md), [`GENERATION_RUNTIME_INTEGRATION.md`](archive/generation/GENERATION_RUNTIME_INTEGRATION.md)
- **Gameplay**: [`GAME_RUNTIME_EXPERIENCE_V1.md`](archive/gameplay/GAME_RUNTIME_EXPERIENCE_V1.md), [`GAMEPLAY_EXPERIENCE_V1.md`](archive/gameplay/GAMEPLAY_EXPERIENCE_V1.md)

---

## 10. Non-Runtime Reference Material (`references/`)

Original visual prototypes, mockups, and screen exports from Stitch are preserved under `references/stitch/`:
- `references/stitch/obsidian_forge/DESIGN.md` — Initial Stitch design concept (historical)
- Screen captures (`screen.png`) and prototype HTML (`code.html`) for home, builder, dashboard, profile, and discovery views.
