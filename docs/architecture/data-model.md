# 07 — Data Model

## Modeling Rule

Keep these concepts distinct:

1. Database models
2. API schemas
3. Frontend interfaces
4. Game DSL schemas
5. GameDesignSpec schemas

Do not use one representation as a shortcut for another merely because fields happen to overlap.

## Core Entities

### User

Stores:

- Server-generated user ID
- Lowercase email
- Unique username
- Argon2 password hash
- Token version
- Creator level
- Avatar metadata
- Timestamps

Important invariants:

- Password hashes never appear in API responses.
- Identity is derived from authenticated server-side context.
- Credential changes can invalidate older tokens through token-version changes.

### Project

Represents the current logical project.

Contains:

- Owner
- Title/genre/prompt
- Build/runtime parameters
- Scale/world mode
- Current validated DSL
- Design specification
- Runtime metadata
- Current version
- Timestamps

`Project` is current state, not historical version history.

### ProjectVersion

Represents an immutable historical project snapshot.

Contains:

- Project ID
- Version number
- Game DSL snapshot
- Optional DesignSpec
- Change summary
- Optional structured remix intent
- Creation timestamp

Historical versions must not be mutated when newer versions are created.

### BuildJob

Represents an asynchronous build attempt.

Tracks:

- Owner
- Project association after successful completion
- Input/build parameters
- Status
- Error information
- Game DSL artifact when available
- Lifecycle timestamps

Build status is backend-authoritative.

### BuildLog

Represents ordered build output.

Invariants:

- Must belong to a `BuildJob`.
- `ON DELETE CASCADE` removes logs when their parent build is intentionally deleted.
- Sequence numbers are ordered per build.
- `(build_id, sequence_number)` is unique.
- Logs must not be used as the authoritative build state; `BuildJob.status` is authoritative.

### PlaytestSession

Stores user/project-scoped gameplay telemetry and optional cached AI critique.

It must respect project/user ownership and must not become an alternate source of truth for project versions.

### SavedDiscovery

Stores a user's bookmark of a canonical catalog game.

Invariant:

`UNIQUE(user_id, steam_app_id)`

### Creator Progression

- `UserProgress`: current server-authoritative totals/level
- `XPEvent`: append-like XP history
- `UserMilestone`: unlocked milestone records
- `UserGenrePreference`: behavioral Game DNA signals

Progression state is server-authoritative.

## Ownership

Private user-specific entities must carry or derive ownership through server-side identity.

Cross-user access must be rejected at the service/API boundary.

Do not trust a `user_id` supplied in a client request as authoritative.

## Cascade Policy

Cascade behavior must be explicit per relationship.

Use cascade deletion only where dependent data has no independent business meaning.

Do not use broad cascades as a substitute for understanding retention requirements.

## Indexing

Indexes should support actual query patterns.

Do not add duplicate or redundant indexes merely because a column participates in a unique constraint.

Before deleting an index, verify:

- The underlying uniqueness guarantee remains.
- Required query performance does not regress.
- Migration upgrade/downgrade behaves correctly.

## Discovery Catalog

The offline catalog uses three conceptual layers:

### ORIGINAL

Raw source provenance.

### SEARCH

Canonicalized retrieval fields and semantic representations.

### DISPLAY

Human-facing normalized fields with provenance/source markers.

Search transformations must not destroy the raw provenance layer.

## Data Integrity

Critical invariants belong in the database where practical.

Application checks remain necessary for domain semantics, but correctness should not depend solely on race-prone pre-checks.

## Retention

Historical operational records must have an explicit retention policy before production.

Retention must:

- Define eligibility
- Never prune active work unintentionally
- Handle missing timestamps explicitly
- Be invoked by a deliberate maintenance mechanism
- Be observable
- Be testable

Never silently delete orphaned records.
