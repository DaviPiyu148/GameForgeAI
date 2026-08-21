# 04 — System Architecture

## Style
Backend: Modular Monolith (FastAPI + SQLAlchemy + Pydantic v2 + SQLite/Alembic).
Frontend: React + Vite + Tailwind CSS + Phaser 3.88.2 Arcade Physics Runtime.

## Architecture
```text
React Frontend (Vite)
   | REST + SSE (Streaming Compiler Logs)
   v
FastAPI Modular API
   |
   +-- Project Service ----------> SQLite (Projects, ProjectVersions, PlaytestSessions)
   +-- Build Service ------------> BuildJob / BuildLog SSE Dispatcher
   +-- Discovery Service --------> FAISS Dense Vector Index + BM25 Lexical Normalization
   +-- AI Service ---------------> Hosted Gemini Provider (gemma-4-31b-it)
   +-- Game Generation Service --> Dual Schema & Gameplay Quality Validator
                                       |
                                       v
                               Phaser 2D Runtime
```

## System Boundaries
- **Frontend**: Presentation, input controls (WASD, dash, combat), Phaser canvas embedding, telemetry event emission, and UI state.
- **Backend**: Authoritative persistent state, build orchestration, Gemini AI prompting, dual validation, playtest session recording, and versioned improvement patching.

## Game Generation V2 Pipeline
1. **User Idea / Prompt** submitted to `POST /api/builds` with real configuration parameters (Profile preset, Visual density, Physics complexity, Logic modules).
2. **AI Game Design**: Gemini (`gemma-4-31b-it`) generates dual structured payload: `GameDesignSpec` (gameplay pillars, objectives, rationale) and `GameDSL` (schema v2.0 primitives).
3. **Dual Validation**:
   - **Schema Validation**: Pydantic v2 type and bound checks + script injection detection.
   - **Gameplay Quality Validation**: Deterministic clearance, reachability, win/loss rule fairness, and speed checks.
4. **Bounded AI Repair**: Errors fed back to Gemini (max 2 retries).
5. **Deterministic Runtime**: Seed-based procedural level generation, dynamic HUD, particle effects, smooth arcade locomotion, and wave spawner.
6. **Playtest Telemetry & AI Critique**: In-game session metrics tracked and analyzed by Gemini post-session, providing structured ratings and actionable DSL patches.
7. **Versioned Improvement**: User approves recommendations, creating Version 2+ with hot-reloaded prototypes.
