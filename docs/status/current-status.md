# 15 — Current Status

## Date

2026-09-06

## Document Authority

This document is the volatile current-state snapshot.

When it conflicts with historical reports, use:

1. Current repository/source evidence
2. Actual verification output
3. Accepted ADRs for durable decisions
4. This status document
5. Historical reports

Refresh this document when major implementation state changes.

## System Freeze Status

```text
DISCOVERY V1
= FROZEN

PERSONALIZATION V1
= FROZEN AT 25% EXPERIMENTAL EXPOSURE

NO FURTHER RANKING TUNING
UNLESS REAL ORGANIC DATA JUSTIFIES IT
```

## Current Product State

The following product areas are documented as feature-complete:

- Backend B0–B7
- Discovery Engine 2.0–2.2
- Discovery Experience V2
- Personalization V1
- Game Generation V2
- Generated Game Quality V3
- Runtime Experience V2 (Stage Compilation, Archetype Matrix, Objective Engine, Rule Re-entrancy Guards, ADR-009)
- Generation/Runtime Integration V1
- Gameplay Experience V1
- Creator Progression
- Blueprint + Remix
- Scale tiers / bounded boss/finale
- Generalized Open World V1
- Project Studio V1
- Creator Loop
- Browser E2E / parity validation
- Security and repository hygiene audits
- UI/UX remediation and documentation cleanup
- Self-bootstrapping local launcher

## Not Started

- **Phase 7 — AI Game Director**
- **Phase 8 — Monetization / BYOK**
- **Production deployment hardening / internet-facing production rollout**

Do not describe these as partially implemented unless new code and evidence exists.

## Verification Snapshot

The most recent documented exhaustive runtime-hardening QA snapshot recorded:

- Runtime unit/integration tests: `55/55` passed (`npx tsx --test src/runtime/__tests__/*.test.ts`)
- Frontend services/utils unit tests: `131/131` passed (`npx tsx --test src/services/__tests__/*.test.ts src/utils/__tests__/*.test.ts`)
- TypeScript check: `npx tsc -b` PASS (0 errors)
- Frontend lint: `npm run lint` PASS (0 errors, 0 warnings across 109 files)
- Production frontend build: `npm run build` PASS (built in 1.08s)
- Backend tests: `667/667` passing (`.\.venv\Scripts\pytest.exe -q`)
- Real browser QA: Gameplay verified for all 6 archetypes (`platformer`, `arena`, `shooter`, `collector`, `survival`, `runner`) + `open_world` at 1440×900 desktop viewport (`runtime_qa_playtest_1788698449683.webp`), with responsive layout and canvas scaling verified at 768×900 and 375×812 viewports with zero console errors.

### Verification freshness warning

Before any future phase is declared complete, run a fresh full regression and update this section with the actual command and result. Do not replace a real test run with a copied historical number.

## Current Architecture

React + TypeScript + Vite + Tailwind CSS frontend with HashRouter, React Context, and embedded Phaser 3.88.2.

FastAPI modular-monolith backend with SQLAlchemy/SQLite/Alembic, JWT+Argon2 authentication, hybrid FAISS+lexical Discovery, hosted AI provider abstraction, project/version persistence, build jobs, SSE, playtest/critique, and creator progression.

## Discovery State

- Frozen operating point
- 25% personalization treatment exposure
- No ranking/candidate-pool tuning without organic data
- Full catalog and candidate-pool definitions documented in [`docs/architecture/discovery-engine.md`](../architecture/discovery-engine.md)
- Three-layer metadata model is authoritative for catalog provenance/search/display behavior

## Data / Migration State

The repository documents:

- BuildLog foreign-key/cascade enforcement
- Redundant user-unique-index removal
- Token-version session revocation

The actual migration head must always be verified from the repository rather than trusted from this file alone.

## Worker / Deployment State

Current architecture remains single-worker because:

- SSE broadcaster state is process-local
- Rate limiter state is process-local

Do not use multi-worker/multi-instance deployment until the distributed-state design is approved and implemented.

## Browser QA State

The latest documented browser QA covered:

- All currently documented routes
- Meaningful controls
- Responsive viewports (1440×900 gameplay, 768×900 and 375×812 layout/canvas verification)
- Existing prototype runtime
- Inspiration flows
- Builder synchronization
- Profile behavior
- Remix behavior
- Keyboard/restart behavior
- Fullscreen behavior
- Console cleanliness

Future browser claims still require fresh live evidence.

## Known Limitations

- Production deployment hardening is not complete.
- Single-worker architecture is a deliberate scaling boundary.
- `/api/health` is liveness-only.
- Open-World actor schedules (`schedules`) are unsupported/rejected by the runtime compiler.
- Dynamic global event modifiers (`event_modifiers` affecting player physics or enemy base stats) are partial/unsupported as currently implemented (threat/danger modifiers execute via `ThreatManager`, while dynamic stat/physics modifiers are rejected with controlled validation errors).
- Not all canonical Open World semantics are fully implemented.
- Some low/medium-confidence repository cleanup items may remain intentionally deferred.
- Historical benchmark results do not replace organic production evaluation.

## Next Engineering Focus

The next engineering phase is **B8 Production Hardening**.

Priority areas:

1. Observability
2. Production configuration and trusted proxy handling
3. Database backup/recovery/retention
4. Release/rollback procedures
5. Deployment smoke testing
6. Only then, if justified, multi-worker/distributed scaling

Do not restart Discovery tuning or completed product work without new evidence.
