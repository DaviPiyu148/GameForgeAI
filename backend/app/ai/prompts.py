import json
from typing import Any, Dict, List, Optional


SYSTEM_PROMPT = """You are GameForge AI's Principal Game Designer & DSL Architect.
Your task is to transform natural language game concepts into a cohesive, playable 2D game prototype.

You must generate:
1. "design_spec": A structured game design specification detailing theme, camera, core loop (action -> feedback -> pressure -> progression -> resolution), primary/supporting objectives, progression phases (EARLY/MID/FINALE), abilities, and design rationale.
2. "dsl": A valid Game DSL object conforming strictly to Game DSL Schema v2.0 for Phaser 3.88.2 Arcade Physics.

RULES & BOUNDS:
1. OUTPUT FORMAT: Output ONLY a single valid JSON object containing {"design_spec": {...}, "dsl": {...}}. Do NOT wrap output in markdown codeblocks. Do NOT include conversational preamble.
2. SCOPE & BOUNDS:
   - Entities: 4 to 20 entities maximum.
   - Rules: 2 to 10 rules maximum.
   - World width: 400 to 1920 (default 800)
   - World height: 300 to 1080 (default 600)
   - Player spawn clearance: Player spawn (spawn_x, spawn_y) must be at least 80px away from any hazard or enemy spawn.
3. ARCHETYPES & GAMEPLAY LOOPS:
   - "survival": Wave/swarm pressure, tactical evasion, dash mobility, clear all waves or reach target score to win.
   - "shooter": Projectile combat, enemy target prioritization, kiting, eliminate enemy forces to win.
   - "platformer": Traversal over platforms, jump power + gravity, hazard avoidance, reach goal beacon to win.
   - "collector": Sweeping arena for resource nodes, evading patrolling/bouncing guardians, collect all nodes to win.
   - "arena": Closed combat arena, escalating pressure, survival stamina management.
4. THEMES: One of ["cyberpunk", "retro_arcade", "dungeon", "space", "neon", "minimal"].
5. ENTITY BEHAVIORS: One of ["patrol", "chase", "stationary", "bounce", "float", "flee", "guard", "ranged_attack"].
6. RULE TRIGGERS: One of ["on_collect", "on_collide_enemy", "on_reach_goal", "on_score_target", "on_time_limit", "on_player_death", "on_wave_start", "on_dash", "on_hazard_touch", "on_enemy_defeat", "on_checkpoint", "on_powerup_expire"].
7. RULE ACTIONS: One of ["add_score", "damage_player", "heal_player", "win_game", "lose_game", "spawn_entity", "speed_boost", "trigger_screen_shake", "spawn_wave", "grant_powerup", "activate_checkpoint", "spawn_particles", "knockback_target"].
8. SAFETY: NEVER include JavaScript, code, script tags, eval, or HTML in any field.
9. DESIGN RATIONALE: Provide 2-4 concise, evidence-based bullet points explaining design choices.
"""


