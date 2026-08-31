# GameForge AI — Accessibility Remediation Plan V1 (Approved with Targeted Guardrails)

> **Status:** APPROVED FOR IMPLEMENTATION  
> **Standard:** WCAG 2.1 Level AA & Semantic HTML Best Practices  
> **Dependency Policy:** 0 new dependencies. Reuse existing component architecture.

---

## 1. Approved Architectural Guardrails & Principles

1. **Role Determination Before ARIA:**
   - Determine whether a control is a tab, toggle, disclosure, or menu before assigning ARIA roles.
   - For Discovery modes (`Best Match`, `Discover`, etc.): Since they act as a single-selection filter switching the result set query, treat them cleanly as native toggle buttons with `aria-pressed={isSelected}` and `<span aria-hidden="true">` on icons.
   - For Dashboard actions (`⋮`): Use a standard disclosure pattern with `aria-expanded={isOpen}`, `aria-controls`, and native `<button>` elements in a normal popup container rather than a fake `role="menu"` that lacks arrow-key navigation.
2. **Prefer Native Semantic HTML Over ARIA Simulation:**
   - For interactive headings (such as Dashboard project titles): Wrap a native `<button>` inside `<h3>` rather than adding click handlers and fake keyboard semantics to the heading tag.
   - Use `<label htmlFor="id">` and `<input id="id">` rather than `aria-label` when visible text is present.
   - Use native `<button>` with text content over `role="button"`.
3. **Additive Global Focus Styles:**
   - Global focus styles must supplement, not override, existing component-specific focus treatments.
   - Ensure cyberpunk chamfer and notch shapes do not clip focus indicators.
4. **No Duplicate Component Systems:**
   - Remediate existing components directly in place (`AuthModal.tsx`, `Navbar.tsx`, `DashboardPage.tsx`, `HomePage.tsx`, `useModalDialog.ts`).
5. **Phaser Canvas Scope Boundary:**
   - The WebGL/Canvas gameplay surface remains a procedural graphical simulation. Remediations apply strictly to surrounding DOM controls, HUD panels, and modal containers.

---

## 2. Prioritized Remediation Sprints

### Sprint 1 (P0): Core Form & Input Associations
*Target: Resolve all unassociated form fields, placeholder-only inputs, and missing browser autocomplete attributes.*

- [ ] **Subtask 1.1 — Search Bar Labeling (`HomePage.tsx`):**
  - Add `aria-label="Natural language game search prompt"` and `id="discovery-search-input"` to the main search bar.
  - Mark decorative search icon with `aria-hidden="true"`.
- [ ] **Subtask 1.2 — Authentication Form Association (`AuthModal.tsx`):**
  - Add unique `id` attributes: `auth-username`, `auth-email`, `auth-password`.
  - Add matching `htmlFor` attributes to `<label>` elements.
  - Add `autoComplete="username"`, `autoComplete="email"`, and `autoComplete="current-password"` / `autoComplete="new-password"`.
- [ ] **Subtask 1.3 — Profile Settings Form Association (`ProfilePage.tsx`):**
  - Add `id="profile-username"` and `htmlFor="profile-username"` to the username change field.
  - Add `id` / `htmlFor` pairs and appropriate `autoComplete` attributes to current password, new password, and confirm password fields.

---

### Sprint 2 (P1): Keyboard Interactions, Disclosure Menus & Navigation
*Target: Native button semantics for headings, standard disclosure pattern for context actions, and active navigation links.*

- [ ] **Subtask 2.1 — Dashboard Context Menu Disclosure (`DashboardPage.tsx`):**
  - Add `aria-label={`More actions for ${game.title}`}` to the `⋮` context trigger button.
  - Mark `<span className="material-symbols-outlined">more_vert</span>` with `aria-hidden="true"`.
  - Use native button disclosure pattern with `aria-expanded={openMenuId === game.id}` and `id={`project-actions-${game.id}`}`.
