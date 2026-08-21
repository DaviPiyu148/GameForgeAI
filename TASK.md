# GameForge AI — Task Execution Ledger

## Task
Game DNA & Personalization V1 — Genre Preferences • Game DNA • Personalized Generation Context • Profile Polish

## Status
IN_PROGRESS

## Objective
Establish a deterministic, explainable "Game DNA" user preference system:
1. **Deterministic Game DNA Model & Scoring**: Normalize behavioral signals (search, save, build similar, prototype generation, playtesting) across canonical genres with diminishing returns.
2. **Confidence & Low-Data Handling**: Graceful "Game DNA is still forming" low-data state without fabricated preferences.
3. **Profile Game DNA UI**: Polished cyberpunk Game DNA telemetry section on Profile with ranked affinity bars, strongest match, recent interest callout, and "How this works" explanation.
4. **Personalized Generation & Builder UI**: Pass structured Game DNA context into LLM prompt (`prompts.py`) without overriding explicit user prompts, alongside a sleek personalization hint in Builder.
5. **State Management & Caching**: Hydrate once on authentication, memoized callbacks, zero request loops, strict user data isolation.

## Started
2026-08-21

---

## 1. GD1.1 Preference Model & Signals (Backend)
- [ ] Subtask 1.1: Extend `PreferenceService` with canonical taxonomy, recent interest tracking, and confidence scoring.
- [ ] Subtask 1.2: Enforce logarithmic/bounded scoring updates to prevent repeated actions from unbounded score explosion.
- [ ] Subtask 1.3: Update signal recording weights across discovery search (1.0), save (3.0), build similar (4.0), start build (4.5), and playtest (4.0).

### Evidence
*Pending implementation*

---

## 2. GD1.2 Preference API & Low-Data Contract
- [ ] Subtask 2.1: Update `UserPreferencesResponse` schema to include `recent_interest`, `confidence_level` ('LOW', 'MODERATE', 'HIGH'), and `has_sufficient_data`.
- [ ] Subtask 2.2: Ensure low-data state returns empty `top_genres` and `has_sufficient_data: false` for new/low-activity users.
- [ ] Subtask 2.3: Verify authenticated endpoint `GET /api/profile/preferences` enforces IDOR protection and user data isolation.

### Evidence
*Pending implementation*

---

## 3. GD1.3 Game DNA Profile UI (Frontend)
- [ ] Subtask 3.1: Upgrade Profile page preference panel into "YOUR GAME DNA" section with cyberpunk styling.
- [ ] Subtask 3.2: Implement low-data state banner ("Your Game DNA is still forming.") with clear guidance.
- [ ] Subtask 3.3: Render ranked genre bars, percentage tags, affinity tiers (`HIGH`, `MODERATE`, `EMERGING`), and strongest match / recent interest callouts.
- [ ] Subtask 3.4: Add "How this works" explanation block explaining signal sources and non-intrusive modeling.

### Evidence
*Pending implementation*

---

## 4. GD1.4 Generation Context Integration (Backend)
- [ ] Subtask 4.1: Extend `build_generation_prompt` in `backend/app/ai/prompts.py` to accept optional structured `personalization` payload.
- [ ] Subtask 4.2: Enforce strict priority: `EXPLICIT CONCEPT > BUILDER SETTING > PERSONALIZATION HINT`.
- [ ] Subtask 4.3: Update `BuildService` and `GameGenerationService` to inject user Game DNA when `has_sufficient_data: true`.

### Evidence
*Pending implementation*

---

## 5. GD1.5 Build Similar & Builder UI Context (Frontend)
- [ ] Subtask 5.1: Add subtle personalization indicator in `BuilderPage.tsx` ("Personalized for you: Action • Shooter • Survival").
- [ ] Subtask 5.2: Preserve source-game primary inspiration in Build Similar pipeline.

### Evidence
*Pending implementation*

---

## 6. GD1.6 State Management & Request Loop Guard
- [ ] Subtask 6.1: Verify `AppContext` loads preferences once upon auth hydration without duplicate calls or intervals.
- [ ] Subtask 6.2: Ensure preference refetch only occurs after explicit mutations (Save, Build, Playtest).

### Evidence
*Pending implementation*

---

## 7. GD1.7 Automated & Regression Tests
- [ ] Subtask 7.1: Backend unit & API tests in `backend/tests/test_preference_service.py` and `backend/tests/test_game_dna.py`.
- [ ] Subtask 7.2: Frontend lint (`npx oxlint`), typecheck (`npx tsc --noEmit`), and build (`npm run build`).
- [ ] Subtask 7.3: Full backend pytest suite (`pytest tests/ -q`).

### Evidence
*Pending implementation*

---

## 8. GD1.8 Browser E2E Verification & Git Checkpoint
- [ ] Subtask 8.1: Browser subagent verification: User A low-data state, search/save/build similar activity, Game DNA update, Builder hint, User B isolation.
- [ ] Subtask 8.2: Check `git diff`, update `BROWSER_E2E_TEST_REPORT.md`, create checkpoint commit `feat: add game dna personalization`.

### Evidence
*Pending implementation*

---

## Change Log
- 2026-08-21: Initialized Game DNA & Personalization V1 task ledger.
