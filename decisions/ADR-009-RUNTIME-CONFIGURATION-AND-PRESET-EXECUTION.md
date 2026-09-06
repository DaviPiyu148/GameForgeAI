# ADR-009 — Phaser Runtime Architecture, Configuration Compilation & Archetype Policy Execution

**Status:** Accepted

## Context

The GameForge AI platform generates expressive game configurations represented as `GameDSL` schemas encompassing 6 archetypes (`platformer`, `arena`, `shooter`, `collector`, `survival`, `runner`), 3 world architecture modes (`linear`, `campaign`, `open_world`), 3 game scale tiers (`prototype`, `standard`, `campaign`), hierarchical stage levels, multi-objective semantics, and open-world entities.

Prior to this architectural hardening, the client-side Phaser runtime exhibited several critical fidelity and stability defects:
1. **P0-001 / Rule Recursion:** `on_score_target` rules executing `add_score` triggered unbounded recursive call cycles leading to call stack exhaustion.
2. **P0-002 / Wave Recursion:** Synchronous event propagation during `on_wave_start` invoking `spawn_wave` triggered uncontrolled re-entrant wave increments.
3. **P1-003 / Objective Fidelity:** The runtime evaluated only collectible counts, ignoring explicit `ObjectiveDef` types (`collect_all`, `defeat_all`, `reach_exit`, `survive_time`, `score_target`).
4. **P1-004 / Campaign Level-Local Configuration:** Multi-level campaign stages were flattened, ignoring level-specific world bounds, local gravity, player spawn points, and stage-specific rules.
5. **P1-005 / Archetype Reduction:** Archetypes were collapsed into a binary `isPlatformer` check, neglecting melee combat, weapon mechanics, and archetype-specific physics.
6. **P1-006 / Open-World Semantic Leaks:** Open-world region transitions leaked floating UI labels and bypassed prerequisite state locks (`required_state_key`).
7. **P1-007 / Scale Tier Representation:** Scale tier budgets were not compiled into stage bounds or entity caps.
8. **P1-008 / PRNG Drift:** Scene restarts perturbed the procedural seed with `Math.random()`, breaking playthrough determinism.
9. **P1-009 / Backend Field Pruning:** The backend normalization pass pruned canonical open-world fields (`activity_ids`, `start_poi_id`, `target_count`, `prerequisites`, `success_consequences`).

## Decision

GameForge AI adopts a modular, contract-driven runtime execution architecture built around 8 core subsystems:

```
┌─────────────────────────────────────────────────────────────┐
│                    GameDSL Specification                    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│          RuntimeConfigCompiler (Stage Compilation)          │
│  - Merges Stage-Local Levels with Global World/Rules        │
│  - Computes Scale Tier Budgets & Wave Capping               │
│  - Validates Mode/Archetype Compatibility Matrix            │
└──────────────────────────────┬──────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│ArchetypePolicy│      │ObjectiveEngine│      │WaveController │
│- Movement Mod.│      │- collect_all  │      │- State Machine│
│- Melee/Ranged │      │- defeat_all   │      │- Re-entrancy  │
│- Jump/Gravity │      │- reach_exit   │      │  Notification │
│- Capabilities │      │- survive_time │      │  Lock         │
│               │      │- score_target │      │- Max Capping  │
└───────┬───────┘      └───────┬───────┘      └───────┬───────┘
        │                      │                      │
        └──────────────────────┼──────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│              Phaser GameScene Execution Kernel              │
│  - Re-entrancy Guarded RuleEngine (MAX_EXECUTION_DEPTH = 6) │
│  - Decoupled Score Threshold Evaluator                      │
│  - Managed OpenWorld Entity & UI Lifecycle (openWorldLabels)│
│  - Deterministic PRNG Seed Preservation                     │
└─────────────────────────────────────────────────────────────┘
```

### 1. Stage Compilation Layer (`RuntimeConfigCompiler`)