- [ ] **Subtask 2.2 — Native Button Heading Semantics (`DashboardPage.tsx`):**
  - Wrap the interactive title inside `<h3>` as a native `<button>` with appropriate styling, native focus, and Enter/Space keyboard activation.
  - Add `aria-label="Save project title"` to the check button and `aria-label="Cancel title rename"` to the close button in `RenameInput`.
- [ ] **Subtask 2.3 — Active Navigation Semantics (`Navbar.tsx`):**
  - Add `aria-current={active ? 'page' : undefined}` to desktop navigation links and mobile drawer navigation links.

---

### Sprint 3 (P2): Toggle States & Filter Semantics
*Target: Expose dynamic selection states across discovery modes, filters, and voice search.*

- [ ] **Subtask 3.1 — Discovery Mode Filter Buttons (`HomePage.tsx`):**
  - Add `aria-pressed={isSelected}` and `aria-hidden="true"` on mode icons for `Best Match`, `Discover`, `Hidden Gems`, and `Popular`.
- [ ] **Subtask 3.2 — Tune Modal Filter Toggles (`TuneRecommendationsModal.tsx`):**
  - Add `aria-pressed={isSelected}` to all "More of" and "Less of" tag filter buttons.
- [ ] **Subtask 3.3 — Game DNA Starter Toggles (`GameDNAOnboardingModal.tsx`):**
  - Add `aria-pressed={isSelected}` to genre and mechanic selection buttons; mark checkmark icons with `aria-hidden="true"`.
- [ ] **Subtask 3.4 — Voice Search Dynamic State (`HomePage.tsx`):**
  - Update the microphone button to expose `aria-pressed={isListening}` and dynamic `aria-label={isListening ? "Stop listening to voice input" : "Start voice search"}`.

---

### Sprint 4 (P3): Color Contrast, Heading Sequence & Refinements
*Target: Fix footer text contrast, standardize comparison heading sequence, additive focus fallback, and thumbnail labels.*

- [ ] **Subtask 4.1 — Footer Link Color Contrast (`Footer.tsx`):**
  - Replace `text-on-surface-variant/60` with `text-on-surface-variant` to raise contrast against `#05060a` from ~4.1:1 to >7.5:1 (exceeding WCAG AA 4.5:1).
- [ ] **Subtask 4.2 — Comparison Heading Hierarchy (`GameComparisonModal.tsx`):**
  - Change card title and common ground section headings from `<h4>` to `<h3>` to maintain strict sequential heading flow (`h2` $\rightarrow$ `h3`).
- [ ] **Subtask 4.3 — Screenshot Gallery Thumbnail Labels (`GameDetailsModal.tsx`):**
  - Add `aria-label={`View screenshot ${idx + 1} of ${validScreenshots.length}`}` and `aria-current={idx === activeScreenshotIndex ? 'true' : undefined}` to screenshot thumbnails.
- [ ] **Subtask 4.4 — Suggestion Chip Glyph Handling (`HomePage.tsx`):**
  - Wrap decorative `&gt;` prompt indicators with `<span aria-hidden="true">&gt;</span>`.
- [ ] **Subtask 4.5 — Additive Focus Visibility Rule (`index.css`):**
  - Add global fallback focus-visible rule in `@layer base` that supplements without overriding component-specific rings.
- [ ] **Subtask 4.6 — Toast Keyboard Pause (`ToastContainer.tsx`):**
  - Add `onFocus={handleMouseEnter}` and `onBlur={handleMouseLeave}` to pause dismiss timer during keyboard interaction.

---

## 3. Verification & Acceptance Criteria

1. **Static Analysis:**
   - `tsc -b` passes with **0 errors**.
   - `npm run build` succeeds with zero warnings.
   - Backend tests (`uv run pytest tests -q`) pass cleanly.
2. **Codebase Inspection:**
   - 100% of form inputs have programmatic labels.
   - 100% of icon-only buttons have accessible names.
   - 0 skipped heading levels.
   - All text contrast ratios $\ge 4.5:1$ (normal text) and $\ge 3:1$ (large text).
3. **Live Browser Verification (Deferred):**
   - Perform interactive keyboard Tab walkthrough and DevTools accessibility tree inspection upon plan approval.
