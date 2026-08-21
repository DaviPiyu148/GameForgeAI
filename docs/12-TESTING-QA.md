# 12 — Testing and QA

## Current Baseline
GameForge AI maintains full test coverage across Backend API, Authentication & IDOR, Discovery 2.0–2.2, and Game Generation V2.

## Backend Test Levels
- **Unit**: services, schemas, validators, parsers, ranking, runtime compatibility, gameplay quality validator, PRNG.
- **Integration**: repositories, Alembic migrations, SQLite database, session transactions.
- **API**: request/response/error contracts (`/api/auth`, `/api/health`, `/api/projects`, `/api/builds`, `/api/discovery`, `/api/saved-discoveries`).
- **SSE**: live event streaming, initial replay, log deduplication, terminal state closing.
- **Browser regression**: all seven routes and primary user journeys across 1440px, 768px, and 375px viewports.

## Game Generation V2 Test Matrix
1. **GameDesignSpec Schema Validation**:
   - `test_game_design_spec_valid`: Validates complete specification structure, mechanics, abilities, objectives, and rationale.
   - `test_game_design_spec_script_injection_rejection`: Confirms rejection of `<script>`, `eval()`, `new Function`, and malicious code injection.
2. **Game DSL Expansion Primitives (v2.0)**:
   - `test_v2_expanded_primitives_validation`: Validates player dash speed/stamina, attack types, enemy behaviors (`ranged_attack`, `chase`, `guard`), and expanded rule triggers/actions.
   - `test_backward_compatibility_with_v1_dsl`: Verifies seamless compatibility with v1.0 GameDSL fixtures.
3. **Deterministic Gameplay Quality Validator**:
   - `test_quality_validator_detects_immediate_spawn_hazard`: Fails when player spawn clearance is < 60px from immediate danger.
   - `test_quality_validator_detects_collector_without_collectibles`: Fails when collector archetype lacks required collectible entities.
   - `test_quality_validator_passes_balanced_game`: Passes well-balanced, reachable gameplay specifications.
4. **Playtest Telemetry & IDOR Protection**:
   - `test_record_and_list_playtests`: Validates recording in-game session metrics and querying user-owned playtests.
   - `test_playtest_idor_protection`: Confirms User B receives HTTP 404 when querying User A's project playtest records.
5. **AI Playtest Critique & Iterative Improvement**:
   - `test_analyze_playtest_endpoint`: Generates structured critique ratings, strengths, problems, and actionable recommendations from gameplay telemetry.
   - `test_apply_improvements_and_version_bump`: Applies approved recommendation patches, bumps version (`version_number = 2`), and updates project DSL snapshot.

## Discovery Engine 2.0–2.2 Benchmark
- 98-query comprehensive multilingual benchmark (+133.3% Precision@5, 0% regressions).
- Three-layer metadata architecture (`ORIGINAL`, `SEARCH`, `DISPLAY`) with English display normalization and IGDB enrichment.

## Reporting Standards
Distinguish code verified, command verified, statically inferred, browser verified, and not verified. Never claim a browser test passed because source code looks correct.
