# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Primary:** Gamers seeking novel or niche game experiences from natural language descriptions who want to describe an idea and immediately test or play a prototype; indie game developers exploring game concepts quickly.
- **Secondary:** Hackathon participants, students, game designers, and creative prototypers testing experimental mechanics and game pitches.

## Product Purpose

GameForge AI reduces the gap between *"I wish a game like this existed"* and *"I can play a prototype of it."* It provides a unified platform to discover existing games from natural-language descriptions and generate playable 2D browser prototypes when no exact match exists or when exploring novel concepts.

Success means delivering high-relevance, explainable semantic game discovery and safe, structured, playable 2D game prototypes that users can test, tune, modify, save, and iterate upon.

## Positioning

A dual-mode experience that bridges natural language semantic game discovery (Sentence Transformers + FAISS catalog) and safe AI procedural game generation.

Unlike unconstrained AI code-generation tools that output fragile or insecure arbitrary JavaScript, GameForge AI enforces a strict structured safety boundary:
`Natural Language Prompt -> Intent/Specification -> Structured Game DSL -> Pydantic Schema Validation -> Repair/Retry -> Artifact -> Phaser 2D Runtime`.

## Operating Context

A browser-based web application with an immersive retro-futuristic cyberpunk terminal interface.

Key workflows include:
- **Semantic Discovery:** Natural language search with voice input, "Why This Matches" explanations, mood filters, and multi-game side-by-side comparison.
- **Game Builder:** Structured parameter controls (engine, art density, physics, logic modules), prompt crafting, and real-time architecture preview schematics.
- **Generation & Compilation:** Real-time build logs streamed via Server-Sent Events (SSE), automated DSL validation, and explicit error recovery.
- **Playtest Arena:** In-browser playable Phaser 2D canvas with keyboard/touch controls, debug HUD, and fullscreen capability.
- **Progression & Library:** Persistent project library with versioning, prompt iteration patching, and personalized Game DNA profile metrics.

## Capabilities and Constraints

- **Confirmed Capabilities:** Natural language discovery with similarity scoring; AI structured Game DSL generation; Phaser 2D game canvas execution; live build streaming via SSE; project and version persistence; user authentication (Argon2id); Game DNA onboarding and preference tuning.
- **Durable Constraints:** Exactly 7 primary routes (`#/`, `#/discover/no-matches`, `#/build`, `#/status/success`, `#/status/error`, `#/dashboard`, `#/profile`); strict safety boundary (no arbitrary JS evaluation; DSL -> Schema validation -> Phaser); backend authoritative for persistent state; SQLite/SQLAlchemy with FastAPI backend.
- **Domain Terminology:** Game DSL, Game DNA, BuildJob, PlaytestSession, Intent Schema, Semantic Similarity, Match Explanation.

## Brand Commitments

- **Name:** GameForge AI
- **Visual Aesthetic:** Retro-Futuristic Terminal / Cyberpunk aesthetic with deep dark backgrounds (`#0a0d14`), high-contrast neon glowing accents (Cyan `#4ce0d2`, Magenta `#ff3d81`, Amber `#ffc24c`), sharp or micro-radii pane borders, and subtle scanline/glassmorphism treatments.
- **Typography:** Press Start 2P (Headlines & Display), Space Grotesk (Body & Paragraphs), JetBrains Mono (Technical, Code, Prompts, & Navigation).
- **Voice & Tone:** Technical, confident, immersive, and precise hacker/creator tone with system-level diagnostic messaging (`[SYS]`, `[MOD]`, `SYS_ONLINE`).

## Evidence on Hand

- **Frontend:** Finished React + TypeScript + Vite + Tailwind CSS application (`gameforge-ai/`) with 7 primary routes, custom UI components, and Phaser game canvas integration.
- **Backend:** Fully implemented FastAPI backend (`backend/app/`) with SQLAlchemy models, Alembic migrations, SSE build streaming, discovery engine, and Game DSL validators.
- **Design & Architecture:** Documented design system ([`DESIGN.md`](./DESIGN.md)), canonical documentation hierarchy ([`docs/README.md`](./docs/README.md)), accepted ADRs ([`decisions/`](./decisions/)), and comprehensive test suites.
- **Absences & Non-Goals:** No arbitrary 3D game engines (MVP is strictly Phaser 2D), no unvalidated LLM code execution, no multi-tenant social network in MVP.

## Product Principles

1. **Natural Language First:** Express game ideas and queries naturally; the system translates rich intent (mood, pacing, mechanics, constraints) into structured specifications.
2. **Discovery and Generation Connected:** Discovery transitions smoothly to prototyping when matches are sparse or when a user wants to forge an original concept.
3. **Explainable by Design:** Recommendations and generation decisions provide clear transparency (e.g., "Why This Matches", real-time compiler build steps).
4. **Safety and Reliability Over Chaos:** Guarantee runtime stability and safety through strict Pydantic DSL schema validation, repair loops, and deterministic Phaser interpretation.
5. **Fast Feedback and Iteration:** Keep build cycles responsive with live SSE streaming, instant in-browser playtesting, and prompt-driven patching.

## Accessibility & Inclusion

- Keyboard navigation support across all controls, modals, and game arena interactions.
- Full compliance with `prefers-reduced-motion` for glows, pulses, animations, and scanline overlays.
- High contrast ratios maintained for text against dark surfaces (`#e1e2ec` on `#0a0d14` / `#10131a`).
- Descriptive ARIA labels for custom terminal inputs, sliders, and status chips.
