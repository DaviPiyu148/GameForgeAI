# GameForge AI — Documentation Index

This directory is the primary documentation home for GameForge AI. Use this file as
your navigation entry point for all project, product, architecture, engineering,
and historical documentation.

---

## Documentation Hierarchy

```
Repository root             — canonical controls, constitution, ledger
decisions/                  — durable architectural decision records
docs/01–15                  — canonical product and engineering documentation
docs/architecture/          — deep-dive architecture references
docs/product/               — product experience definitions and quality targets
docs/engineering/           — implementation plans and technical notes
docs/archive/               — historical audits, QA reports, and obsolete plans
references/stitch/          — reference UI prototype exports from Stitch
```

---

## 1. Canonical Authority (Repository Root)

These files at the repository root are the **source of truth** for their topics.

| File | Purpose |
|------|---------|
| [`AGENTS.md`](../AGENTS.md) | Engineering and AI-agent constitution — rules for all agents working in this repo |
| [`README.md`](../README.md) | Repository entry point and orientation |
| [`PRODUCT.md`](../PRODUCT.md) | Product definition and vision |
| [`DESIGN.md`](../DESIGN.md) | Design system reference |
| [`SETUP.md`](../SETUP.md) | Developer setup guide |
| [`TASK.md`](../TASK.md) | Current active task execution ledger |

---

## 2. Architecture Decision Records (`decisions/`)

Durable decisions that are not subject to revision without a new ADR.

| ADR | Decision |
|-----|---------|
| [`ADR-001`](../decisions/ADR-001-FRONTEND-STACK.md) | Frontend stack (React + Vite + TypeScript) |
| [`ADR-002`](../decisions/ADR-002-BACKEND-STACK.md) | Backend stack (FastAPI + SQLAlchemy + SQLite) |
| [`ADR-003`](../decisions/ADR-003-GAME-DSL.md) | Game DSL schema and validation pipeline |
| [`ADR-004`](../decisions/ADR-004-BUILD-JOBS.md) | Build job system and SSE broadcaster architecture |
| [`ADR-005`](../decisions/ADR-005-DISCOVERY-ARCHITECTURE.md) | Discovery engine architecture |
| [`ADR-006`](../decisions/ADR-006-HOSTED-LLM-PROVIDER.md) | Hosted LLM provider integration |
| [`ADR-007`](../decisions/ADR-007-AUTHENTICATION-AND-OWNERSHIP.md) | Authentication and ownership model |

---

## 3. Canonical Documentation (`docs/01–15`)

Numbered documents are the **current source of truth** for their topics.
They are maintained as the project evolves.

| Doc | Topic |
|-----|-------|
| [`01-PROJECT.md`](01-PROJECT.md) | Project overview and goals |
| [`02-PRODUCT-SPEC.md`](02-PRODUCT-SPEC.md) | Product specification |
| [`03-TECH-STACK.md`](03-TECH-STACK.md) | Technology stack choices |
| [`04-SYSTEM-ARCHITECTURE.md`](04-SYSTEM-ARCHITECTURE.md) | Overall system architecture |
| [`05-FRONTEND-ARCHITECTURE.md`](05-FRONTEND-ARCHITECTURE.md) | Frontend architecture |
| [`06-BACKEND-ARCHITECTURE.md`](06-BACKEND-ARCHITECTURE.md) | Backend architecture, SSE broadcaster constraints |
| [`07-DATA-MODEL.md`](07-DATA-MODEL.md) | Data model and schema |
| [`08-API-CONTRACT.md`](08-API-CONTRACT.md) | API contract reference |
| [`09-AI-GAME-GENERATION.md`](09-AI-GAME-GENERATION.md) | AI game generation pipeline |
| [`10-DISCOVERY-ENGINE.md`](10-DISCOVERY-ENGINE.md) | Discovery and search engine |
| [`11-IMPLEMENTATION-PHASES.md`](11-IMPLEMENTATION-PHASES.md) | Implementation phase roadmap |
| [`12-TESTING-QA.md`](12-TESTING-QA.md) | Testing strategy and QA |
| [`13-SECURITY.md`](13-SECURITY.md) | Security model and controls |
| [`14-DEPLOYMENT.md`](14-DEPLOYMENT.md) | Deployment guide and operational procedures |
| [`15-CURRENT-STATUS.md`](15-CURRENT-STATUS.md) | Current system status |

