# ADR-003 — Structured Game DSL

**Status:** Accepted

## Context

GameForge AI uses an LLM to transform natural-language game ideas into playable browser prototypes.

Allowing an LLM to emit arbitrary executable JavaScript would create an unacceptable trust boundary: generated content could bypass application safeguards, execute unintended behavior, and make validation and reproducibility difficult.

The generated representation therefore needs to be constrained, typed, versionable, and compatible with the GameForge runtime.

## Decision

The LLM must produce a structured **Game DSL** rather than arbitrary executable source code.

Required flow:

```text
Prompt
  ↓
Intent
  ↓
GameSpec
  ↓
Game DSL
  ↓
Pydantic/schema validation
  ↓
Bounded repair
  ↓
Validated artifact
  ↓
Phaser runtime
```

The backend remains authoritative for validation and compilation.

## Security Boundary

Never implement:

```text
LLM → arbitrary JavaScript → browser execution
```

Never treat LLM output as trusted code.

LLM output must be validated against an explicit schema and a constrained capability set before it can enter the runtime.

## DSL Requirements

The DSL should provide:

- Explicit schema/version information
- Typed values
- Enumerated/allowlisted capabilities
- Explicit entities/mechanics where supported
- Bounded collection sizes
- Resource/complexity limits where applicable
- Deterministic interpretation by the compiler/runtime
- Clear validation errors
- Forward/backward compatibility rules where versioning requires them

Unknown or unsupported capabilities must be rejected or deliberately normalized; do not silently invent semantics.

## Validation and Repair

Validation must happen before runtime execution.

A bounded repair loop may correct invalid structured output, but repair must remain:

- Deterministic where practical
- Schema-constrained
- Bounded
- Observable

Repair must never become an unconstrained prompt loop.

## Runtime Compatibility

The DSL is a contract with the renderer/compiler.

The set of supported game mechanics must be intentionally limited to behavior the renderer can reliably implement.

Compiler output must reflect the validated DSL and active project configuration. Client input must not override server-authoritative build state.

## Versioning

If the DSL schema changes incompatibly:

- Introduce an explicit schema/version transition.
- Preserve the ability to identify which schema produced an artifact.
- Consider migration/compatibility before changing existing persisted projects.

## Rejected

- LLM → arbitrary HTML/JavaScript
- LLM → arbitrary Python/server code
- LLM → Unity/Unreal source as the initial execution boundary
- Executing unvalidated LLM output
- Unlimited self-repair loops

## Consequences

### Positive

- Strong security boundary.
- Deterministic runtime behavior.
- Easier validation/testing.
- Easier provider/model replacement.
- Artifacts can be inspected, persisted, and reproduced.

### Negative

- The initial mechanic set is intentionally constrained.
- New capabilities require DSL, validation, compiler, and runtime support.
- Some natural-language requests cannot be implemented exactly and must be rejected or mapped to supported behavior.
