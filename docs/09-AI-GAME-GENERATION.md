# 09 — AI Game Generation

## Game Generation V2 Pipeline
```text
USER IDEA
    ↓
AI GAME DESIGN
    ↓
STRUCTURED GAME DESIGN SPECIFICATION (GameDesignSpec)
    ↓
GAME DSL (Expanded Primitives v2.0)
    ↓
DSL SCHEMA VALIDATION (Pydantic v2)
    ↓
GAMEPLAY QUALITY VALIDATION (Deterministic Quality & Clearance Checks)
    ↓
BOUNDED AI REPAIR (Max 2 Retries with Structured Feedback)
    ↓
DETERMINISTIC PHASER PROTOTYPE (Procedural Generation & Game Feel)
    ↓
PLAYTEST TELEMETRY (Non-Intrusive In-Game Event Tracker)
    ↓
AI PLAYTEST ANALYSIS (Post-Game Critique & Ratings)
    ↓
IMPROVEMENT PLAN (Selectable Actionable Recommendations)
    ↓
USER APPROVES CHANGES
    ↓
DSL PATCH / REVISION
    ↓
REBUILD / VERSION PROTOTYPE (v1 → v2 → v3)
```

## Provider Abstraction & Model Invariants
- **Active Provider**: Google Gemini (Gemini 3 Flash Preview, identifier: `gemini-3-flash-preview`).
- **Safety Boundary**: The model outputs structured JSON only (`GameDesignSpec` + `GameDSL`).
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
(`>= 2x` the strongest non-boss enemy in the same scope) or generation fails validation.
`telegraph_ms` is only valid on `ranged_attack` behavior. `LevelDef.is_finale` is an
explicit marker (rather than inferring "last level") that `build_game_blueprint()`'s
finale derivation now prefers when present. Runtime boss behavior is a single
deterministic threshold-based bump (speed/fire-rate x1.3 at <=50% health) plus a fixed
visual telegraph before a ranged attack fires — not a state-machine framework.

## Multi-Level Runtime Rendering (Phase 5)
The Phaser runtime (`GameScene.ts`) previously only ever rendered level 0's visuals even
though the DSL schema supported up to 5 levels — level transitions repositioned entities
but never reapplied a level's `world`/`theme` overrides. `applyLevelConfig()` is now the
single source of truth for "apply a level" (background color, spawn, entities, HUD text),
used identically on initial load and every transition. Entity/player `color` fields are
now rendered via texture tinting (previously generated but ignored). Level transitions
use a deterministic 200ms fade instead of an instant teleport.
