# Runtime & Gameplay Architecture

## 1. Overview

The Runtime and Gameplay subsystem bridges validated `GameDSL` schemas into a deterministic, performant, and kinetic 2D browser gaming experience powered by **Phaser 3.88.2 Arcade Physics**.

Rather than treating runtime graphics as generic monochromatic wireframes, GameForge AI implements:
- **A Centralized Visual Profile System**: Synthesizes thematic color palettes, silhouette languages, and environmental motifs deterministically from DSL metadata.
- **Procedural Texture Generation**: Generates vector-style entity silhouettes directly into Phaser's `TextureManager` at runtime with zero external asset downloads.
- **Dynamic Environmental Composition**: Renders layered procedural backgrounds, ambient props, landmark structures, and 2-layer parallax.
- **Procedural VFX & Kinetic Feedback**: Enriches combat with hit flashes, directional muzzle flares, tiered screen rumbles, dash ghosting, and collectible halos.
- **The Canonical Gameplay Beat Model**: Structures game pacing across 5 formal flow phases (`INTRO` $\rightarrow$ `ACTION` $\rightarrow$ `VARIATION` $\rightarrow$ `ESCALATION` $\rightarrow$ `FINALE`).
- **Deterministic Deadlock Detection**: Analyzes spatial layout and rule graphs to eliminate unwinnable progression states.
- **System Usage Tiers & Dead-Rule Validation**: Verifies that generated systems (vehicles, factions, threat, POIs) and event rules actively participate in gameplay rather than existing passively in metadata.

---

## 2. Phaser Runtime Architecture & Lifecycle

```text
                                GameDSL Artifact
                                       │
                                       ▼
                       Runtime Visual Profile Derivation
                             (deriveVisualProfile)
                                       │
                                       ▼
                         Phaser Game Initialization
                           (Phaser.Game / Canvas)
                                       │
                                       ▼
                     GameScene Lifecycle (GameScene.ts)
   ┌───────────────────────────────────┼───────────────────────────────────┐
   ↓                                   ↓                                   ↓
Preload / Texture Gen           Create Subsystems                    Update Loop
- generateProceduralTextures()   - Player & Weaponry                - Physics step (60 Hz)
- Cache in TextureManager        - Enemy Pools & Boss Hierarchy     - Entity behaviors
- Setup keyboard/touch bindings  - Environment & Landmark Props     - Combat collisions
                                 - VFX Emitter Lifecycle           - Rule trigger evaluation
                                 - Thematic HUD Overlay             - Telemetry logging
```

### 2.1 Scene Lifecycle Management
- **Preload Stage**: Checks `TextureManager` for cached silhouettes matching `profile + role + variant + theme`. Missing textures are generated procedurally on-the-fly.
- **Create Stage**: Constructs physics groups, registers collision and overlap pairs, spawns entities, builds environmental landmarks, and initializes HUD layers.
- **Update Stage**: Ticks entity AI routines (patrol, chase, ranged artillery, guard), updates active VFX tweens, records telemetry metrics, and checks win/loss conditions.
- **Shutdown Stage**: Destroys all active particle emitters, cancels pending timer events, clears tween pools, and detaches DOM listeners to prevent memory leaks.

---

## 3. Visual Profile System (`visualProfile.ts`)

The `RuntimeVisualProfile` acts as the single source of visual authority for the active session, derived deterministically from the game's theme, genre, and level structure:

```typescript
export interface RuntimeVisualProfile {
  themeKey: 'cyberpunk' | 'dungeon' | 'space' | 'wasteland' | 'arcade' | 'neutral';
  palette: {
    primary: number;       // Main player/accent color
    secondary: number;     // Secondary entity color
    accent: number;        // Interactive element highlight
    surface: number;       // Primary background tint
    surfaceSecondary: number;
    text: number;          // In-game typography color
    hazard: number;        // Hazard & trap indicators
    collectible: number;   // Relic & pickup glows
    boss: number;          // Boss entity highlight
  };
  player: {
    silhouetteRole: 'operative' | 'knight' | 'crawler' | 'runner' | 'starship';
    fillColor: number;
    accentColor: number;
    hasTrail: boolean;
  };
  enemy: {
    shapeLanguage: 'angular' | 'crested' | 'faceted' | 'spiked' | 'robotic';
    tierColors: Record<'basic' | 'fast' | 'ranged' | 'heavy' | 'elite' | 'boss', number>;
  };
  environment: {
    backgroundMode: 'CITY' | 'RUINS' | 'SPACE' | 'DESERT' | 'ARENA' | 'GRID';
    propDensity: 'low' | 'medium' | 'high';
    ambientTint: number;
  };
  hud: {
    borderColor: string;
    fontFamily: string;
    accentColor: string;
  };
  reducedMotion: boolean;
}
```