def build_generation_prompt(
    prompt: str,
    engine: str = "Top-Down Action",
    art_density: int = 50,
    physics: int = 80,
    modules: List[str] = None,
    inspiration: Optional[Dict[str, Any]] = None,
) -> str:
    """Build user prompt instructing generation of structured GameDesignSpec and GameDSL."""
    mods = modules or []
    mods_str = ", ".join(mods) if mods else "standard mechanics"

    # Physics complexity guidance
    if physics <= 35:
        physics_guide = "Low/Arcade (gravity: 0-100, player speed: 180-220, linear locomotion, gentle collisions)"
    elif physics <= 70:
        physics_guide = "Balanced (gravity: 200-450, player speed: 220-280, jump_power: 320-450, knockback)"
    else:
        physics_guide = "High/Dynamic (gravity: 500-800, player speed: 280-350, dash speed: 600, acceleration, knockback, screen shake)"

    # Visual density guidance
    if art_density <= 35:
        density_guide = "Minimalist Vector (4-6 key entities, clean high-contrast colors, hazard density ~15)"
    elif art_density <= 70:
        density_guide = "Balanced Procedural (7-12 entities, distinct theme accents, collectibles, and hazards ~30)"
    else:
        density_guide = "Rich Procedural Details (12-18 entities, particle feedback, varied hazards ~60, patrol routes)"

    inspiration_text = ""
    if inspiration:
        inspiration_text = f"""
GAME INSPIRATION (Extract abstract design motifs ONLY; create an original game):
- Inferred Archetype: {inspiration.get('inferred_archetype')}
- Inferred Theme: {inspiration.get('inferred_theme')}
- Suggested Mechanics: {', '.join(inspiration.get('suggested_modules', []))}
"""

    return f"""Create a cohesive, playable 2D game prototype for:

CONCEPT PROMPT:
{prompt.strip()}
{inspiration_text}
TARGET CONFIGURATION:
- Prototype Profile: {engine}
- Physics Complexity ({physics}/100): {physics_guide}
- Visual Density ({art_density}/100): {density_guide}
- Active Logic Modules: {mods_str}

SCHEMA REQUIREMENT:
Output a single JSON object with exact structure:
{{
  "design_spec": {{
    "title": "Game Title",
    "elevator_pitch": "Short elevator pitch",
    "genre": "Action",
    "subgenre": "Cyberpunk Courier",
    "theme": "neon",
    "camera": "top_down",
    "core_gameplay_loop": "evade -> collect -> survive",
    "player_role": "Data Courier",
    "primary_objective": "Collect all data chips while evading hunter drones",
    "secondary_objectives": ["Conserve dash stamina", "Lure drones into traps"],
    "player_abilities": ["move", "dash", "shoot"],
    "enemy_archetypes": [
      {{"name": "Patrol Drone", "behavior": "patrol", "speed": 120}},
      {{"name": "Hunter Drone", "behavior": "chase", "speed": 140}}
    ],
    "win_conditions": ["Collect all data chips"],
    "loss_conditions": ["Player health depleted"],
    "loop_details": {{
      "player_action": "Navigate arena and collect power nodes",
      "immediate_feedback": "Floating score banners and visual dash particles",
      "increasing_pressure": "Enemy pursuit speed increases each wave",
      "progression": "Clear waves to reach final extraction point",
      "resolution": "Escape with all nodes to win"
    }},
    "objective_details": {{
      "primary": "Collect all data chips while evading hunter drones",
      "supporting": ["Evade enemy fire", "Conserve dash stamina"],
      "completion_criteria": "all_collectibles_gathered",
      "failure_condition": "player_health_depleted"
    }},
    "progression_phases": [
      {{"phase": "EARLY", "trigger": "Wave 1 start", "description": "Navigate and collect starter nodes", "runtime_effect": "Patrol drones active"}},
      {{"phase": "MID", "trigger": "Wave 2 start", "description": "Hunter drones engage", "runtime_effect": "Chase enemies spawn"}},
      {{"phase": "FINALE", "trigger": "Final wave", "description": "High threat extraction", "runtime_effect": "Ranged attack enemies spawn"}}
    ],
    "rationale": ["Top-down view enables tactical evasion", "Dash provides responsive mobility"]
  }},
  "dsl": {{
    "schema_version": "2.0",
    "metadata": {{"title": "Game Title", "genre": "Action", "description": "Game summary", "archetype": "survival"}},
    "world": {{"width": 800, "height": 600, "theme": "neon", "background_color": "#0a0a1a", "gravity": 0, "wave_count": 3, "hazard_density": 30}},
    "player": {{"spawn_x": 400, "spawn_y": 300, "max_health": 100, "speed": 250, "dash_speed": 600, "color": "#00f0ff", "attack_type": "ranged", "attack_damage": 25}},
    "entities": [
      {{"id": "chip_1", "type": "collectible", "x": 200, "y": 200, "width": 20, "height": 20, "color": "#00ff66", "behavior": "stationary", "points": 100}},
      {{"id": "drone_1", "type": "enemy", "x": 650, "y": 150, "width": 28, "height": 28, "color": "#ff0055", "behavior": "patrol", "speed": 120, "patrol_radius": 150, "damage": 15}}
    ],
    "rules": [
      {{"id": "r_col", "trigger": "on_collect", "action": "add_score", "params": {{"amount": 100}}}},
      {{"id": "r_dmg", "trigger": "on_collide_enemy", "action": "damage_player", "params": {{"amount": 25}}}},
      {{"id": "r_win", "trigger": "on_score_target", "action": "win_game", "params": {{"target_score": 100}}}},
      {{"id": "r_lose", "trigger": "on_player_death", "action": "lose_game"}}
    ],
    "ui": {{"show_health": true, "show_score": true, "show_stamina": true, "show_wave": true, "status_text": "SURVIVE AND COLLECT"}}
  }}
}}"""


def build_repair_prompt(
    invalid_candidate: Dict[str, Any],
    validation_errors: List[str],
) -> str:
    """Build repair prompt feeding validation errors back to the model."""
    error_list_str = "\n".join(f"- {err}" for err in validation_errors)
    invalid_json_str = json.dumps(invalid_candidate, indent=2)
    return f"""The previous Game Design & DSL generation contained validation errors:

VALIDATION ERRORS:
{error_list_str}

PREVIOUS CANDIDATE:
{invalid_json_str}

Repair the issues while strictly respecting the capability matrix, bounds, and rules:
- Ensure primary objective is clear and achievable.
- Ensure win conditions map to existing rules/entities.
- Ensure player spawn is at least 80px away from enemies/hazards.
- Ensure all entity behaviors are from ["patrol", "chase", "stationary", "bounce", "float", "flee", "guard", "ranged_attack"].
- Output ONLY the repaired JSON object with "design_spec" and "dsl"."""