---

## 4. Architecture References (`docs/architecture/`)

Deep-dive architecture documents for specific subsystems.

| File | Topic |
|------|-------|
| [`AI_PROVIDER_ARCHITECTURE.md`](architecture/AI_PROVIDER_ARCHITECTURE.md) | AI provider abstraction, failover, and key rotation |
| [`UI_MOTION_SYSTEM.md`](architecture/UI_MOTION_SYSTEM.md) | Frontend motion design system |

---

## 5. Product Experience Documentation (`docs/product/`)

Product experience definitions, quality targets, and experience benchmarks.
These inform development and QA; the numbered docs (`02`, `09`, `10`) remain
the canonical specifications.

| File | Topic |
|------|-------|
| [`DISCOVERY_EXPERIENCE_V2.md`](product/DISCOVERY_EXPERIENCE_V2.md) | Discovery experience v2 definition |
| [`DISCOVERY_INTELLIGENCE_V1.md`](product/DISCOVERY_INTELLIGENCE_V1.md) | Discovery intelligence behavior |
| [`GAMEPLAY_EXPERIENCE_V1.md`](product/GAMEPLAY_EXPERIENCE_V1.md) | Gameplay experience v1 targets |
| [`GAME_GENERATION_V2.md`](product/GAME_GENERATION_V2.md) | Game generation v2 quality goals |
| [`GAME_RUNTIME_EXPERIENCE_V1.md`](product/GAME_RUNTIME_EXPERIENCE_V1.md) | Runtime experience definition |
| [`GENERATION_OUTPUT_QUALITY_V3.md`](product/GENERATION_OUTPUT_QUALITY_V3.md) | Generation output quality targets v3 |
| [`GENERATION_RESILIENCE.md`](product/GENERATION_RESILIENCE.md) | Generation resilience and fallback behavior |
| [`GENERATION_RUNTIME_INTEGRATION.md`](product/GENERATION_RUNTIME_INTEGRATION.md) | Generation-to-runtime integration contract |

---

## 6. Engineering Plans and Notes (`docs/engineering/`)

Implementation plans, technical notes, and engineering change records.

| File | Topic |
|------|-------|
| [`GEMINI_INTERACTIONS_MIGRATION_PLAN_V1.md`](engineering/GEMINI_INTERACTIONS_MIGRATION_PLAN_V1.md) | Migration plan for Gemini Interactions API |
| [`MODERN_WEB_POLISH_V1_PLAN.md`](engineering/MODERN_WEB_POLISH_V1_PLAN.md) | Modern web polish implementation plan |
| [`TOAST_RENDER_PHASE_FIX_V1.md`](engineering/TOAST_RENDER_PHASE_FIX_V1.md) | Toast render-phase fix technical note |

---

## 7. Archive (`docs/archive/`)

Historical evidence — QA reports, browser audits, accessibility audits, remediation
plans, and operational investigations. These are preserved for forensic and
historical reference. **They do not represent current system state.**

When a historical report conflicts with a numbered canonical document (`01–15`),
the numbered document is authoritative.

