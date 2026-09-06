# 12 — Testing and QA

## Purpose

Testing is a system of evidence, not a coverage-number competition.

Every significant change must use the lowest-cost test level that can prove the behavior, plus higher-level tests where integration risk requires them.

## Test Levels

### Unit

Use for focused deterministic logic:

- Services
- Schemas
- Validators
- Parsers
- Ranking
- Runtime compatibility
- Gameplay quality
- PRNG/procedural logic

### Integration

Use for:

- Repositories
- Database transactions
- SQLite behavior
- Alembic migrations
- Cross-service boundaries
- Persistence invariants

### API

Verify:

- Request validation
- Response contracts
- Error envelopes
- Authentication
- Authorization
- Ownership
- Conflicts
- Rate limits
- Pagination/filter semantics

### SSE

Verify:

- Authentication
- Ownership
- Initial replay
- Live event delivery
- Duplicate-log prevention
- Terminal closure
- Worker failure
- Client disconnect
- Timeout/inactivity behavior

### Browser

Verify actual user-visible behavior:

- Navigation
- Forms
- Modals
- Drawers
- Empty/loading/error states
- Keyboard interactions
- Runtime gameplay
- Responsive behavior
- Console/network errors

Use real browser dimensions where required, including:

- 1440×900
- 1024×768
- 768×1024
- 375×812

## Generation Test Matrix

Test:

- Valid GameDesignSpec
- Malicious/script-injection input rejection
- GameDSL bounds
- Backward compatibility
- Quality gates
- Spawn safety
- Reachability
- Rule liveness
- Scale budgets
- Boss/finale constraints
- World connectivity
- Runtime compatibility
- Playtest telemetry
- AI critique parsing
- Improvement patching
- Version immutability

## Discovery Testing

Test:

- Entity queries
- Similarity queries
- Concept queries
- Mixed-language queries
- Hard constraints
- Explicit avoidances
- Candidate-pool semantics
- Ranking determinism
- Personalization boundaries
- No-match behavior
- Enrichment failure/fallback
- Latency regression

The frozen 98-query benchmark is regression evidence, not permission for indiscriminate ranking changes.

## Security Testing

Test:

- Invalid/expired tokens
- Token-version revocation
- Cross-user resource access
- IDOR/BOLA
- Duplicate registration/username races
- Rate-limit boundaries
- Input injection
- Secret exposure
- Error leakage
- Avatar upload restrictions
- SSE ownership

## Migration Testing

For schema changes:

```text
inspect
→ preflight
→ upgrade
→ verify schema/data
→ downgrade when supported
→ verify
→ re-upgrade
→ verify
→ full regression
```

Historical identity preservation requires more than row-count equality.

## Concurrency Testing

Use actual concurrency where the bug/risk is concurrent.

Do not accidentally serialize the test with an inappropriate lock or fixture.

Verify final invariants, not merely that all calls returned.

## Flaky Tests

Never cure flakiness by:

- Adding arbitrary sleeps
- Disabling assertions
- Increasing retries blindly
- Serializing real concurrency
- Marking tests skipped without investigation

Find the underlying cause.

## Browser Evidence Rule

Never claim browser verification because source code looks correct.

For runtime movement/interaction, verify the actual resulting state independently for each important action.

## Evidence Categories

Every report must distinguish:

- Source inspected
- Command executed
- Automated test verified
- Browser verified
- Statically inferred
- Not verified

## Release Gates

Before a production release, run the required:

- Backend regression
- Frontend type check
- Frontend build
- Lint
- Relevant browser smoke/regression
- Migration verification
- Security checks
- Dependency checks

Record exact commands and real results.