The runtime never executes raw, un-compiled DSL directly in scene update loops. Instead, `RuntimeConfigCompiler.compile()` transforms the DSL into an immutable `RuntimeGameConfig` containing resolved `RuntimeStageConfig` elements:
- **Hierarchical Fallback:** Stage configuration resolves level-specific properties (`world`, `spawn_x`, `spawn_y`, `rules`, `objective`) when present in `dsl.levels[i]`, falling back to global `dsl.world`, `dsl.player`, and `dsl.rules`.
- **Atomic Stage Transition:** Advancing to the next campaign level atomically swaps stage physics bounds, camera bounds, gravity, rule engines, and objective evaluators.
- **Incompatible Combination Rejection:** Safe validation rejects illegal combinations (e.g. `platformer` archetype with `open_world` mode) with actionable error diagnostics.

### 2. Authoritative Objective Engine (`ObjectiveEvaluator`)

Game outcomes are determined solely by the `ObjectiveEvaluator`:
- **Supported Types:**
  - `collect_all`: Tracks gathered items against total required count.
  - `defeat_all`: Tracks defeated enemy count against required target.
  - `reach_exit`: Evaluates Euclidean distance between player coordinates and exit portal radius.
  - `survive_time`: Decrements delta-time countdown to zero without player death.
  - `score_target`: Verifies player score against target point threshold.
- **Terminal Latching:** Once an objective transitions to `COMPLETED` or `FAILED`, the evaluator locks state, preventing post-terminal regressions.

### 3. Synchronous Execution-Path Rule Engine (`RuleEngine`)

- **Execution Path Tracking:** Cycle detection tracks the exact synchronous call path (`activeRuleIds: Set<string>` and `activeExecutionStack: RuleExecutionFrame[]`) on the path:
  `Rule -> Action -> Emitted Trigger -> Rule`
- **Selective Termination:** If a rule already present in the active synchronous execution stack is invoked again, execution terminates immediately for that cycle, logging the cyclic chain diagnostic while preserving independent rules listening to the same trigger.
- **Legitimate Causal Chains:** Linear trigger chains (e.g. `A -> B -> C -> D`) execute cleanly without false-positive suppression.
- **Score Threshold Decoupling & Re-arming:** Threshold crossings trigger rules once per crossing. If score drops below the threshold and crosses it again, the rule re-arms and fires legitimately.
- **Static Cycle Analysis:** `RuleEngine.validateRuleGraph(rules)` performs pre-flight cycle detection on declared rule networks.
- **Defensive Call-Stack Depth Limiter:** Enforces `MAX_EXECUTION_DEPTH = 6` as an auxiliary ceiling.

### 4. Wave Controller State Machine (`WaveController`)

Wave progression is governed by an explicit finite state machine (`IDLE` -> `SPAWNING` -> `ACTIVE` -> `COMPLETED`):
- **Separation of Request and Notification:** `requestNextWave()` is cleanly decoupled from `on_wave_start` notifications.
- **Notification Re-entrancy Lock (`isNotifying`):** Prevents synchronous action cascades triggered by `on_wave_start` rules from recursively calling `spawnWave()`.
- **Terminal Progression Lock:** Transitions to `WON`, `LOST`, or `DESTROYED` irrevocably disable all future wave spawning.
- **Wave Capping:** Enforces `maxWaves` boundary based on scale tier and stage configuration.

### 5. Archetype Capability & Policy Matrix (`ArchetypePolicy`)

Archetype policies are defined in a typed matrix:
- **`platformer`:** 2D platformer movement, horizontal velocity control, discrete jump power (`allowVerticalMovement: false`, `requiresGravity: true`, `allowsEnemyWaves: false`, `defaultAttackType: 'melee'`, prohibited in `open_world`).
- **`arena`:** Top-down 8-directional movement, melee & dash mobility, multi-wave enemy combat (`requiresGravity: false`, `allowsEnemyWaves: true`, `defaultAttackType: 'melee'`).
- **`shooter`:** Top-down 8-directional movement, diagonal normalization, directional projectile weapon firing (`defaultAttackType: 'ranged'`).
- **`collector`:** Top-down movement, resource magnet, non-combat primary loop (`defaultAttackType: 'none'`, prohibited from wave combat).
- **`survival`:** Top-down evasion and timed survival against escalating pressure.
- **`runner`:** Continuous horizontal progression, jumping allowed if gravity configured (`allowVerticalMovement: false`, prohibited in `open_world`).

### 6. Open-World Subsystems & Memory Isolation

