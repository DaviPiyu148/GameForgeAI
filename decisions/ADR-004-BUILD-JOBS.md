# ADR-004 — Backend-Owned Build Jobs

**Status:** Accepted

## Context

Prototype generation is an asynchronous operation that can involve an external LLM, validation/repair, artifact generation, compilation, persistence, and streamed progress.

The browser must not be the authority for whether a build succeeded or whether the resulting project exists.

## Decision

Builds are backend-owned asynchronous jobs.

`POST /api/builds` creates a server-side build job.

The backend owns:

- Build lifecycle
- Input validation
- Authoritative project/version lookup
- AI-provider interaction
- Game DSL validation
- Repair/retry policy
- Compilation
- Runtime/build metadata
- Terminal status
- Successful project persistence
- Build logs

Build progress/logs are streamed to the browser through SSE.

## Build Authority

The client must not inject an arbitrary authoritative DSL/build definition in place of the server-selected project/version state.

The backend determines the build inputs from authenticated, authorized, server-side state.

The browser displays server state; it does not declare server-side success.

## Idempotency and Deduplication

Build creation and duplicate-work prevention must consider all fields that materially affect generated output or build identity.

If two requests are semantically different, the deduplication mechanism must not collapse them.

For concurrency-sensitive operations, prefer explicit database constraints/transactions and deterministic conflict handling over process-local assumptions.

## Build Lifecycle

A build should expose explicit lifecycle states appropriate to the current implementation, for example:

```text
QUEUED → RUNNING → SUCCESS
                  └→ ERROR
                  └→ CANCELLED
```

State transitions must be server-owned and observable.

Terminal records must not be retained indefinitely without an explicit retention policy.

Active jobs must not be pruned as historical data.

## SSE

SSE is a transport for server-owned build events, not the source of truth.

The stream must handle:

- Worker termination
- Terminal job state
- Client disconnects
- Inactivity
- Time limits
- Reconnection where supported
- Clean shutdown

The stream must not remain alive indefinitely after the associated build can no longer produce useful events.

## Current Execution Model

Initial execution uses FastAPI-compatible async/background execution.

The current architecture intentionally avoids Celery/Redis.

The present in-process event broadcaster imposes a deployment boundary: multiple application workers cannot automatically share in-memory event queues.

Horizontal scaling therefore requires an explicit distributed event/state strategy and an architecture decision.

## Persistence

A successful backend build persists the resulting project through the server-side lifecycle.

Historical project/version state must remain immutable where the product model requires version immutability.

## Historical Prototype Behavior

The early frontend-local `compileProject()` prototype is superseded.

The current architecture is the backend-owned build flow described by this ADR.

## Consequences

### Positive

- Backend is the authoritative source of build truth.
- Build behavior is testable independently of browser state.
- Logs/status are available for operational diagnosis.
- Project persistence cannot be faked by the frontend.

### Negative

- Requires robust async job lifecycle management.
- SSE and in-process event delivery constrain horizontal scaling.
- Long-running jobs require explicit timeout, cancellation, and cleanup behavior.

## Deferred

Do not add Celery, Redis, or another distributed queue/event system unless actual workload/deployment requirements justify it.

When that happens, preserve:

- Explicit job states
- Idempotency
- Ownership checks
- Durable job state
- Observable failure semantics
- Existing API contracts where practical
