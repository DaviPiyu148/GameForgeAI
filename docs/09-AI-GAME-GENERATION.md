# 09 — AI Game Generation

## Game Generation Pipeline V2 (Quality, Depth & Capability Contract)
```text
USER BUILD REQUEST (Prompt + Engine + Scale + Modules)
      ↓
STAGE 1: [SYS] UNDERSTANDING GAME REQUEST (build_generation_contract, capability allowlist, reject unsupported)
      ↓
STAGE 2: [AI] BUILDING GAME DESIGN (Core loop & progression formulation)
      ↓
STAGE 3: [AI] MAPPING RUNTIME CAPABILITIES (Phaser Arcade 3.88.2 Capability Registry)
      ↓
STAGE 4: [AI] GENERATING GAMEDSL (Single structured Gemini generation call)
      ↓
STAGE 5: [VALIDATION] SCHEMA VALIDATION (Pydantic models with extra="forbid")
      ↓
STAGE 6: [VALIDATION] GAMEPLAY QUALITY (GameDepthEvaluator, RequirementCoverageMatrix, GameForge Quality Score)
      ↓
STAGE 7: [REPAIR] DETERMINISTIC NORMALIZATION/REPAIR (Safe auto-repair: implied finale, drift normalization)
      ↓
STAGE 8: [PHASER] RUNTIME COMPILATION (Phaser 3.88.2 Arcade Physics compilation)
      ↓
STAGE 9: [PHASER] RUNTIME VERIFICATION (Procedural seed & reachability guarantee)
      ↓
STAGE 10: [SYS] BUILD COMPLETE (Persistence & 0x00_SYS_READY)
```


## Provider Abstraction & Model Invariants (Architecture V2)
- **Active Provider**: Google Gemini (Gemini 3 Family: `gemini-3.7-flash`, `gemini-3.6-flash`, `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`).
- **Sequential Credential Failover**: Deterministic request-level failover across independently configured credentials (Key 1 primary; Key 2/3 tried only on eligible errors).
- **Task-Based Model Routing**: Canonical `TaskType` routing maps operations (`GAME_GENERATION`, `REMIX`, `DSL_PATCH`, `BLUEPRINT`, `PLAYTEST_ANALYSIS`, `DIRECTOR`) to tailored model fallback chains.
- **Safety Boundary**: The model outputs structured JSON only (`GameDesignSpec` + `GameDSL`) via `response_format={"type": "json_object"}`.
- **Zero Arbitrary Execution**: Never generate raw JavaScript, never use `eval()` or `new Function()`.
- **Compiler Logs**: Real structured build progress emitted via SSE.

## GameDesignSpec
Acts as an intermediate structured design layer between natural-language user concepts and executable Phaser Game DSL schemas:
- `title`, `elevator_pitch`, `genre`, `subgenre`, `theme`, `visual_style`, `camera`, `core_gameplay_loop`, `player_role`, `primary_objective`, `secondary_objectives`, `player_abilities`, `enemy_archetypes`, `hazards`, `collectibles`, `progression`, `difficulty_curve`, `win_conditions`, `loss_conditions`, `level_structure`, `estimated_session_length`, `selected_modules`, `rationale`.

## Game DSL Expansion (v2.0 Primitives)
- **PlayerDef**: `dash_speed`, `dash_cooldown`, `stamina`, `attack_type`, `attack_damage`, `attack_cooldown`, `weapon_color`.
- **EntityDef**: `damage`, `fire_rate`, `patrol_radius`, `detection_radius`, `loot_drop`, expanded behaviors (`patrol`, `chase`, `stationary`, `bounce`, `float`, `flee`, `guard`, `ranged_attack`).
- **RuleDef**: Expanded triggers (`on_wave_start`, `on_dash`, `on_hazard_touch`, `on_enemy_defeat`, `on_checkpoint`, `on_powerup_expire`) and actions (`trigger_screen_shake`, `spawn_wave`, `grant_powerup`, `activate_checkpoint`, `spawn_particles`, `knockback_target`).
- **WorldDef**: `difficulty_scaling`, `wave_count`, `procedural_seed`, `hazard_density`.
- **UIDef**: `show_health`, `show_score`, `show_stamina`, `show_wave`, `show_objectives`.

## Procedural Level Generation & Reachability
- Deterministic seed-based layout generation (`seed + GameDSL`).
- Player spawn clearance guaranteed (minimum 80px distance from initial hazards/enemies).
- Static reachability validation ensuring traversal to all objectives.

## Playtest Telemetry & AI Critique
- **Telemetry Recorder**: Tracks in-game events (`SESSION_START`, `DAMAGE_TAKEN`, `ENEMY_DEFEATED`, `ITEM_COLLECTED`, `OBJECTIVE_COMPLETED`, `CHECKPOINT_REACHED`, `GAME_WON`, `GAME_LOST`, `SCORE_CHANGED`).
- **AI Playtest Analysis**: Post-game critique returns structured ratings (`fun_rating`, `difficulty_rating`, `clarity_rating`), strengths, problems, and actionable recommendations.
- **Iterative Improvement**: User selects recommendations, Gemini patches existing DSL, project bumps version (`current_version = 2`), and prototype hot-reloads without full regeneration.

