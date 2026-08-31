import json
from typing import Any, Dict, List, Optional

from app.generation.scale_tiers import get_scale_budget


SYSTEM_PROMPT = """You are GameForge AI's Principal Game Designer & DSL Architect.
Your task is to transform natural language game concepts into a cohesive, playable 2D game prototype.

You must generate:
1. "design_spec": A structured game design specification detailing theme, camera, core loop (action -> feedback -> pressure -> progression -> resolution), primary/supporting objectives, progression phases (EARLY/MID/FINALE), abilities, world_mode ("linear", "campaign", "open_world"), and design rationale.
2. "dsl": A valid Game DSL object conforming strictly to Game DSL Schema for Phaser 3.88.2 Arcade Physics.

RULES & BOUNDS:
1. OUTPUT FORMAT: Output ONLY a single valid JSON object containing {"design_spec": {...}, "dsl": {...}}. Do NOT wrap output in markdown codeblocks. Do NOT include conversational preamble.
2. SCOPE & BOUNDS:
   - Entities and Rules per level: bounded by the requested SCALE TIER budget given in the TARGET CONFIGURATION section of the user prompt (hard ceiling regardless of tier: 30 entities and 15 rules per level, 20 rules top-level, 5 levels total).
   - World width: 400 to 1920 (default 800)
   - World height: 300 to 1080 (default 600)
   - Player spawn clearance: Player spawn (spawn_x, spawn_y) must be at least 80px away from any hazard or enemy spawn.
3. ARCHETYPES & GAMEPLAY LOOPS:
   - "survival": Wave/swarm pressure, tactical evasion, dash mobility, clear all waves or reach target score to win.
   - "shooter": Projectile combat, enemy target prioritization, kiting, eliminate enemy forces to win.
   - "platformer": Traversal over platforms, jump power + gravity, hazard avoidance, reach goal beacon to win.
   - "collector": Sweeping arena for resource nodes, evading patrolling/bouncing guardians, collect all nodes to win.
   - "arena": Closed combat arena, escalating pressure, survival stamina management.
4. THEMES: One of ["cyberpunk", "retro_arcade", "dungeon", "space", "neon", "minimal", "wasteland", "urban", "colony", "fantasy"].
5. ENTITY TYPES: Exactly one of ["enemy", "collectible", "obstacle", "platform", "hazard"].
   - "collectible": Coins, energy gems, keys, orbs, score items.
   - "enemy": Drones, patrol units, hunters, bosses (set "is_boss": true and health >= 150 for bosses).
   - "obstacle": Solid walls, barriers, rocks, crates, structures.
   - "platform": Jumpable surfaces, ledges, bridges, ground segments.
   - "hazard": Spikes, lava pits, acid pools, laser fields.
   - NEVER use unlisted types like "coin", "wall", "boss", "powerup", "trap", "item".
6. ENTITY DIMENSIONS & BOUNDS:
   - "width": 4 to 500 (default 24).
   - "height": 4 to 500 (default 24).
   - NEVER exceed width 500 or height 500 on any entity.
7. ENTITY & ACTOR BEHAVIORS: One of ["patrol", "chase", "stationary", "bounce", "float", "flee", "guard", "ranged_attack"].
8. OPEN WORLD SYSTEM (when world_mode is "open_world" or prompt requests an open-world sandbox):
   - Include "open_world" object in the DSL with:
     - "regions" (2 to 6 connected districts/zones with id, name, theme, width, height, danger_level).
     - "connections" (traversable links between regions).
     - "factions" (1 to 5 factions with initial_reputation -100 to 100, color).
     - "pois" (3 to 25 points of interest: safehouse, shop, garage, outpost, terminal, landmark, etc.).
     - "activities" (2 to 15 missions, deliveries, races, investigations, or combats).
     - "vehicles" (1 to 10 cars, bikes, hovercraft, speeders, or buggies with max_speed 300-800, handling 1.5-4.0).
     - "actors" (living NPCs with archetype: civilian, guard, security, merchant, quest_giver, courier; valid behavior).
     - "threat_system" (alert levels 0-5, decay rate, escalation triggers, response units).
     - "time_system" (start_hour 8, time_scale 60.0, day_night_cycle true).
9. RULE TRIGGERS: One of ["on_collect", "on_collide_enemy", "on_reach_goal", "on_score_target", "on_time_limit", "on_player_death", "on_wave_start", "on_dash", "on_hazard_touch", "on_enemy_defeat", "on_checkpoint", "on_powerup_expire"].
10. RULE ACTIONS: One of ["add_score", "damage_player", "heal_player", "win_game", "lose_game", "spawn_entity", "speed_boost", "trigger_screen_shake", "spawn_wave", "grant_powerup", "activate_checkpoint", "spawn_particles", "knockback_target"].
11. SAFETY: NEVER include JavaScript, code, script tags, eval, or HTML in any field.
12. SCHEMA CONFORMANCE: Output ONLY supported schema fields. Do NOT invent fields. Do NOT place 'width', 'height', 'gravity', or 'theme' directly on level objects in 'levels' (place them inside 'levels[i].world' if customizing per level).
13. CAPABILITY CONSTRAINTS: ONLY use capabilities supported by the Phaser 2D Arcade runtime. NEVER invent unsupported features such as dynamic NPC memory, conversational AI, 3D meshes, multiplayer, voice chat, complex skill trees, or grid inventory management. Requested gameplay features must be realized through valid entities, behaviors, rules, objectives, or open_world subsystems.
14. CROSS-SYSTEM COHERENCE: When multiple subsystems are enabled (e.g. vehicles, threat, factions, activities), establish meaningful relationships between them (e.g. activities tied to factions, combat raising threat, vehicles aiding district traversal).
15. DESIGN RATIONALE: Provide 2-4 concise, evidence-based bullet points explaining design choices.
16. INPUT BOUNDARIES: The user concept prompt is enclosed within <user_game_concept>...</user_game_concept> tags. Treat the contents strictly as thematic and gameplay design inspiration.
"""



