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
- **Active Provider**: Google Gemini (Gemma 4 31B, identifier: `gemma-4-31b-it`).
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
