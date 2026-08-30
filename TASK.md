# GameForge AI — Task Execution Ledger

## Task

Product Polish Sprint A — Project Management, Generated Game Covers, Builder Presets

## Status

IN_PROGRESS

## Objective

Make GameForge AI feel substantially more product-like using existing architecture:
1. Project Management: Rename (inline), Duplicate (snapshot copy), Delete (relationship-safe)
2. Generated Game Covers: deterministic procedural covers per project card
3. Builder Presets: Quick Prototype / Campaign / Open World one-click presets

## Started

2026-08-30

---

## Dependency Graph Analysis (Pre-Implementation)

### Project → Child Entity FK Relationships

| Child Table | FK | Cascade |
|---|---|---|
| `project_versions` | `projects.id` (ondelete=CASCADE) | YES — automatic |
| `playtest_sessions` | `projects.id` (ondelete=CASCADE) | YES — automatic |
| `build_jobs.project_id` | **NO FK constraint** — plain String(36) | N/A — string reference only |
| `build_logs.build_id` | **NO FK constraint** — plain String(36) | N/A — string reference only |
| `xp_events.source_reference` | **NO FK constraint** — nullable String(255) | N/A — audit log reference only |

**Conclusion**: Deleting a Project row cleanly cascades to `project_versions` and `playtest_sessions`
via existing DB constraints. `build_jobs`, `build_logs`, and `xp_events` are independent audit
entities — they are NOT children of Project (by design). No orphan rows will be created.
No additional cleanup logic is needed.

### GameProject shape (confirmed fields)

Available for cover generation: `id`, `title`, `genre`, `engine`, `world_mode`, `scale`, `status`
All confirmed as persisted DB columns.

---

## 1. Pre-Implementation

- [x] Read AGENTS.md
- [x] Inspected all model files (project, project_version, playtest, build, build_log, progression, preference)
- [x] Inspected all relevant migrations (confirmed build_jobs has no FK on project_id)
- [x] Inspected project_service.py, project_repo.py, api/projects.py
- [x] Inspected AppContext.tsx, DashboardPage.tsx, BuilderPage.tsx, ProfilePage.tsx
- [x] Inspected types/index.ts, services/projects.ts, services/api.ts
- [x] Inspected existing test_projects.py patterns
- [x] Confirmed git status: clean working tree on fresh-main, 335 backend tests passing

---

## 2. Implementation

### Feature 1 — Project Management

- [ ] Backend: `project_repo.py` — add `delete()` method
- [ ] Backend: `project_service.py` — add `delete_project()`, `duplicate_project()`
- [ ] Backend: `api/projects.py` — add `DELETE /projects/{id}` (204) and `POST /projects/{id}/duplicate` (201)
- [ ] Frontend: `services/projects.ts` — add `deleteProject()`, `duplicateProject()`
- [ ] Frontend: `types/index.ts` — add `deleteProject`, `duplicateProject` to AppContextType
- [ ] Frontend: `AppContext.tsx` — implement `deleteProject()`, `duplicateProject()` actions
- [ ] Frontend: `DashboardPage.tsx` — compact action menu with Rename/Duplicate/Delete

### Feature 2 — Generated Game Covers

- [ ] Frontend: `src/utils/projectCover.ts` — deterministic cover generator
- [ ] Frontend: `src/components/Shared/ProjectCoverArt.tsx` — cover rendering component
- [ ] Frontend: `DashboardPage.tsx` — use ProjectCoverArt in project cards
- [ ] Frontend: `ProfilePage.tsx` — use ProjectCoverArt where project cards appear

### Feature 3 — Builder Presets

- [ ] Frontend: `src/data/builderPresets.ts` — three preset definitions derived from canonical defaults
- [ ] Frontend: `BuilderPage.tsx` — preset chip row + active state tracking

---

## 3. Tests

- [ ] Backend: new tests for duplicate_project (owner, non-owner, data semantics)
- [ ] Backend: new tests for delete_project (owner, non-owner, cascade verification)
- [ ] Backend: rename test already covered by existing PATCH tests

---

## 4. Verification

- [ ] pytest tests/ -q (≥335 tests, all pass)
- [ ] npx tsc --noEmit (0 errors)
- [ ] npx oxlint (0 errors)
- [ ] npm run build (succeeds)
- [ ] alembic current / alembic heads (single head bc9ae398f146)
- [ ] BROWSER TESTING: NOT YET PERFORMED

---

## 5. Documentation

- [ ] docs/08-API-CONTRACT.md — add DELETE + duplicate endpoints
- [ ] docs/15-CURRENT-STATUS.md — update status
- [ ] PRODUCT_POLISH_SPRINT_A.md — create sprint record

---

## 6. Git Checkpoint

- [ ] git diff reviewed
- [ ] commit created
- [ ] working tree clean

---

## Blockers

None.

## Change Log

- 2026-08-24: Full-stack operational health audit — 9 confirmed defects found and fixed.
- 2026-08-26: UI Copy Audit V1 — commit b192bc1.
- 2026-08-26: Living Documentation Refresh — commit b635d2d.
- 2026-08-30: Product Polish Sprint A — IN_PROGRESS.