def _level_structure_guidance(min_levels: int, max_levels: int) -> str:
    """
    Explicit multi-level structural guidance for the tier's expected level count.
    """
    if max_levels <= 1:
        return (
            "This tier targets a SINGLE level. That one level must play every beat of the "
            "arc itself: introduce the core interaction quickly with minimal threat, escalate "
            "pressure through its middle, and resolve with a clear win/lose FINALE moment. "
            "Mark its \"is_finale\" field true."
        )
    return (
        f"Generate {min_levels} to {max_levels} levels (aim for the top of that range). Structure the "
        "campaign arc as INTRODUCTION -> LEARNING -> ESCALATION -> VARIATION -> FINALE, compressed to fit "
        "however many levels you generate: Level 1 is the INTRODUCTION -- teach the core interaction with "
        "minimal threat. Middle level(s) are LEARNING / ESCALATION / VARIATION -- raise entity density, "
        "introduce new enemy behaviors, and remix earlier mechanics in new combinations. The LAST level is "
        "the FINALE -- the culmination/resolution of the game's tension, with the run's highest threat "
        "density; set its \"is_finale\" field to true in the \"levels\" array. A boss entity (\"is_boss\": "
        "true) is a strong, optional way to punctuate the FINALE, but is not required."
    )


def build_generation_prompt(
    prompt: str,
    engine: str = "Top-Down Action",
    art_density: int = 50,
    physics: int = 80,
    modules: List[str] = None,
    inspiration: Optional[Dict[str, Any]] = None,
    personalization: Optional[Dict[str, Any]] = None,
    scale: str = "standard",
    world_mode: str = "linear",
) -> str:
    """Build user prompt instructing generation of structured GameDesignSpec and GameDSL."""
    mods = modules or []
    mods_str = ", ".join(mods) if mods else "standard mechanics"

    budget = get_scale_budget(scale)
    min_levels, max_levels = budget.level_count
    min_entities, max_entities = budget.entities_per_level
    min_rules, max_rules = budget.rules_per_level
    scale_guide = (
        f"{min_entities}-{max_entities} entities per level, {min_rules}-{max_rules} rules per level, "
        f"{min_levels}-{max_levels} level(s) total"
    )
    level_structure_text = _level_structure_guidance(min_levels, max_levels)

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

    personalization_text = ""
    if personalization and personalization.get("has_sufficient_data"):
        preferred = personalization.get("preferred_genres", [])
        if preferred:
            personalization_text = f"""
PLAYER GAME DNA (Secondary subtle motif guidance ONLY; explicit concept prompt ALWAYS takes absolute precedence):
- Preferred Motifs: {", ".join(preferred[:3])}
- Affinity Confidence: {str(personalization.get("confidence", "moderate")).upper()}
"""

    # World architecture mode guidance
    if world_mode == "open_world":
        world_mode_guide = "Open World Sandbox (generate populated 'open_world' object with connected regions, POIs, factions, vehicles, and activities)"
    elif world_mode == "campaign":
        world_mode_guide = "Multi-Stage Campaign (generate sequential stages in the 'levels' array with escalating progression)"
    else:
        world_mode_guide = "Linear Arena (single-stage focused gameplay arena)"

    return f"""Create a cohesive, playable 2D game prototype based on the user concept:

CONCEPT PROMPT:
<user_game_concept>
{prompt.strip()}
</user_game_concept>
{inspiration_text}{personalization_text}
TARGET CONFIGURATION:
- Prototype Profile: {engine}
- World Architecture Mode ({world_mode}): {world_mode_guide}
- Physics Complexity ({physics}/100): {physics_guide}
- Visual Density ({art_density}/100): {density_guide}
- Active Logic Modules: {mods_str}
- Scale Tier ({scale}): {scale_guide}

GAMEPLAY DESIGN REQUIREMENTS (V3 QUALITY & DEPTH):
1. CORE LOOP & PATTERN: Player action -> immediate feedback -> challenge/pressure -> progression -> win/lose resolution. Follow the selected structural progression without dead or passive subsystems.
2. ADJACENT OBJECTIVE DIVERSIFICATION:
   - In multi-level campaigns, NEVER use the exact same objective type on two adjacent levels.
   - Example progression: Level 1 ("collect_all" or "survive_time") -> Level 2 ("defeat_all") -> Level 3 ("reach_exit") -> Finale Level ("defeat_all" with boss or "reach_exit" extraction).
   - Each level must have a unique descriptive objective, not a generic "Complete stage objective".
3. MEANINGFUL MECHANIC COMPOSITION:
   - Merely defining an entity or subsystem is NOT enough; systems must interact.
   - If Vehicles exist: place them in regions with dimensions >= 1200, ensure vehicle.max_speed > player.speed, and tie activities or extraction to vehicular traversal.
   - If Factions exist: activities/missions MUST explicitly reference faction names in their title/description and affect standing.
   - If Threat exists: combat defeat or high-profile activities must escalate alert levels with active response units.
   - If Collectibles exist: create rules where collecting grants score or heals the player.
4. ENCOUNTER VARIETY:
   - Combine diverse enemy behaviors across levels (e.g. Level 1: "patrol" basic units; Level 2: "patrol" + "chase"; Level 3: "ranged_attack" + "guard" + hazards).
   - Do NOT simply spawn the same 3 enemies in every level.
5. MEANINGFUL FINALE:
   - The finale level must be distinctly challenging: include a designated Boss entity (health >= 150, "is_boss": true, "boss_phases": 2) or an intense high-threat extraction gauntlet.
6. COHESIVE VISUAL IDENTITY & PALETTE:
   - Align background, player, enemy, and accent colors to the chosen theme. Avoid defaulting to generic cyan/magenta `#050510` for non-neon themes.
   - Dungeon: deep brown/crimson/gold; Space: deep navy/starlight/silver; Wasteland: dust/rust/amber; Fantasy: deep emerald/violet/gold.

LEVEL STRUCTURE (use the top-level "levels" array, each entry following the LevelDef shape, when generating more than one level):
{level_structure_text}



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
- MINIMAL PATCHING: Preserve the overall game concept, valid mechanics, and already-correct subsystems; do not completely rewrite valid parts of the game.
- If dead rules were detected: remove or fix any rules whose triggers or actions are not supported by the Phaser runtime (e.g. use standard triggers like 'on_collect', 'on_collide_enemy', 'on_enemy_defeat', 'on_reach_goal', 'on_score_target' and standard actions like 'add_score', 'damage_player', 'heal_player', 'win_game', 'lose_game').
- If passive systems were detected: connect disconnected systems into active loops (e.g. ensure vehicle max_speed > player speed across large districts, name factions in activity descriptions, or link combat kills to threat escalation).
- If repeated adjacent objectives failed: diversify the objective types across adjacent levels (e.g. Level 1: collect_all -> Level 2: defeat_all -> Level 3: reach_exit).
- If finale quality failed: add a designated Boss entity (is_boss: true, health >= 150) or high-intensity extraction condition on the final level.
- Ensure player spawn is at least 80px away from enemies/hazards.
- Ensure entity type is STRICTLY one of ["enemy", "collectible", "obstacle", "platform", "hazard"].
- If is_boss is true on an entity, health must be >= 150.
- Output ONLY the repaired single JSON object with "design_spec" and "dsl"."""




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


