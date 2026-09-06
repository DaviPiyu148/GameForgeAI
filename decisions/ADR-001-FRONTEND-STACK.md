# ADR-001 — Frontend Stack

**Status:** Accepted

## Context

GameForge AI requires a highly interactive browser application with discovery, project-building, inspiration, project/version management, playtest, and account workflows.

The frontend is already implemented using a React-based architecture. Replacing the frontend framework would create unnecessary migration risk without a concrete product or architectural benefit.

## Decision

Use:

- React 19
- TypeScript
- Vite
- Tailwind CSS
- `react-router-dom`
- React Context

The frontend remains a client of backend APIs rather than the authoritative owner of persistent business state.

### State ownership

Use client-side state for:

- UI state
- Session/UI coordination
- Short-lived view state
- Local presentation concerns

Persistent business state must be owned and validated by the backend when the backend is authoritative.

Do not introduce a second state-management framework merely to solve a small local state problem.

### Routing

The router is the source of truth for actual application routes.

Do not hard-code an obsolete route count in architecture rules. New top-level product routes require an intentional product/architecture decision and must follow existing navigation conventions.

### API boundary

Backend integration occurs through explicit service/API boundaries.

Do not place backend business rules, authorization decisions, provider credentials, or authoritative persistence logic in the frontend.

### UX and accessibility

Production frontend work must consider:

- Loading, empty, error, success, and disabled states
- Keyboard interaction and visible focus
- Responsive behavior
- Accessible names and semantic controls
- Modal/drawer focus behavior
- Motion/accessibility preferences
- Console and network errors

User-visible behavior must be verified in a real browser when the behavior is material to the task.

## Consequences

### Positive

- Preserves the existing, proven frontend implementation.
- Strong typing improves maintainability.
- Vite provides a simple and fast development/build workflow.
- React Context is sufficient for the current application-wide client state needs.
- Backend ownership of business state prevents frontend/server divergence.

### Negative

- React Context is not a universal server-state manager.
- Large-scale client-state requirements may eventually justify another tool, but that change requires evidence.
- Tailwind styling discipline must be maintained to avoid inconsistent UI implementation.

## Rejected / Deferred

- Replacing React solely for stylistic preference.
- Adding Redux/Zustand or another global state framework without a demonstrated need.
- Moving authoritative business state into browser storage.
- Adding top-level routes without a product/architecture decision.

## Implementation Invariants

1. The frontend must not be trusted for authorization.
2. Provider secrets never reach the browser.
3. The browser must not be able to fabricate authoritative backend state.
4. Existing user-visible behavior should remain compatible unless a change is intentional.
5. Browser verification is required for claims about actual browser behavior.
