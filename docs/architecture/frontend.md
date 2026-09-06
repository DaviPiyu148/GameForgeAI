# 05 — Frontend Architecture

## Current Truth

The frontend is integrated with the real backend service layer.

It communicates with FastAPI through REST and SSE and embeds the Phaser runtime for playable prototypes.

## Routes

The current application has twelve documented browser routes:

```text
#/
#/discover/no-matches
#/build
#/status/success
#/status/error
#/dashboard
#/profile
#/documentation
#/api-access
#/community
#/support
#/privacy
```

Do not treat the route count itself as an architectural invariant. Add new top-level product routes only through an intentional product/architecture decision.

## State Ownership

`AppContext` provides application-level client state.

### Backend-authoritative

- `myGames`
- Active build state
- Compiler/build logs
- Authenticated user identity/profile
- Saved discoveries
- Persistent project/version state

### Client/transient

- Current prompt draft
- Current build-parameter draft
- UI modal/tab/loading state
- Other short-lived presentation state

Local browser storage may preserve selected drafts/session information, but must not be treated as authoritative business state.

## API Service Layer

The frontend should centralize API communication rather than scattering raw `fetch` behavior across components.

Typical boundaries include:

- `api.ts`: HTTP/error handling
- `projects.ts`: project/version operations
- `builds.ts`: build creation/status/log/SSE operations
- `discovery.ts`: discovery/recommendation operations
- Authentication/profile services
- Playtest/remix/inspiration services as applicable

## Error Handling

Normalize backend errors into a predictable client representation.

UI should distinguish:

- Authentication failures
- Validation failures
- Not found
- Conflict/stale version
- Rate limiting
- Dependency/server failure

Do not display raw stack traces or internal error payloads.

## Prototype Runtime Integration

The prototype modal receives validated project state and passes the current DSL plus deterministic runtime metadata/seed into the Phaser runtime.

The runtime must not fetch arbitrary executable code from the network.

## UX Quality

Frontend changes should preserve:

- Existing information hierarchy
- Visual language
- Loading/error/empty states
- Keyboard usability
- Responsive behavior
- Visible focus
- Modal/drawer layering
- Console hygiene

Source inspection is not sufficient evidence for visual/runtime claims.

## Performance

Avoid unnecessary global rerenders.

Keep expensive calculations out of render paths when practical.

Do not add a client-state library without evidence that the current architecture cannot reasonably support the requirement.
