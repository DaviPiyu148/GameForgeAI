# ADR-003 — Structured Game DSL

**Status:** Accepted

## Decision
The LLM produces a structured Game DSL that is validated before entering the Phaser runtime.

## Required path
Prompt -> Intent -> GameSpec -> DSL -> Pydantic validation -> Repair -> Phaser.

## Rejected
LLM -> arbitrary HTML/JS or LLM -> Unity/Unreal source code as the initial runtime boundary.

## Consequence
The first supported game mechanics must be intentionally limited to what the renderer can reliably implement.