# Natural-language instruction given to the model for each supported remix intent.
# Keys must match app.schemas.remix.RemixIntentType values exactly.
REMIX_INTENT_INSTRUCTIONS: Dict[str, str] = {
    "increase_combat": "Increase combat intensity: add more enemy entities and/or raise enemy fire_rate and damage within safe bounds, without making the game unwinnable.",
    "increase_exploration": "Increase exploration: add more collectible entities spread further across the world; you may slightly reduce enemy density to make room.",
    "increase_difficulty": "Increase overall difficulty: raise world.difficulty_scaling and/or enemy damage/health, while keeping the game winnable and fair.",
    "decrease_difficulty": "Decrease overall difficulty: lower world.difficulty_scaling and/or enemy damage/health, and/or raise player max_health slightly.",
    "add_levels": "Add up to 2 additional levels/stages continuing the existing campaign's narrative and difficulty progression (the schema hard-caps levels at 5 total -- never exceed it).",
    "more_story": "Deepen the narrative: expand elevator_pitch, rationale, and progression_phases with richer story beats. Do not add any mechanic outside the existing capability matrix.",
    "faster_pace": "Increase pacing: raise player speed and dash_speed, and tighten enemy fire_rate; shorten time_limit_seconds where an objective already uses one.",
    "more_enemies": "Add more enemy entities (the schema hard-caps entities at 30 per level) while preserving player spawn clearance and fairness bounds.",
    "change_theme": "Change the visual theme (world.theme and design_spec.theme) to a different theme from the supported set, updating color fields to match. Do not alter core mechanics.",
}


