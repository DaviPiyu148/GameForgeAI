# GameForge AI — UI Motion & Special Effects System

## Status
The frontend already had a substantial cyberpunk motion system in place before this pass (motion
tokens, page/stagger/modal transitions, glow language, terminal/CRT ambient effects, reduced-motion
handling). This document formalizes that system and records the gaps that were closed in this pass.

## 1. Motion Tokens
Defined in `gameforge-ai/src/styles/index.css` (`:root`):

| Token | Value | Use |
|---|---|---|
| `--motion-fast` | 100ms | micro-interactions (icon hover/active) |
| `--motion-normal` | 180ms | button/control transitions |
| `--motion-medium` | 260ms | page/modal/stagger entrances |
| `--motion-slow` | 400ms | emphasis sweeps, energy-sweep |
| `--ease-cyber` | `cubic-bezier(0.1, 0.9, 0.2, 1)` | the one easing curve used everywhere for a consistent "snap in, settle" feel |

Tailwind v4 theme-driven `animate-*` utilities (generated from `@theme { --animate-* }`):
`--animate-fade-in` / `--animate-fadeIn` → both map to the same `fadeIn` keyframe (both spellings
were already used across the codebase; previously neither was registered as a real Tailwind
utility, so those elements silently had no entrance animation — fixed in this pass).

## 2. Reusable Effect Classes
All defined once in `styles/index.css`, reused everywhere rather than one-off inline keyframes:

- **Entrances**: `.page-enter`, `.stagger-enter` + `.stagger-1`..`.stagger-5`, `.modal-enter` / `.modal-exit`, `.modal-backdrop-enter` / `.modal-backdrop-exit`
- **Interaction**: `.btn-interactive` (hover lift + active press), `.icon-interactive`, `.energy-sweep` (diagonal light sweep on hover)
- **Glow language**: `.glow-cyan`/`.glow-magenta`/`.glow-amber`/`.glow-error`, `.glow-box-*` (border+shadow combo), `.text-glow-*`
- **Ambient / terminal**: `.scanline-effect` (CRT scanlines), `.crt-flicker`, `.terminal-cursor` (blink), `.ai-pulse`, `.mic-listening` (pulse ring), `.arcade-border` / `.arcade-panel`
- **New in this pass**:
  - `.scan-sweep` — a thin animated light band that sweeps top-to-bottom inside a panel (Builder "Live Preview" wireframe)
  - `.milestone-unlock-flash` — one-shot glow/brightness pulse for a milestone unlocked in the last 10 minutes
  - `.fullscreen-transition` — brief scale/opacity settle applied for ~260ms when the Prototype modal enters/exits native fullscreen
  - `.toast-enter` / `.toast-enter-emphasis` / `.toast-exit` — toast slide/scale in and out (emphasis variant used for Level Up / Milestone toasts, which overshoot slightly before settling)

## 3. Toast Notification System (new)
Previously there was no notification system anywhere in the app despite several state changes
(save, build complete, XP gain, level up, milestone unlock) having no transient feedback.

- `src/services/toastBus.ts` — a minimal pub/sub (`pushToast`, `subscribeToasts`) decoupled from
  React state. This lets `AppContext` (which sits above the component tree) raise a toast as a
  side effect without threading toast state through `AppState`.
- `src/components/Shared/ToastContainer.tsx` — mounted once in `App.tsx` (both the builder's
  full-screen layout and the standard `PageContainer` layout), renders a stacked, top-right toast
  list via `createPortal`. Six variants (`info`, `success`, `xp`, `levelup`, `milestone`, `error`)
  each get their own icon/border/glow color reusing the existing glow-box classes. Auto-dismiss
  timers are staggered by variant (3–5s); Level Up and Milestone get the longer window and the
  "emphasis" entrance since they're the intentionally bigger moments.
- Wired call sites (`AppContext.tsx`), all purely additive UI feedback — no business logic,
  request payloads, or state shapes were changed:
  - `saveDiscovery` success → `GAME SAVED`
  - `compileProject` SSE `SUCCESS` → `BUILD COMPLETE` (fires just before navigating to the
    dedicated Success page, which remains the primary celebration surface)
  - `refreshProgress` diffs the previous vs. newly-fetched `UserProgressData` snapshot:
    level increase → `LEVEL UP`, XP increase → `+N XP`, unlocked milestone count increase →
    `NEW MILESTONE` (with the specific milestone title)

## 4. Gaps Closed In This Pass
1. **Broken `animate-fade-in` / `animate-fadeIn` utilities** — used in `HomePage.tsx`,
   `ProfilePage.tsx`, `PrototypeModal.tsx`, `RemixPanel.tsx` but never registered as real Tailwind
   utilities, so those fades were silent no-ops. Fixed via `@theme { --animate-fade-in / --animate-fadeIn }`.