## Game Blueprint (Phase 4)
`GET /api/projects/{id}/blueprint` derives a nontechnical-friendly `GameBlueprint` purely
from the project's already-validated `GameDesignSpec` + `GameDSL` — a computed
projection, never a second source of truth. `supported_mechanics` is allowlist-derived
(`backend/app/generation/blueprint.py`): a mechanic name only appears when its predicate
against the real DSL is true (e.g. `"Dash Mobility"` iff `player.dash_speed > 0`). This
is the enforcement mechanism preventing the blueprint from ever claiming a capability the
runtime can't back — `"Vehicles"`, `"Boss Fights"`, and `"Wanted System"` never appear;
those belong to later roadmap phases (5/6).

## Remix (Phase 4)
`POST /api/projects/{id}/remix` accepts 1-3 structured `RemixIntent` objects from a closed
catalog (`app/schemas/remix.py`): `increase_combat, increase_exploration,
increase_difficulty, decrease_difficulty, add_levels, more_story, faster_pace,
more_enemies, change_theme`. Duplicate or mutually-exclusive intents (e.g.
`increase_difficulty` + `decrease_difficulty`) are rejected with HTTP 422 before any AI
call. `GameGenerationService.apply_remix()` reuses the exact same schema validation,
`GameplayQualityValidator`, `ReachabilityValidator` repair pass, and bounded AI repair
loop as fresh generation — a remix is held to the identical safety bar. `add_levels` is
clamped server-side to the existing 5-level schema cap rather than silently dropped.
Game DNA personalization is passed into the remix prompt strictly as secondary flavor;
the explicit remix request always takes precedence. Every successful remix creates a new
immutable `ProjectVersion` (never mutates prior versions), recording the structured
intent(s) that produced it in the new `remix_intent` column.

## Scale Tiers & Budget Validation (Phase 5)
A build's `BuildParams.scale` (`prototype`/`standard`/`campaign`, default `standard`)
flows through to `generate_game_dsl(..., scale=...)` and `build_generation_prompt(...,
scale=...)`, mirroring how `engine`/`art_density`/`physics` already propagate.
`app/generation/scale_tiers.py` defines each tier's level/entity/rule count budget,
strictly inside the DSL's existing hard caps (levels<=5, entities<=30/level,
rules<=15/level). `GameplayQualityValidator.validate_scale_budget()` is a **floor-only**
check: a DSL below its tier's minimum gets exactly one bounded-repair nudge (folded into
the existing repair loop as a soft, first-attempt-only error); if still under target
after that, the build succeeds anyway with a `WARNING` log rather than a hard failure.

## Bounded Boss / Finale (Phase 5)
`EntityDef` gains optional `is_boss`, `boss_phases` (1-2), and `telegraph_ms` (0-2000ms)
fields (all default to values that make every pre-Phase-5 DSL validate unchanged); a boss
must have `health >= 150` and, per-level, must meaningfully outclass ordinary enemies
in health. Boss fights get a 1.5s intro banner with full-width screen health bar, a
deterministic Phase 2 at <=50% health (+25% speed, +20% damage, distinct color), and a
fixed-duration circular attack telegraph with color shift before firing.

## Generalized Open World System (Phase 6)
Phase 6 introduces a general-purpose, reusable open-world capability supporting crime
sandboxes, cyberpunk courier cities, zombie survival hubs, fantasy realms, and sci-fi colonies
without hardcoding genre-specific mechanics.
- **Architectural Mode Separation**: `world_mode` (`"linear"`, `"campaign"`, `"open_world"`)
  and `scale` (`"prototype"`, `"standard"`, `"campaign"`) operate as independent orthogonal
  dimensions.
- **OpenWorldDef Subsystem Schemas**:
  - `RegionDef`: Multi-district world map with danger levels, themes, and dimensions.
  - `WorldConnectionDef`: Bidirectional/unidirectional links between regions with traversal constraints.
  - `POIDef`: Interactive points of interest (garages, terminals, safehouses, quest givers, shops).
  - `VehicleDef`: Driveable vehicles (cars, hovercrafts, bikes, mechs) with speed, acceleration, and handling physics.
  - `FactionDef`: Faction reputations (-100 to 100) with dynamic hostility thresholds.
  - `ActivityDef`: Dynamic missions, deliveries, investigations, combat tasks, and rewards.
  - `ActorDef`: Living NPCs with capability-verified behaviors (`patrol`, `chase`, `stationary`, `guard`, `flee`, `ranged_attack`).
  - `ThreatSystemDef`: Alert meter (0-5) with decay and response unit reinforcements.
  - `WorldTimeDef`: Game time clock and day/night cycle.
- **Validation & Repair**: BFS reachability graph traversal ensures all regions are connected;
  isolated regions receive automatic bridging. Open-world budgets (regions <= 6, POIs <= 25,
  actors <= 50, vehicles <= 10, factions <= 5, activities <= 15) and runtime compatibility
  are strictly enforced.
- **Modular Phaser Runtime**: 7 standalone managers (`WorldManager`, `RegionManager`,
  `VehicleManager`, `ActivityManager`, `FactionManager`, `ThreatManager`, `WorldEventManager`)
  handle vehicle entry/exit (`E`), driving mechanics, seamless district boundary traversal,
  and open-world HUD status displays.

## Multi-Level Runtime Rendering (Phase 5)
The Phaser runtime (`GameScene.ts`) previously only ever rendered level 0's visuals even
though the DSL schema supported up to 5 levels — level transitions repositioned entities
but never reapplied a level's `world`/`theme` overrides. `applyLevelConfig()` is now the
single source of truth for "apply a level" (background color, spawn, entities, HUD text),
used identically on initial load and every transition. Entity/player `color` fields are
now rendered via texture tinting (previously generated but ignored). Level transitions
use a deterministic 200ms fade instead of an instant teleport.
