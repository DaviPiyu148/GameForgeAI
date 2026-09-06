# 02 — Product Specification

## Principles

- Natural language first.
- Discovery and generation are connected.
- Recommendations are explainable and evidence-grounded.
- Generated results are structured and validated.
- Persistent state is backend-authoritative.
- Meaningful changes are versioned and reversible where practical.
- Explicit developer actions control builds and remixes.

## Intent Understanding

Input begins as unstructured natural language.

The system may extract structured concepts such as:

- Theme
- Genre/subgenre
- Tone
- Pacing
- Player mode
- Mechanics
- Progression
- Constraints
- Desired similarity

The intent schema should remain constrained to concepts the downstream systems can actually honor.

Unknown or unsupported concepts must not be silently treated as implemented capabilities.

## Discovery

Conceptual flow:

```text
Prompt
  ↓
Intent / query classification
  ↓
Semantic + lexical retrieval
  ↓
Hard constraints
  ↓
Ranking
  ↓
Grounded evidence / explanation
  ↓
Optional enrichment
```

Strong matches should surface clearly.

Weak/no-match states should provide a coherent transition to the build path without inventing unsupported results.

Discovery must preserve explicit constraints and avoidances.

## Build

Builder controls become structured build parameters, including:

- Prompt
- Engine/runtime profile
- Art density
- Physics complexity
- Logic modules
- Scale
- World mode

The backend owns the authoritative build request and lifecycle.

## Generation

A build is a backend-owned asynchronous job.

Successful generation produces:

- Validated `GameDesignSpec`
- Validated `GameDSL`
- Runtime metadata
- Persisted project/version state
- Playable runtime configuration

Failure must be explicit, observable, and recoverable where practical.

## Modification

Prefer structured modifications and version creation over unconstrained full regeneration.

AI-assisted changes must pass the same validation/runtime compatibility boundaries as fresh generation.

The developer must explicitly approve meaningful remix/improvement operations.

## Persistence

The current persistent model includes:

- User
- Project
- ProjectVersion
- BuildJob
- BuildLog
- SavedDiscovery
- PlaytestSession
- UserProgress
- XPEvent
- UserMilestone
- UserGenrePreference

The discovery catalog is a normalized offline dataset, not a per-user business entity.

There is no separate `GameArtifact` business table; the generated artifact is represented through the project's validated DSL and runtime metadata.

## State Ownership

**Frontend:** presentation, transient UI state, local drafts, interaction state.

**Backend:** authentication truth, ownership, persistent business state, build truth, project/version state, playtest persistence, progression state, discovery personalization state where persisted.

The frontend must not be treated as an authority for backend success or ownership.

## Versioning

Historical project versions are immutable.

A meaningful approved modification creates a new `ProjectVersion`.

Stale proposals or concurrent modifications must not silently overwrite newer versions.

## UX States

Every major workflow should define:

- Loading
- Empty
- Success
- Error
- Disabled
- Conflict/stale state where applicable

User-visible failures should explain what happened without exposing internal implementation details.