2. **No toast/notification system** (Phase 17 of the spec) — added, see §3.
3. **Dashboard project status badge always cyan** regardless of actual status — `COMPILING`/`ERROR`
   states rendered identically to `PLAYABLE` with a constant `.crt-flicker` regardless of state.
   Now reuses the same status→color mapping as `StatusBadge.tsx`: `PLAYABLE` gets a calm badge (no
   loop), `COMPILING`/`ERROR` get an animated pulse dot in their respective color.
4. **No rotating icon during async/loading states** — Builder's Compile Scene button, the Auth
   Modal's submit button, and the Error page's Retry button all swapped to a `sync` glyph but
   never animated it. Added `animate-spin` conditionally so the icon actually spins while busy.
5. **Builder "Live Preview (Wireframe)" panel was static** apart from a pulsing icon — added
   `.scan-sweep`, a subtle looping light band, so the panel reads as "live" without claiming to
   represent real render output (per the spec's explicit "do not fake progress" constraint).
6. **Milestones had no distinct "just unlocked" moment** — `ProfilePage.tsx` now flags a milestone
   as recently unlocked (`unlocked_at` within the last 10 minutes) and applies `.milestone-unlock-flash`,
   a one-shot glow pulse, plus a small hover lift that was missing from milestone cards entirely.
7. **Fullscreen toggle in `PrototypeModal` was an abrupt native jump-cut** — added a brief
   `.fullscreen-transition` scale/opacity settle on the `fullscreenchange` event so entering/exiting
   fullscreen has a visible "settling in" beat instead of a hard cut. Does not touch the Phaser
   canvas or its coordinate system — only the modal chrome around it.

## 5. Reduced Motion (Phase 18)
`styles/index.css` already had a `prefers-reduced-motion: reduce` block disabling the named
entrance/interaction classes. This pass added a second, comprehensive catch-all in the same media
query:

```css
*, *::before, *::after {
  animation-duration: 0.01ms !important;
  animation-iteration-count: 1 !important;
  transition-duration: 0.01ms !important;
  scroll-behavior: auto !important;
}
```

This is deliberately layered on top of (not a replacement for) the existing named-class rules. It
guarantees every animation — including Tailwind's built-in `animate-spin`/`animate-pulse`, the new
toast/scan-sweep/milestone-flash effects, and anything added later — resolves instantly rather than
looping or playing out, without needing an ever-growing manual selector list. State changes (a
button's disabled state, a badge's color, a progress bar's width) still happen; only the motion
that gets you there is removed. `ProfilePage.tsx`'s XP count-up already explicitly checks
`window.matchMedia('(prefers-reduced-motion: reduce)')` and jumps straight to the final value.

## 6. Performance Notes
- All new/added motion uses `transform`, `opacity`, `filter`, and `box-shadow` — no animated
  `width`/`height`/`top`/`left` layout properties were introduced (the one exception,
  `.scan-sweep`'s `top` animation, animates an absolutely-positioned pseudo-element that does not
  participate in layout, so it does not trigger reflow).
- The toast system re-renders only its own portal subtree on push/dismiss; it does not touch
  `AppState` or trigger re-renders of the rest of the app.
- No new animation library was introduced — everything is native CSS keyframes/transitions plus
  Tailwind's built-in utilities, consistent with the codebase's existing approach.
- The Phaser canvas is untouched: no React animation state is read inside the Phaser game loop, and
  no DOM animation runs at game-loop frequency.

## 7. Verification Performed
- `npx tsc --noEmit` — clean.
- `npx oxlint` — clean (0 errors/warnings).
- `npm run build` — production build succeeds.
- `backend/.venv/Scripts/python.exe -m pytest tests/ -q` — 335 passed (no backend files were
  touched by this pass; run to confirm no incidental regression).
- Browser verification via a local headless Chromium (Playwright) driving the actual Vite +
  FastAPI dev servers at 1440×900: Home, Builder, Dashboard, Profile, No-Matches, and the
  Success/Error redirect-guard pages all loaded with **zero console/page errors**. Confirmed via
  screenshot diffing that the Builder preview `.scan-sweep` band visibly moves between two frames
  ~900ms apart. Registered a real test user end-to-end through the Auth Modal (real backend call,
  navbar updated to the authenticated state, zero console errors). Directly exercised all six toast
  variants through the live `toastBus` module against the running dev server and confirmed correct
  stacking, per-variant styling, and staggered auto-dismiss timing via before/after screenshots.
  Discovery search itself did not return results in this sandbox (times out — appears to depend on
  an external embedding/enrichment call not reachable from this environment); this is a pre-existing
  environment/network constraint unrelated to this pass, not a regression, and the `saveDiscovery`
  toast call site was verified by code path plus the direct toastBus exercise instead.