- **Authoritative World Mode:** `world.world_mode` strictly governs mode resolution; open-world subsystems only initialize when `world_mode === 'open_world'`.
- **Region Traversal:** `RegionManager` enforces bidirectional connection legality, traversal types (`on_foot`, `vehicle`), and inventory/quest prerequisites (`required_state_key`).
- **Targeted Activities:** `ActivityManager` tracks designated POI targets (`target_poi_id`), actors (`target_actor_id`), timers, and reward consequences.
- **UI Lifecycle Protection:** Dynamic world labels and floating HUD text are registered in `openWorldLabelsGroup` and cleanly disposed via `.clear(true, true)` upon region transitions.
- **Field Execution Fidelity:**
  - *Fully Executed:* `regions`, `connections`, `traversal_mode`, `required_state_key`, `pois`, `activities`, `activity_timer`, `prerequisites`, `consequences`, `rewards`, `vehicles`, `actors`, `threat_system`, `time_system`, `factions`.
  - *Partially Executed:* `events` (time-based triggering and HUD announcement banners execute; dynamic global `event_modifiers` altering player physics or enemy stats are not yet connected to arcade physics).
  - *Preserved in Schema:* `schedules` on `ActorDef` are parsed and retained in data models, but dynamic cross-region NPC relocation based on real-time clock is not simulated in the Phaser runtime.

### 7. Deterministic PRNG Seed Preservation

- Simulation randomness is strictly decoupled from visual effects and telemetry. Simulation uses seeded Mulberry32 (`prng.ts`).
- `PhaserCanvas.tsx` maintains the exact compiled seed across scene restarts (`'R'` key, restart button), removing unseeded `Math.random()` drift to guarantee reproducible replays and synchronized telemetry.

### 8. Backend Normalization Allowlist Sync

- `validator.py` preserves all canonical `OpenWorldDef` fields (`activity_ids`, `start_poi_id`, `target_count`, `time_limit_seconds`, `prerequisites`, `success_consequences`, `schedules`, `required_state_key`) during DSL ingestion and normalization.

### 9. Terminal State Gameplay Mutation Safety

Every gameplay mutation entry point is gated by `canMutateGameplay()`, which checks `RuntimeStateMachine.isTerminal()`:
- Score updates (`addScore`), player damage (`damagePlayer`), player healing (`healPlayer`), bonus spawns (`spawnBonusEntity`), wave spawns (`spawnWave`), speed boosts (`applySpeedBoost`), melee attacks, ranged attacks, collectible pickups, objective progression, and region transitions are strictly blocked in terminal states (`WON`, `LOST`, `DESTROYED`).
- Timer and tween callbacks verify scene and active status before updating HUD text or state.

### 10. 54-Cell Capability Matrix & Scale Tier Budgets

- **Matrix Scope:** 6 Archetypes × 3 World Modes × 3 Scale Tiers = 54 Cells.
- **Capability Verification:** `RuntimeConfigCompiler` evaluates all 54 cells. 48 supported cells compile into valid, typed `RuntimeGameConfig` structures. 6 unsupported cells (`platformer` and `runner` in `open_world` across 3 scale tiers) are strictly rejected before scene initialization.
- **Integration & Browser Scope:** Headless integration exercises 8 canonical archetype/world fixtures. Interactive browser gameplay execution verifies all 6 primary archetypes and supported open-world variants on the live Phaser canvas across 3 viewports. (The 54 cells represent capability and configuration coverage, not 54 full manual gameplay playthroughs).
- **Scale Budgets:** Canonical soft target ranges (`level_count`, `entities_per_level`, `rules_per_level`) are imported from `scale_tiers.py` as generation targets. At runtime, `maxLevels` and `maxWaves` are derived and enforced, while declared stage entities and rules are executed without artificial truncation.

## Consequences

- **Faithful DSL Execution:** All supported generated DSL structures compile and execute according to their declared archetypes, world modes, scale tiers, and objectives.
- **Zero Recursion Panics:** Cyclic rule configurations and wave triggers terminate safely without crashing the browser main thread.
- **Deterministic Playtests:** Replay analysis and telemetry synchronization operate on consistent procedural seeds.
- **Clean Architecture Boundaries:** Separation between DSL definitions, compilation models, policy resolution, and Phaser scene rendering.