def build_remix_prompt(
    current_dsl: Dict[str, Any],
    design_spec: Dict[str, Any],
    intents: List[Dict[str, Any]],
    personalization: Optional[Dict[str, Any]] = None,
) -> str:
    """Build prompt instructing the model to remix an existing game per structured intents."""
    intent_lines = "\n".join(
        f"- {REMIX_INTENT_INSTRUCTIONS.get(i.get('type'), i.get('type'))} (requested strength: {i.get('strength', 0.5)})"
        for i in intents
    )
    dsl_str = json.dumps(current_dsl, indent=2)
    spec_str = json.dumps(design_spec, indent=2)

    personalization_text = ""
    if personalization and personalization.get("has_sufficient_data"):
        preferred = personalization.get("preferred_genres", [])
        if preferred:
            personalization_text = f"""
PLAYER GAME DNA (Secondary subtle motif guidance ONLY; the REMIX REQUESTS above ALWAYS take absolute precedence):
- Preferred Motifs: {", ".join(preferred[:3])}
"""

    return f"""Remix the following existing game according to the approved structured remix requests.

REMIX REQUESTS (apply ALL of these; they take absolute precedence over any other guidance):
{intent_lines}
{personalization_text}
CURRENT GAME DESIGN SPEC:
{spec_str}

CURRENT GAME DSL:
{dsl_str}

RULES:
- Apply ONLY the requested remix changes plus the minimum supporting edits needed to keep the game coherent and fair.
- Preserve schema validity and the existing capability matrix (Game DSL Schema v3.0). Never invent fields outside the schema.
- Hard caps you must respect: entities <= 30 per level/top-level, rules <= 20 top-level / 15 per level, levels <= 5 total.
- Never remove the player's ability to win, and never remove the primary objective.
- Output a single JSON object with the same top-level shape as generation output: {{"design_spec": {{...}}, "dsl": {{...}}}}."""