---

## 4. Procedural Texture Generator (`proceduralTextures.ts`)

To eliminate reliance on external asset servers, entity textures are drawn directly to Phaser canvas textures using procedural vector drawing commands:

### 4.1 Player Archetypes
- **`operative`**: Sleek angular cyber-scout with shoulder pauldrons, visor slit, and central energy node.
- **`knight`**: Heavy armored warrior with crested helm, gleaming eye slit, and flank shields.
- **`crawler`**: Low-slung armored treaded rover with a rotatable top turret hatch.
- **`runner`**: Ultra-sharp forward-swept racing wedge with dual rear exhaust nozzles.
- **`starship`**: Faceted space interceptor with cockpit canopy and swept wings.

### 4.2 Enemy Archetypes
- **`basic`**: Faceted diamond patrol drone.
- **`fast`**: Chevron-shaped forward dagger interceptor.
- **`ranged`**: Concentric artillery orb with a rotating targeting pupil.
- **`heavy`**: Reinforced faceted hexagonal brute.
- **`elite`**: Multi-pointed radiant spiked star.
- **`boss`**: Imposing crowned fortress crest with a central core eye and multi-segmented armor plates.

### 4.3 Collectibles & Weapon Projectiles
- **Cyberpunk / Space**: Luminous data cubes, octagonal energy shards, and laser beam pulses.
- **Dungeon / Fantasy**: Ancient gold talisman seals, mana crystals, and incandescent fireballs.

---

## 5. Procedural Environments & Landmark Composition (`environmentSystem.ts`)

Instead of a plain grid, levels feature thematic environmental dressing scaled by `artDensity`:

| Environment Mode | Thematic Decor Props | Landmark Structures | Ambient Backdrop |
| :--- | :--- | :--- | :--- |
| **`CITY`** | Terminal nodes, holographic signs, ventilation fans, cables | Cyberpunk relay tower / power generator | Deep midnight blue with moving light streaks |
| **`RUINS`** | Stone pillars, wall torches with flame flickers, rubble piles | Ancient runic monolith / broken altar | Dark charcoal with ember particle drift |
| **`SPACE`** | Solar arrays, satellite dishes, communication pylons | Deep-space docking hub / asteroid beacon | Starfield with 2-layer parallax stars |
| **`DESERT`** | Fortified barricades, scrap heaps, fuel canisters | Salvage crane / outpost bunker | Warm umber void with dust drift |
| **`ARENA`** | Combat floodlights, boundary barriers, energy pylons | Central arena crown podium | High-contrast neon perimeter rings |

**Parallax**: Midground props and background starfields shift at 20% and 50% of camera speed respectively, creating spatial depth without performance overhead.

---

## 6. Procedural VFX & Game Feel (`vfxSystem.ts`)

1. **Entity Animation**: Organic idle breathing (sinusoidal scale modulation) on players, enemies, and bosses.
2. **Combat Feedback**:
   - Directional muzzle flare sparks on weapon discharge.
   - 60ms white flash shader on damaged entities (`hit_flash`).
   - Radial spark bursts on projectile collision (6–8 micro-particles).
   - Tiered camera shake: subtle micro-rumble (intensity: `0.003`, duration: `60ms`) for normal impacts; heavy screen shake (intensity: `0.015`, duration: `250ms`) for boss attacks and phase changes.
3. **Locomotion**: Semi-transparent ghost afterimages rendered during dash execution.
4. **Item Acquisition**: Expanding luminous ring halo on collectible pickup with score popups.
5. **Memory Safety**: Every transient particle, tween, and emitter is registered in a tracker and destroyed upon level completion or restart.

---

## 7. The Canonical Gameplay Beat Model (`gameplay_rhythm.py`)

A compelling game loop requires structured pacing. GameForge AI formalizes every encounter into a 4-element beat:
$$\text{Action} \longrightarrow \text{Challenge} \longrightarrow \text{Feedback} \longrightarrow \text{Reward / Progress}$$

### The 5 Flow Phases:
1. **`INTRO` (0–15s)**: Safe spatial orientation, movement controls discovery, clear objective prompt.
2. **`ACTION` (15–45s)**: First active kinetic encounter (engaging basic patrols, collecting initial tokens).
3. **`VARIATION` (45–90s)**: Introduction of secondary enemy archetypes (ranged artillery, fast chasers, or environmental hazards).
4. **`ESCALATION` (90–150s)**: Multi-threat combinations, wave pressure, or expanding alert zones.
5. **`FINALE` (Climax)**: Boss phase transitions, health pool $\ge 150$, rage thresholds, or high-intensity extraction.

