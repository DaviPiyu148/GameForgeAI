# AI Game Generation Architecture

## 1. Scope & Core Guarantees

This document defines the canonical architecture and contract for the **Game Generation Pipeline** in GameForge AI.

The pipeline translates natural-language prompts and interactive builder controls into structured, validated, and executable `GameDSL` schemas running in Phaser 3.88.2 Arcade Physics.

### Core Guarantees
1. **AI Safety & Sandbox Boundary**: Never execute raw or arbitrary LLM-generated code (`LLM → arbitrary JavaScript → browser` is strictly forbidden). LLMs emit structured data adhering to strict Pydantic schemas.
2. **Deterministic Quality Gates**: Games are evaluated across 7 weighted design axes with scale-aware thresholds (Prototype $\ge 60$, Standard $\ge 68$, Campaign $\ge 72$).
3. **Canonical Runtime Capability Registry**: Strict allowlist of supported 2D Arcade capabilities. Unsupported concepts (3D meshes, dynamic NPC dialogue trees, multiplayer) are rejected upfront during request analysis.
4. **Verified Cross-System Interaction**: Subsystems (Vehicles, Factions, Threat, Activities) must have verified data and gameplay linkages; passive co-existence in metadata is penalized.
5. **Two-Stage Resilience Pipeline**: Harmless schema drift is normalized locally with **0 LLM repair calls**; semantic repair is bounded to a maximum of 1 attempt with a dedicated 45s timeout.
6. **Exact 10-Stage Compiler Pipeline**: Structured compiler events are streamed to the frontend via Server-Sent Events (SSE).

---

## 2. The 10-Stage Deterministic Compiler Pipeline

```text
USER BUILD REQUEST (Prompt + Engine + Scale + Modules)
                      │
                      ▼
STAGE 1: Understanding game request (build_generation_contract)
                      │ └─▶ Rejects unsupported concepts upfront
                      ▼
STAGE 2: Building game design (Core loop & GameDesignSpec formulation)
                      │
                      ▼
STAGE 3: Mapping runtime capabilities (Capability registry allowlist)
                      │
                      ▼
STAGE 4: Generating GameDSL (1 Gemini structured generation call)
                      │
                      ▼
STAGE 5: Schema validation (Pydantic models with extra="forbid")
                      │
                      ▼
STAGE 6: Gameplay quality (GameDepthEvaluator & RequirementCoverageMatrix)
                      │
                      ▼
STAGE 7: Deterministic normalization / repair (Local drift recovery or 1 bounded semantic repair)
                      │
                      ▼
STAGE 8: Runtime compilation (Phaser Arcade physics bytecode/config compiler)
                      │
                      ▼
STAGE 9: Runtime verification (Procedural seed & spatial reachability check)
                      │
                      ▼
STAGE 10: Build complete (Persistence & 0x00_SYS_READY)
```

### SSE Compiler Stage Events
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

## 3. Structured Design Specifications

### 3.1 `GameDesignSpec`
Acts as the intermediate design representation between user intent and executable DSL:
- **Core Identity**: Title, pitch, genre, subgenre, theme, visual style, camera perspective.
- **Gameplay Definition**: Core gameplay loop, player role, primary & secondary objectives, movement/combat abilities.
- **Encounter Architecture**: Enemy archetypes (`basic`, `fast`, `ranged`, `heavy`, `elite`, `boss`), hazards, collectibles.
- **Progression & Pacing**: Difficulty curve, stage transitions, win/loss conditions, estimated session length.
- **Selected Modules & Rationale**: Explicit feature requirements (vehicles, factions, threat, POIs).

### 3.2 `GameDSL`
The strict runtime contract interpreted by the Phaser Arcade engine:
- **Player Definition**: Speed, max health, dimensions, role silhouette, weapon attributes, abilities (dash, shoot).
- **Entity Definitions**: Typed enemies with behaviors (`patrol`, `chase`, `ranged_attack`, `guard`), collectibles, hazards, landmarks.
- **Rule Engine**: Event triggers (`on_collect`, `on_collide_enemy`, `on_reach_goal`, etc.) bound to executable actions (`add_score`, `damage_player`, `spawn_wave`, etc.).
- **World & Level Models**: Multi-level stages, dimensions, gravity, procedural seeds, boundary walls, and finale flags.
- **Open World Subsystems**: Regions, POIs, vehicles, factions, activities, threat meters, and world events.

---

## 4. Deterministic Quality Gates & Scoring

The `GameDepthEvaluator` computes a deterministic quality score ($0–100$) across 7 weighted design axes:

| Quality Axis | Weight | Evaluation Criteria |
| :--- | :---: | :--- |
| **Core Loop Completeness** | **25.0%** | Clear progression from spawn $\rightarrow$ action $\rightarrow$ objective $\rightarrow$ victory condition. |
| **Objective Clarity & Diversity** | **15.0%** | Explicit win conditions; adjacent stage objectives must differ (no repetitive `collect_all` across 100% of levels). |
| **Progression & Escalation** | **15.0%** | Increasing challenge curve across levels or waves; presence of multi-threat combinations. |
| **Content Variety** | **15.0%** | Diverse enemy behaviors (mix of melee, ranged, fast chasers) and thematic visual palettes. |
| **Requirement Coverage** | **15.0%** | Satisfaction of explicit prompt requirements and active builder modules. |
| **Cross-System Interaction** | **10.0%** | Verified linkages between subsystems (e.g. vehicles provide speed advantage across large regions; activities target factions). |
| **Finale & Climax Quality** | **5.0%** | Dedicated boss encounter (health $\ge 150$, rage thresholds) or high-intensity extraction. |

