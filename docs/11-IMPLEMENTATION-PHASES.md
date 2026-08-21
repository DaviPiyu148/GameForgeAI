# 11 — Implementation Phases

## Rule
One phase at a time. Implement -> verify -> document -> obtain approval.

## Frontend F0-F5 (COMPLETE)
Initialization, shared design system, seven primary routes, state management, motion/QA.

## Backend Foundation & Core Phases B0–B7 (COMPLETE)
- **B0**: FastAPI + SQLite foundation
- **B1**: Project persistence & CRUD
- **B2**: Async Build jobs & SSE log streaming
- **B3**: Hosted AI generation & Game DSL Schema v1.0
- **B4**: Dense FAISS semantic discovery
- **B5**: Phaser 3.88.2 Arcade Physics renderer & prototype runtime
- **B6**: Full frontend-backend API integration
- **B7**: Argon2 authentication, JWT tokens, IDOR ownership protection, saved discoveries

## Discovery Engine 2.0–2.2 (COMPLETE)
- **D1–D10**: Hybrid dense semantic (FAISS) + lexical (BM25) search, calibrated score bands, rich match explanations, IGDB metadata enrichment, and Game DNA build-inspiration extraction.
- **Multilingual 2.1 & Display Normalization 2.2**: Three-layer catalog metadata architecture (`ORIGINAL`, `SEARCH`, `DISPLAY`), landmark descriptions in clean English, 98-query evaluation (+133.3% Precision@5, 0% regressions).

## Game Generation V2 (COMPLETE — Subtasks G1–G16)
- **G1**: End-to-end architecture audit.
- **G2**: Structured Game Design Specification (`GameDesignSpec` schema).
- **G3**: Game DSL Expansion (Player dash, stamina, attack types; Entity behaviors; Rule triggers & actions; World difficulty scaling).
- **G4**: Real Builder parameter integration (Engine profiles, Art density, Physics complexity, Logic modules).
- **G5**: Deterministic Gameplay Quality Validator (Player clearance, win/loss rules, balance bounds).
- **G6**: Enhanced Phaser Runtime (Locomotion physics, dash mobility, projectile combat, particle bursts, screen shake, escalating waves, dynamic HUD).
- **G7**: Deterministic Procedural Level Generation with static reachability validation.
- **G8**: Non-intrusive in-game Playtest Telemetry Tracker.
- **G9**: AI Playtest Critique Analysis (Structured ratings, strengths, problems, actionable recommendations).
- **G10**: Interactive AI Improvement Workflow (Recommendation selection, targeted DSL patching).
- **G11**: Live Compiler Output & Real Structured Design Logs via SSE.
- **G12**: Versioning & Persistence (`playtest_sessions`, `project_versions`, `current_version`, Alembic migration `c3d4e5f6a7b8`).
- **G13**: Automated Test Suite (Schema, Quality Validator, Playtests, Improvements, Full 140+ test regression).
- **G14**: Live Browser Verification across 1440px, 768px, and 375px viewports.
- **G15**: System Architecture & QA Documentation update.
- **G16**: Mandatory Git Checkpoint (`feat: evolve ai game generation pipeline`).

## Next Phase
- **B8**: Hardening, observability, and production deployment.