---

## 8. Deterministic Deadlock Detection (`GameplayRhythmManager`)

Before compilation, the deadlock validator analyzes the DSL to guarantee progression viability:
- **Zero-Target Elimination**: Flags objectives requiring `defeat_all` when 0 enemies are placed in the level.
- **Unreachable Exits**: Asserts that `reach_exit` coordinates (`exit_x`, `exit_y`) lie strictly within level boundaries and outside static solid walls.
- **Scoring Circularity**: Ensures that score-based win targets can be achieved through placed collectibles or enemy defeat rewards.
- **Wave Trigger Viability**: Warns if world `wave_count > 1` lacks event handlers for `on_wave_start`.

---

## 9. System Usage Tiers & Composition Matrix

To prevent subsystems from existing purely as passive metadata, GameForge AI defines strict **System Usage Tiers**:

| Tier | Definition | Requirement |
| :--- | :--- | :--- |
| **`FULL`** | Directly causes an observable, active gameplay consequence | e.g. Vehicles provide speed advantage across regions $\ge 1000\text{px}$; Factions are explicitly targeted in mission objectives. |
| **`PARTIAL`** | Contextual telemetry or UI presence without direct mechanical challenge | e.g. Threat meter displays alert level without spawning reinforcements. |
| **`PASSIVE`** | Rendered visually or stored in metadata, but never interacted with | Triggers `QualityFailureCode.PASSIVE_SYSTEM_DETECTED` penalty. |
| **`DEAD`** | References triggers or actions unsupported by the Phaser engine | Triggers `QualityFailureCode.DEAD_RULE_DETECTED` penalty. |
| **`UNSUPPORTED`**| Requests concepts outside the 2D Arcade runtime allowlist | Rejected upfront during request parsing. |

### Rule Liveness Validator (`validate_rule_liveness`)
Validates that every rule in `GameDSL.rules` uses allowlisted triggers and executable actions:
- **Supported Triggers**: `on_collect`, `on_collide_enemy`, `on_reach_goal`, `on_score_target`, `on_time_limit`, `on_player_death`, `on_wave_start`, `on_dash`, `on_hazard_touch`, `on_enemy_defeat`, `on_checkpoint`, `on_powerup_expire`.
- **Supported Actions**: `add_score`, `damage_player`, `heal_player`, `win_game`, `lose_game`, `spawn_entity`, `speed_boost`, `trigger_screen_shake`, `spawn_wave`, `grant_powerup`, `activate_checkpoint`, `spawn_particles`, `knockback_target`.

---

## 10. Telemetry & Failure Clarity

- **In-Game Telemetry Capture**: Records player deaths, accuracy, time-to-objective, and collectible rates to pass structured context to the post-game AI critique engine.
- **Descriptive Failure Messaging**: Displays exact defeat causes on the game-over screen (e.g. `✖ HEALTH DEPLETED — OVERWHELMED BY ENEMY FIRE ✖` or `✖ TIME EXPIRED — SECTOR CONTAINMENT FAILED ✖`) instead of generic placeholder text.

---

## 11. Authoritative Runtime Architecture & Preset Execution (ADR-009)

The GameForge AI Phaser runtime executes validated `GameDSL` configurations through a contract-driven multi-stage engine:

### 11.1 Runtime Configuration Compiler (`RuntimeConfigCompiler.ts`)
- **Stage Compilation**: Compiles global DSL and level-specific definitions into isolated `RuntimeStageConfig` stages.
- **Hierarchical Fallback**: Level-local parameters (`world`, `spawn_x`, `spawn_y`, `rules`, `objective`) override global defaults with stage isolation.
- **Atomic Multi-Level Progression**: Level transitions atomically reconfigure world bounds, camera bounds, physics gravity, stage rules, and objective evaluators.
- **Scale Profiles**: Maps scale tiers (`prototype`, `standard`, `campaign`) to stage budgets and maximum wave caps.

### 11.2 Objective Evaluation Engine (`ObjectiveEvaluator.ts`)
- **Canonical Objective Types**: Evaluates `collect_all`, `defeat_all`, `reach_exit`, `survive_time`, and `score_target`.
- **Terminal State Latch**: Once a terminal outcome (`WON` or `LOST`) is reached, state is locked, preventing spurious flips.