| File | Classification |
|------|---------------|
| [`ACCESSIBILITY_AUDIT_V1.md`](archive/ACCESSIBILITY_AUDIT_V1.md) | Audit — accessibility |
| [`ACCESSIBILITY_REMEDIATION_PLAN_V1.md`](archive/ACCESSIBILITY_REMEDIATION_PLAN_V1.md) | Plan — accessibility remediation |
| [`BROWSER_COMPREHENSIVE_QA_V4.md`](archive/BROWSER_COMPREHENSIVE_QA_V4.md) | QA report — browser comprehensive |
| [`BROWSER_E2E_TEST_REPORT.md`](archive/BROWSER_E2E_TEST_REPORT.md) | QA report — browser end-to-end |
| [`BROWSER_PRODUCT_AUDIT_V2.md`](archive/BROWSER_PRODUCT_AUDIT_V2.md) | Audit — browser product v2 |
| [`BROWSER_PRODUCT_REMEDIATION_V1.md`](archive/BROWSER_PRODUCT_REMEDIATION_V1.md) | Plan — browser product remediation |
| [`DIRECT_API_BROWSER_SMOKE_V1.md`](archive/DIRECT_API_BROWSER_SMOKE_V1.md) | QA report — direct API smoke test |
| [`DISCOVERY_EXPERIENCE_AUDIT.md`](archive/DISCOVERY_EXPERIENCE_AUDIT.md) | Audit — discovery experience |
| [`DOCUMENTATION_REFRESH_REPORT.md`](archive/DOCUMENTATION_REFRESH_REPORT.md) | Report — documentation refresh |
| [`DYNAMIC_SOURCE_OF_TRUTH_AUDIT.md`](archive/DYNAMIC_SOURCE_OF_TRUTH_AUDIT.md) | Audit — dynamic source of truth |
| [`FORENSIC_REVIEW_REPORT.md`](archive/FORENSIC_REVIEW_REPORT.md) | Report — forensic review |
| [`FULL_STACK_OPERATIONAL_AUDIT.md`](archive/FULL_STACK_OPERATIONAL_AUDIT.md) | Audit — full stack operational |
| [`GAMEPLAY_EXPERIENCE_AUDIT.md`](archive/GAMEPLAY_EXPERIENCE_AUDIT.md) | Audit — gameplay experience |
| [`GENERATION_OUTPUT_AUDIT.md`](archive/GENERATION_OUTPUT_AUDIT.md) | Audit — generation output |
| [`GENERATION_RUNTIME_AUDIT.md`](archive/GENERATION_RUNTIME_AUDIT.md) | Audit — generation runtime |
| [`HARDCODED_LITERAL_AUDIT.md`](archive/HARDCODED_LITERAL_AUDIT.md) | Audit — hardcoded literals |
| [`REPOSITORY_HYGIENE_AUDIT.md`](archive/REPOSITORY_HYGIENE_AUDIT.md) | Audit — repository hygiene |
| [`RUNTIME_VISUAL_AUDIT.md`](archive/RUNTIME_VISUAL_AUDIT.md) | Audit — runtime visual |
| [`SMALL_PRODUCT_FIXES_V2.md`](archive/SMALL_PRODUCT_FIXES_V2.md) | Plan — small product fixes v2 |
| [`UI_COPY_AUDIT.md`](archive/UI_COPY_AUDIT.md) | Audit — UI copy |

---

## 8. Backend Scripts (`backend/scripts/`)

Operational and research scripts are organized under `backend/scripts/`:

```
backend/scripts/
├── bootstrap/      — environment setup, index building, catalog ingestion
├── maintenance/    — dev seeding and maintenance utilities
├── evaluation/     — formal evaluation scripts (part of engineering workflow)
└── research/
    ├── audits/         — discovery/ranking audits
    ├── benchmarks/     — production and mode benchmarks
    ├── experiments/    — RRF, candidate pool, ranker experiments
    ├── diagnostics/    — inspection and diagnostic utilities
    ├── validations/    — statistical and shadow validation runs
    └── tests/          — quick ad-hoc query verification scripts
```

See [`backend/README.md`](../backend/README.md) for usage instructions.

---

## 9. Design References (`references/stitch/`)

Original UI prototypes and visual design references exported from Stitch are preserved under `references/stitch/`:
- Screen captures (`screen.png`) and prototype HTML (`code.html`) for home, builder, dashboard, profile, and discovery states.
- Original `obsidian_forge/DESIGN.md` design spec (the consolidated root [`DESIGN.md`](../DESIGN.md) document details the shipped deviations and current design system).

---

## Classification Guide

When contributing documentation, use this classification:

| Type | Location |
|------|---------|
| Engineering constitution / rules | `AGENTS.md` (root) |
| Durable architectural decision | `decisions/ADR-NNN-*.md` |
| Current product / engineering spec | `docs/01–15-*.md` |
| Deep-dive architecture reference | `docs/architecture/` |
| Product experience / quality targets | `docs/product/` |
| Implementation plan or technical note | `docs/engineering/` |
| Historical audit, QA report, or closed plan | `docs/archive/` |