### Scale-Aware Quality Thresholds
- **`prototype`**: Quality Score $\ge 60$ (Allows simple, focused single-level mechanics).
- **`standard`**: Quality Score $\ge 68$ (Requires multi-threat variety and clear pacing).
- **`campaign`**: Quality Score $\ge 72$ (Requires multi-stage escalation, diverse objectives, and climax finale).

---

## 5. Design Pattern Library & Composition Matrix

### 5.1 Deterministic Design Patterns (`design_patterns.py`)
To prevent shallow "move-shoot-collect" clones, generation selects from 9 structural patterns:
- **Campaign**: `CP_PROGRESSIVE_ESCALATION` (Intro $\rightarrow$ Combine $\rightarrow$ Pressure $\rightarrow$ Boss), `CP_COMBAT_TRAVERSAL` (Sweep $\rightarrow$ Skirmish $\rightarrow$ Extraction).
- **Open World**: `OW_ACTIVITY_ESCAPE` (Recon $\rightarrow$ Infiltration $\rightarrow$ Evade $\rightarrow$ Safehouse), `OW_FACTION_REPUTATION` (Hub $\rightarrow$ Contested Zone $\rightarrow$ Rival Confrontation $\rightarrow$ Liberation), `OW_VEHICULAR_TRAVERSAL` (Depot $\rightarrow$ Highway Run $\rightarrow$ Roadblock $\rightarrow$ Dropoff).
- **Arena & Survival**: `AR_WAVE_ESCALATION` (Scout Swarm $\rightarrow$ Pursuit $\rightarrow$ Barrage $\rightarrow$ Overlord), `AR_RESOURCE_ATTRITION` (Containment $\rightarrow$ Depletion $\rightarrow$ Surge $\rightarrow$ Resolution).
- **Platformer & Collector**: `PF_PRECISION_TRAVERSAL` (Fundamentals $\rightarrow$ Hazards $\rightarrow$ Vertical Ascent $\rightarrow$ Summit Beacon), `CO_PATROL_SWEEP` (Outer Perimeter $\rightarrow$ Guarded Vault $\rightarrow$ Core Chamber).

### 5.2 Canonical Composition Matrix (`composition_matrix.py`)
Enforces verified cross-system relationships:
- `VEHICLE_TO_TRAVERSAL`: Vehicle speed $>$ player speed across regions $\ge 1000\text{px}$.
- `THREAT_TO_ACTIVITY`: Combat activities escalate threat meters and trigger reinforcements.
- `FACTION_TO_ACTIVITY`: Activities directly name and reward faction standings.
- `COLLECTIBLE_TO_OBJECTIVE`: `on_collect` rules affect score, health, or win conditions.

---

## 6. Two-Stage Generation Resilience

```text
RAW AI OUTPUT
      │
      ▼
STAGE 1: Parsing & Security Scanning
- Strip markdown fences (```json ... ```) & thought tags (<thought>)
- Security scanner: fast fail on unsafe keys (runtime_script, eval, <script>) with 0 repair calls
      │
      ▼
STAGE 2: Deterministic Normalization (dsl_normalizer.py) [0 Provider Calls]
- Level world migration: maps levels[i].width/height into levels[i].world
- Safe scalar coercion (numeric strings -> ints/floats, hex color normalization)
- Legacy alias mapping (spawn_x <- x, max_health <- health, points <- score)
- Entity synonym mapping & safe field stripping
      │
      ▼
STAGE 3: Strict Pydantic Validation (validator.py)
- GameDSL.model_validate(normalized) with extra="forbid"
      │
      ▼
STAGE 4: Quality & Feasibility Evaluation
- Evaluates 7 quality axes, rule liveness, and reachability
      │
      ▼
STAGE 5: Bounded Semantic Repair Loop (game_generation_service.py) [Max 1 Call]
- Triggered ONLY on genuine semantic validation failures
- Bounded to 1 attempt (AI_REPAIR_MAX_ATTEMPTS = 1) with dedicated AI_REPAIR_TIMEOUT_SECONDS = 45.0s
      │
      ▼
STAGE 6: Phaser Runtime Compilation & Immutable Version Persistence
```

---

## 7. Remix, Blueprint & Telemetry Critique

### 7.1 Structured Remix
- Remix intents are selected from a closed vocabulary (e.g. `add_combat`, `increase_difficulty`, `add_boss_level`, `expand_open_world`).
- Duplicate or contradictory intents are rejected before invoking AI models.
- Successful remixes undergo the identical 10-stage validation pipeline and create an immutable `ProjectVersion`.

### 7.2 Game Blueprint
- A non-technical, allowlist-derived projection of validated project design state.
- Derived strictly from validated DSL rules and capability predicates; never hallucinates unsupported features.

### 7.3 Playtest Telemetry & AI Critique
- Captures in-game events (deaths, accuracy, time-to-objective, collectibles).
- Evaluates telemetry to generate targeted ratings and actionable DSL-patch recommendations.