def build_playtest_analysis_prompt(
    design_spec: Dict[str, Any],
    dsl: Dict[str, Any],
    telemetry: Dict[str, Any],
) -> str:
    """Build prompt for AI playtest analysis and actionable critique."""
    spec_summary = f"Title: {design_spec.get('title')}, Genre: {design_spec.get('genre')}, Archetype: {dsl.get('metadata', {}).get('archetype', 'survival')}"
    metrics = (
        f"Duration: {telemetry.get('duration_seconds', 0)}s, Outcome: {telemetry.get('outcome', 'PLAYED')}, "
        f"Score: {telemetry.get('score', 0)}, Damage Taken: {telemetry.get('damage_taken', 0)}, "
        f"Damage Dealt: {telemetry.get('damage_dealt', 0)}, Enemies Defeated: {telemetry.get('enemies_defeated', 0)}, "
        f"Collectibles Gathered: {telemetry.get('collectibles_gathered', 0)}, Objectives Completed: {telemetry.get('objectives_completed', 0)}, "
        f"Waves Reached: {telemetry.get('waves_reached', 1)}, Phase Reached: {telemetry.get('phase_reached', 'EARLY')}"
    )

    return f"""You are an expert Game Design Analyst reviewing a completed gameplay session.

GAME CONCEPT:
{spec_summary}

PLAYTEST TELEMETRY & DETERMINISTIC METRICS:
{metrics}

DSL SUMMARY:
Player Speed: {dsl.get('player', {}).get('speed')}, Max HP: {dsl.get('player', {}).get('max_health')}, Dash Speed: {dsl.get('player', {}).get('dash_speed', 0)}
Entities: {len(dsl.get('entities', []))} entities spawned, Waves: {dsl.get('world', {}).get('wave_count', 3)}

INSTRUCTIONS:
1. EVIDENCE GROUNDING: Base every problem and recommendation STRICTLY on the observed telemetry above. Do NOT invent player actions, deaths, or events that did not occur.
2. CITATION: Every problem must cite specific metrics (e.g. "Player took 45 damage in 30s before dying on wave 1").
3. ACTIONABLE PATCHES: Every recommendation must specify a valid 'suggested_patch' modifying DSL properties (such as player.speed, world.wave_count, entity damage, or collectibles).
4. READ-ONLY ANALYSIS: Provide recommendations for user review; do not assume automatic application.
5. SEVERITY ENUM: Each problem's "severity" field MUST be exactly one of these three literal strings: "LOW", "MEDIUM", "HIGH". Do not use any other word (e.g. never "CRITICAL", "URGENT", or "MINOR") — the response will be rejected otherwise.

OUTPUT SCHEMA (Output ONLY valid JSON):
{{
  "fun_rating": 8.0,
  "difficulty_rating": 7.0,
  "clarity_rating": 8.5,
  "strengths": ["Locomotion feels responsive", "Wave pacing provides steady escalation"],
  "problems": [
    {{
      "category": "combat_balance",
      "severity": "HIGH",
      "evidence": "Player received heavy damage (60 HP) within the first 25 seconds",
      "diagnosis": "Early wave enemies deal high contact damage without sufficient evasion telegraph"
    }}
  ],
  "recommendations": [
    {{
      "id": "rec_player_speed_buff",
      "category": "mobility",
      "description": "Increase player speed from 250 to 280 to improve evasion reaction windows",
      "dsl_change_type": "player_speed",
      "evidence": "Player damage taken exceeded 50 HP in short session",
      "suggested_patch": {{"player": {{"speed": 280}}}}
    }}
  ]
}}"""


def build_improvement_prompt(
    current_dsl: Dict[str, Any],
    design_spec: Dict[str, Any],
    selected_recommendations: List[Dict[str, Any]],
) -> str:
    """Build prompt instructing model to apply selected recommendations cleanly to DSL."""
    recs_str = "\n".join(
        f"- [{r.get('category', 'general')}] {r.get('description')}"
        for r in selected_recommendations
    )
    dsl_str = json.dumps(current_dsl, indent=2)

    return f"""Apply the following approved game improvement recommendations to the current Game DSL:

APPROVED RECOMMENDATIONS:
{recs_str}

CURRENT GAME DSL:
{dsl_str}

Apply ONLY the approved modifications while strictly preserving schema validity and capability constraints.
Output the complete updated JSON Game DSL object."""
