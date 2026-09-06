# Game Generation Pipeline V2 — Quality, Depth & Capability Contract

## 1. Overview & Objectives

Game Generation Pipeline V2 delivers a deterministic structural and design quality evolution for GameForge AI. The generation pipeline advances from basic syntactic validation to deep, cohesive, capability-aware, scale-appropriate game creation with explicit requirement tracking and verified cross-system interaction rules.

### Core Guarantees:
1. **Zero New External Infrastructure**: Powered entirely by the existing single-call Google Gemini API provider + local deterministic compiler pipeline.
2. **Deterministic Quality Gates**: Games are evaluated across 7 weighted design axes with scale-aware thresholds (Prototype $\ge$ 60, Standard $\ge$ 68, Campaign $\ge$ 72).
3. **Canonical Runtime Capability Registry**: Strict allowlist of supported Phaser 3.88.2 Arcade features. Unsupported features (e.g. dynamic NPC memory, 3D meshes, multiplayer) are detected upfront and rejected without silent schema deletion.
4. **Verified Cross-System Interaction**: Co-existence of subsystems is strictly distinguished from actual gameplay interaction.
5. **Exact 10-Stage Compiler Pipeline**: 10 deterministic stages emitted via SSE.

---

## 2. Architecture & Subsystems

```
USER BUILD REQUEST (Prompt + Engine + Scale + Modules)
                      │
                      ▼
STAGE 1: Understanding game request (build_generation_contract)
                      │
                      ├─▶ Check Unsupported Concepts (e.g. NPC memory, 3D) -> Strict rejection
                      ▼
STAGE 2: Building game design (Core loop formulation)
                      │
                      ▼
STAGE 3: Mapping runtime capabilities (Capability registry allowlist)
                      │
                      ▼
STAGE 4: Generating GameDSL (1 Gemini structured generation call)
                      │
                      ▼
STAGE 5: Schema validation (Pydantic models)
                      │
                      ▼
STAGE 6: Gameplay quality (GameDepthEvaluator & RequirementCoverageMatrix)
                      │
                      ▼
STAGE 7: Deterministic normalization/repair (Unambiguous auto-repair: e.g. implied finale)
                      │
                      ▼
STAGE 8: Runtime compilation (Phaser Arcade physics compiler)
                      │
                      ▼
STAGE 9: Runtime verification (Procedural seed & spatial reachability)
                      │
                      ▼
STAGE 10: Build complete (Persistence & 0x00_SYS_READY)
```

---

## 3. The 10 Deterministic Compiler Stages

1. `("SYS", "Understanding game request")`
2. `("AI", "Building game design")`
3. `("AI", "Mapping runtime capabilities")`
4. `("AI", "Generating GameDSL")`
5. `("VALIDATION", "Schema validation")`
6. `("VALIDATION", "Gameplay quality")`
7. `("REPAIR", "Deterministic normalization/repair")`
8. `("PHASER", "Runtime compilation")`
9. `("PHASER", "Runtime verification")`
10. `("SYS", "Build complete")`

---

## 4. Quality Scoring & Weight Distribution

The `GameDepthEvaluator` computes a deterministic score (0–100) using centralized weights defined in `generation_config.py`:
- **Core Loop Completeness**: 25.0%
- **Objective Clarity & Diversity**: 15.0%
- **Progression & Escalation**: 15.0%
- **Content Variety (Behaviors & Themes)**: 15.0%
- **Mechanic / Requirement Coverage**: 15.0%
- **Verified Cross-System Interaction**: 10.0%
- **Finale / Climax Quality**: 5.0%

---

## 5. Requirement Confidence & Coverage Rules

Requirements extracted during request understanding are tagged with confidence:
- `EXPLICIT_REQUIREMENT`: Directly mentioned features or active builder modules. Missing these triggers failure.
- `INFERRED_PREFERENCE`: Theme/genre implications.
- `OPTIONAL_INTERPRETATION`: Secondary stylistic elements.

### Cross-System Rules:
- **Vehicle $\rightarrow$ Traversal**: Verified only if vehicles have speed advantages and open-world districts exceed 1000px dimensions.
- **Threat $\rightarrow$ Activities**: Verified only if threat escalates on combat defeat or activities link to threat states.
- **Faction $\rightarrow$ Activities**: Verified only if activities/missions explicitly reference faction alignments.
- **Collectibles $\rightarrow$ Objectives**: Verified only if `on_collect` rules affect score or win conditions.

---

## 6. Verification Results

- **Automated Quality Suite**: `pytest tests/test_generation_quality_v2.py -v` (7 passed in 0.07s).
- **Core Generation & Build Suite**: `pytest tests/test_builds.py tests/test_game_generation.py tests/test_generation_resilience.py tests/test_gameplay_quality.py -q` (42 passed in 1.71s).
- **Quality Benchmark**: `python scripts/evaluate_generation_quality_v2.py` (10/10 test cases passed, 93.3 mean score, 76.2% coverage, 1.18ms mean evaluation latency).
- **Frontend Verification**: Clean `oxlint` (0 warnings, 0 errors) and `npm run build` success.
- **Browser Testing**: `BROWSER TESTING: NOT PERFORMED` (per explicit instruction).
