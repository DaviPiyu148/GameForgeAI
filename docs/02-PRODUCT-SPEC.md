# 02 — Product Specification

## Principles
- Natural language first.
- Discovery and generation are connected.
- Recommendations are explainable.
- Generated results are structured and validated.

## Intent
Input starts as unstructured text. The system may extract fields such as theme, genre, tone, pacing, player mode, constraints, and progression. The schema should remain intentionally small for the MVP.

## Discovery
Prompt -> intent -> embedding -> candidate retrieval -> hard filters -> ranking -> explanations. Strong matches show results; weak/no matches lead to the build path without requiring a new primary route.

## Build
Builder controls include prompt, engine, art density, physics, and logic modules. These become structured build parameters.

## Generation
A build is a backend-owned asynchronous job. Success produces a validated Game DSL, project record, and playable artifact/configuration. Failure is explicit and recoverable.

## Modification
User can request natural-language changes. Prefer structured patches/version creation over unconstrained full regeneration.

## Persistence
Persistent objects eventually include User, Project, ProjectVersion, BuildJob, GameArtifact, Discovery, and SavedDiscovery.

## State Ownership
Frontend: UI/transient state. Backend: persistent business state and build truth.