### 11.3 Synchronous Execution-Path Rule Engine (`rules.ts`)
- **Active Call-Path Cycle Detection**: Tracks the synchronous execution stack (`activeRuleIds`, `activeExecutionStack`) across the causality chain `Rule -> Action -> Emitted Trigger -> Rule`.
- **Selective Termination**: Detects and terminates cyclic re-entry immediately while allowing multiple independent rules subscribed to the same trigger to execute cleanly.
- **Causal Chains & Re-arming**: Supports valid linear chains (`A -> B -> C -> D`). Threshold crossings re-arm if score drops below and re-crosses threshold. Static rule graphs are validated via `RuleEngine.validateRuleGraph`.
- **Defensive Ceiling**: Enforces `MAX_EXECUTION_DEPTH = 6` as an auxiliary ceiling.

### 11.4 Wave Controller State Machine (`WaveController.ts`)
- **FSM Transitions**: `IDLE` $\rightarrow$ `SPAWNING` $\rightarrow$ `ACTIVE` $\rightarrow$ `COMPLETED`.
- **Separation of Request and Notification**: `requestNextWave()` is decoupled from `on_wave_start` notifications.
- **Notification Re-entrancy Lock**: `isNotifying` lock prevents synchronous rule actions from triggering secondary wave spawns during startup.
- **Terminal Progression Lock**: Irrevocably halts wave progression in terminal states (`WON`, `LOST`, `DESTROYED`).

### 11.5 Terminal State Gameplay Mutation Safety (`GameScene.ts`)
- Every gameplay mutation (`addScore`, `damagePlayer`, `healPlayer`, `spawnBonusEntity`, `spawnWave`, `applySpeedBoost`, attacks, pickups, objective progressions, and region transitions) is guarded by `canMutateGameplay()`, which checks `RuntimeStateMachine.isTerminal()`.
- Scene restarts properly reset all GameObject references and verify `active && scene` before calling methods on Phaser text/HUD components.

### 11.6 Archetype Policy Matrix (`ArchetypePolicy.ts`)
- Maps 6 archetypes (`platformer`, `arena`, `shooter`, `collector`, `survival`, `runner`) to physics movement models, attack modes (`melee`, `ranged`, `none`), dash mechanics, and wave legality. Prohibits open world for `platformer` and `runner`.

### 11.7 Open-World Subsystems & Memory Isolation (`RegionManager.ts`, `ActivityManager.ts`)
- **Authoritative World Mode**: Mode resolution strictly uses `world.world_mode`.
- **Region State Locks**: Validates `required_state_key` and traversal modes (`on_foot`, `vehicle`) on region transitions.
- **Targeted Progression**: Tracks designated POI targets (`target_poi_id`), actors (`target_actor_id`), timers, and rewards.
- **UI Memory Hygiene**: Dynamically generated floating labels and text objects are tracked in `openWorldLabelsGroup` and cleanly cleared on region changes.

### 11.8 Seeded Determinism (`PhaserCanvas.tsx`, `prng.ts`)
- Preserves the exact compiled procedural seed across scene restarts (`'R'` key and header restart), eliminating drift and guaranteeing bit-exact telemetry and replay reproducibility. Visual randomness (particle flares) is strictly separated from simulation PRNG.

### 11.9 54-Cell Capability Matrix & Scale Tier Budgets
- Evaluates 6 Archetypes × 3 World Modes × 3 Scale Tiers = 54 Cells.
- **Capability Coverage:** 48 supported cells compile into valid `RuntimeGameConfig` instances; 6 canonically incompatible cells (`platformer` and `runner` in `open_world` across 3 scale tiers) are strictly rejected with compile errors before scene instantiation.
- **Verification Levels:** The 54 cells evaluate compiler configuration and capability mapping. End-to-end integration verifies 8 canonical/synthetic fixture suites, and live browser gameplay verification exercises all 6 primary archetypes and supported open-world variants on the canvas.
- **Open-World Field Status:** Core mechanics (regions, connections, traversal gating, POIs, activities, timers, prerequisites, consequences, rewards, vehicles, actors, threat, time of day, factions) are executed. However, not all canonical Open World semantics are fully implemented: actor schedules (`schedules`) are unsupported/rejected with controlled validation errors, and dynamic global event modifiers (`event_modifiers` affecting player physics or enemy base stats) are partial/unsupported as currently implemented (threat/danger modifiers execute via `ThreatManager`, while dynamic stat/physics modifiers are rejected before runtime execution).
- Scale profiles mirror `scale_tiers.py` generation target budgets (`prototype`, `standard`, `campaign`), deriving runtime `maxLevels` and `maxWaves`.
