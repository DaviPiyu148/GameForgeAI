# Small Product Fixes & Reliability Polish V2

## Overview

This document records the six focused reliability and product-polish fixes delivered in the **Small Product Fixes & Reliability Polish V2** milestone (2026-08-31).

---

## Fix 1 — Blueprint Derivation Recovery

**Problem**: `"Blueprint unavailable: Stored Game DSL failed validation; cannot derive blueprint."` appeared for existing generated games even when those games played correctly.

**Root Cause**: `DSLNormalizer.normalize_levels()` was iterating optional level fields (`theme`, `world`) and writing `None` directly into `base_world`, replacing valid enum strings with `None`. This caused strict `WorldDef.theme` Pydantic validation to fail at blueprint-derivation time even though the game itself ran fine.

**Fix** (`backend/app/generation/dsl_normalizer.py`):
- `normalize_levels()` now skips `None` values instead of propagating them.
- `normalize_world()` now falls back to `"neon"` when theme is `None` or unrecognized.
- Verified against all 22 playable projects in `gameforge.db`: 100% derive valid blueprints.

**New tests** (`backend/tests/test_blueprint.py`): 11/11 passing.

---

## Fix 2 — Persistent Technical Build Logs

**Fix** (`gameforge-ai/src/pages/SuccessStatusPage.tsx`):
- Added collapsible TECHNICAL BUILD LOG section on success page.
- Full ordered event sequence with source prefixes, severity color-coding, and RECOVERED badge.

---

## Fix 3 — Real Browser Fullscreen

**Fix** (`gameforge-ai/src/components/Shared/PrototypeModal.tsx`):
- Standard `element.requestFullscreen()` with WebKit fallback.
- `document.exitFullscreen()` with catch.
- Both `fullscreenchange` and `webkitfullscreenchange` listeners.
- ESC handler guards against double-close when exiting fullscreen.
- Modal fills display via Tailwind classes when fullscreen.

---

## Fix 4 — Account Settings (Username & Password)

### Backend

- `UpdateProfileRequest`, `ChangePasswordRequest`, `ChangePasswordResponse` schemas.
- `update_username()`, `change_password()` service methods.
- `PATCH /api/auth/profile`, `PATCH /api/auth/me`, `POST /api/auth/change-password` endpoints.
- 4/4 new tests in `test_profile_api.py`.

### Frontend

- `updateUsername()`, `changePassword()` in `auth.ts` and `AppContext.tsx`.
- Account Settings panel with Display Username + Change Password forms in `ProfilePage.tsx`.

---

## Fix 5 — Functional Builder Design Preview

**Fix**:
- `BuilderDesignPreview.tsx` — deterministic schematic renderer, zero API calls.
- Three distinct layouts: Open World (topology graph), Campaign (stage progression), Linear/Arena (flow).
- Integrated into `BuilderPage.tsx` sidebar, replacing static AWAITING_RENDER_DATA placeholder.

---

## Verification Summary

| Check | Result |
|---|---|
| pytest tests/test_blueprint.py | 11/11 PASSED |
| pytest tests/test_profile_api.py | 4/4 PASSED |
| pytest tests/test_auth.py | 15/15 PASSED |
| pytest tests/test_builds.py tests/test_projects.py tests/test_project_management.py | 36/36 PASSED |
| pytest tests/test_ai_provider.py | 36/36 PASSED |
| pytest tests/test_generation_resilience.py | 10/10 PASSED |
| npx tsc --noEmit | 0 errors |
| npm run build | 0 errors, 79 modules, 3.72s |
| alembic current | bc9ae398f146 (head) |
| 22 playable projects derive valid blueprints | VERIFIED |
| PATCH /api/auth/profile registered in live backend | VERIFIED |
| BROWSER TESTING | PARTIAL (account settings + design preview verified; fullscreen + blueprint tab pending due to model quota) |
