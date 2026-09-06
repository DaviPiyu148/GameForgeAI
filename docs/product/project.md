# 01 — Project Definition

## Document Role

This document defines the durable product purpose and boundaries of GameForge AI. It does not describe the current implementation snapshot; see [`docs/status/current-status.md`](../status/current-status.md) for that.

## Product

GameForge AI is an AI-powered game discovery and prototyping platform that reduces the gap between:

> “I wish a game like this existed.”

and:

> “I can play a prototype of it.”

The product connects semantic discovery with structured game generation, playable prototypes, playtesting, and controlled iteration.

## Problem

Traditional game stores primarily expose tags, categories, popularity, and keywords.

Users often describe desired experiences using richer concepts:

- Mood
- Pacing
- Mechanics
- Progression
- Theme
- Player mode
- Constraints
- Similar experiences

GameForge AI should understand this intent and either find an existing game that satisfies it or help create a constrained prototype when the desired experience is not adequately represented by the catalog.

## Target Users

- Gamers discovering unusual experiences
- Indie developers exploring concepts
- Students and hackathon teams
- Game designers and prototypers as a future expansion audience

## Core Value

**Discovery:** Describe the experience, not merely the tags.

**Generation:** When discovery is insufficient, build a constrained playable prototype.

**Iteration:** Let the developer inspect, playtest, understand, and explicitly evolve the generated result.

## Product Loop

```text
DESCRIBE
   ↓
UNDERSTAND
   ↓
DISCOVER
   ├── MATCH FOUND → INSPECT / SAVE / INSPIRE
   └── NO STRONG MATCH → BUILD
                         ↓
                      GENERATE
                         ↓
                      VALIDATE
                         ↓
                       PLAY
                         ↓
                      ANALYZE
                         ↓
                     MODIFY / REMIX
                         ↓
                       SAVE
                         ↓
                      REPLAY
```

## Architectural Product Principles

1. Natural language is the primary input.
2. Discovery and generation are connected but independently bounded systems.
3. Generated output is structured and validated before runtime execution.
4. Backend state is authoritative for persistent business data.
5. Developer control is explicit: meaningful changes create new versions rather than silently mutating history.
6. AI is used where it provides value; deterministic systems enforce safety, consistency, and runtime guarantees.
7. Existing games used as inspiration remain identifiable by their canonical catalog identity and are not treated as clone/rename templates.

## Hackathon Goal

Demonstrate:

- Natural-language understanding
- Semantic discovery
- Credible AI-assisted generation
- Structured validation
- A playable browser prototype
- Explainability
- Persistence
- Reliable recovery
- Controlled iteration

## Non-Goals

The initial product does not attempt to provide:

- AAA engine capabilities
- Arbitrary generated-code execution
- Foundation-model training
- A social network
- A microservice platform
- Unbounded game-mechanic support

## Success Criteria

A judge should be able to enter an unusual request, inspect intelligent matches, save or use an inspiration, build a prototype, observe believable generation progress, play it, inspect/modify it, and see the resulting state persist safely.

## Scope Discipline

New capabilities should be added through the project's phase process. Do not infer that a capability exists merely because a roadmap, design document, or future phase mentions it.
