"""
Game Generation Contract & Pre-Generation Request Understanding.

Extracts a canonical GameGenerationContract from user prompt and builder options
prior to prompting the AI model. Distinguishes EXPLICIT requirements from INFERRED
preferences and OPTIONAL interpretations to ensure honest requirement tracking.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.generation.runtime_capabilities import (
    RUNTIME_CAPABILITIES,
    check_for_unsupported_concepts,
    is_capability_supported,
)


class RequirementConfidence:
    EXPLICIT_REQUIREMENT = "EXPLICIT_REQUIREMENT"
    INFERRED_PREFERENCE = "INFERRED_PREFERENCE"
    OPTIONAL_INTERPRETATION = "OPTIONAL_INTERPRETATION"


@dataclass
class TrackedRequirement:
    """A single user-requested game feature or system with tracked confidence."""
    name: str
    confidence: str  # EXPLICIT_REQUIREMENT, INFERRED_PREFERENCE, OPTIONAL_INTERPRETATION
    matched_text: str
    runtime_capability: Optional[str] = None  # Identifier in RUNTIME_CAPABILITIES if applicable
    supported: bool = True
    reason: Optional[str] = None


@dataclass
class GameGenerationContract:
    """
    Structured pre-generation specification establishing user intent,
    architectural scale, required runtime capabilities, and progression plan.
    """
    raw_prompt: str
    genre: str
    archetype: str
    world_mode: str
    scale: str
    core_loop: str
    player_goal: str
    fail_conditions: List[str]
    progression_plan: str
    tracked_requirements: List[TrackedRequirement] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    optional_capabilities: List[str] = field(default_factory=list)
    unsupported_requests: List[Tuple[str, str]] = field(default_factory=list)
    visual_direction: str = "neon"
    design_pattern_id: str = "CP_PROGRESSIVE_ESCALATION"
    palette: Dict[str, str] = field(default_factory=dict)

    @property
    def explicit_requirements(self) -> List[TrackedRequirement]:
        return [
            r for r in self.tracked_requirements
            if r.confidence == RequirementConfidence.EXPLICIT_REQUIREMENT
        ]



# ─────────────────────────────────────────────────────────────────────────────
# Request Parser
# ─────────────────────────────────────────────────────────────────────────────

def build_generation_contract(
    prompt: str,
    engine: str = "Top-Down Action",
    scale: str = "standard",
    world_mode: str = "linear",
    modules: Optional[List[str]] = None,
    art_density: int = 50,
    physics: int = 80,
) -> GameGenerationContract:
    """
    Converts raw Builder request into a canonical structured understanding
    before calling Gemini or generating GameDSL.
    """
    text = prompt.lower().strip()
    active_modules = modules or []

    # 1. Determine Archetype & Genre
    archetype = "survival"
    genre = "Action"

    if "platform" in text or engine == "2D Platformer":
        archetype = "platformer"
        genre = "Platformer"
    elif "collect" in text or "gather" in text or engine == "Data Collector":
        archetype = "collector"
        genre = "Collector"
    elif "arena" in text or engine == "Arena Survival":
        archetype = "arena"
        genre = "Action Survival"
    elif "shoot" in text or "gun" in text:
        archetype = "shooter"
        genre = "Shooter"
    elif "open-world" in text or "open world" in text or world_mode == "open_world":
        archetype = "survival"
        genre = "Open World Action"

    # Refine genre with thematic keywords
    if "cyberpunk" in text:
        genre = "Cyberpunk " + genre
    elif "space" in text or "sci-fi" in text:
        genre = "Sci-Fi " + genre
    elif "fantasy" in text or "dungeon" in text:
        genre = "Fantasy " + genre
    elif "zombie" in text or "horror" in text:
        genre = "Survival Horror"

    # 2. Extract Tracked Requirements & Confidence
    tracked: List[TrackedRequirement] = []
    unsupported: List[Tuple[str, str]] = check_for_unsupported_concepts(prompt)

    for item, reason in unsupported:
        tracked.append(
            TrackedRequirement(
                name=item,
                confidence=RequirementConfidence.EXPLICIT_REQUIREMENT,
                matched_text=item,
                runtime_capability=None,
                supported=False,
                reason=reason,
            )
        )

    # Capability keyword mappings
    capability_patterns = [
        ("VEHICLES", ["vehicle", "car", "drive", "bike", "hovercraft", "courier", "transport"]),
        ("FACTIONS", ["faction", "rival", "gang", "syndicate", "reputation", "hostile"]),
        ("THREAT_SYSTEM", ["threat", "heat", "wanted", "police", "security", "alarm", "escalat"]),
        ("ACTIVITIES", ["mission", "contract", "quest", "delivery", "activity", "hack", "data theft"]),
        ("OPEN_WORLD_REGIONS", ["district", "region", "zone", "sector", "open world", "open-world"]),
        ("DASH", ["dash", "dodge", "evad"]),
        ("COMBAT_RANGED", ["shoot", "ranged", "gun", "laser", "projectile"]),
        ("COMBAT_MELEE", ["melee", "sword", "slash", "punch"]),
        ("BOSS_FINALE", ["boss", "overlord", "final encounter", "extraction", "finale", "escape"]),
        ("WORLD_TIME", ["day night", "day/night", "time cycle", "night"]),
        ("WORLD_EVENTS", ["event", "storm", "ambush", "sweep"]),
        ("COLLECTIBLES", ["collect", "gather", "steal", "loot", "crystal", "coin", "data"]),
    ]

    for cap_id, keywords in capability_patterns:
        is_explicit = False
        matched_word = ""
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw), text):
                is_explicit = True
                matched_word = kw
                break

        if is_explicit:
            tracked.append(
                TrackedRequirement(
                    name=cap_id,
                    confidence=RequirementConfidence.EXPLICIT_REQUIREMENT,
                    matched_text=matched_word,
                    runtime_capability=cap_id,
                    supported=is_capability_supported(cap_id),
                )
            )

    # Add requirements from explicit Builder UI Module toggles
    module_cap_map = {
        "Combat & Dash Mobility": ["COMBAT_RANGED", "DASH"],
        "Resource & Score Economy": ["COLLECTIBLES"],
        "Enhanced NPC Behavior": ["FACTIONS"],
        "Procedural Generation": ["CAMPAIGN_LEVELS"],
    }
    for mod in active_modules:
        if mod in module_cap_map:
            for cap_id in module_cap_map[mod]:
                if not any(r.runtime_capability == cap_id for r in tracked):
                    tracked.append(
                        TrackedRequirement(
                            name=cap_id,
                            confidence=RequirementConfidence.EXPLICIT_REQUIREMENT,
                            matched_text=f"Module: {mod}",
                            runtime_capability=cap_id,
                            supported=is_capability_supported(cap_id),
                        )
                    )

    # 3. Core Loop & Goals Formulation
    if archetype == "platformer":
        core_loop = "Traverse -> Jump Hazards -> Collect Beacons -> Reach Goal"
        player_goal = "Navigate through challenging terrain to reach the level extraction point."
    elif archetype == "collector":
        core_loop = "Explore Area -> Evade Guardians -> Gather Resource Nodes -> Clear Zone"
        player_goal = "Collect all required data nodes before time or stamina runs out."
    elif world_mode == "open_world" or any(r.runtime_capability == "OPEN_WORLD_REGIONS" for r in tracked):
        core_loop = "Infiltrate District -> Execute Mission/Activity -> Evade Security/Threat -> Extract"
        player_goal = "Complete district operations while managing faction hostility and threat level."
    else:
        core_loop = "Engage Targets -> Dash Evasion -> Collect Pickups -> Survive Waves"
        player_goal = "Survive escalating hostile pressure and eliminate key threats."

    # 4. Progression & Scale Plan
    if scale == "prototype":
        progression_plan = "Single focused level (1-2) with rapid mechanic demonstration and win/lose resolution."
    elif scale == "standard":
        progression_plan = "2-3 level arc: Intro -> Escalating Challenge -> Climax/Finale."
    else:
        progression_plan = "3-5 level campaign: Introduction -> Learning -> Escalation -> Variation -> High-threat Finale."

    # 5. Visual Direction & Thematic Palette
    visual_direction = "neon"
    theme_palettes = {
        "cyberpunk": {"bg": "#0a0518", "player": "#00f0ff", "accent": "#ff0055", "hazard": "#ffaa00"},
        "space": {"bg": "#020412", "player": "#66e3ff", "accent": "#bd00ff", "hazard": "#ff3366"},
        "dungeon": {"bg": "#120d0a", "player": "#ffb84d", "accent": "#ff3300", "hazard": "#990000"},
        "wasteland": {"bg": "#1a140e", "player": "#ffd166", "accent": "#ef476f", "hazard": "#06d6a0"},
        "urban": {"bg": "#0f172a", "player": "#38bdf8", "accent": "#f43f5e", "hazard": "#fbbf24"},
        "retro_arcade": {"bg": "#050014", "player": "#39ff14", "accent": "#ff073a", "hazard": "#ffe600"},
        "fantasy": {"bg": "#0d1b1e", "player": "#70e000", "accent": "#9d4edd", "hazard": "#e85d04"},
        "neon": {"bg": "#050510", "player": "#00f0ff", "accent": "#ff0077", "hazard": "#ffbb00"},
    }
    for theme_opt in ["cyberpunk", "space", "dungeon", "wasteland", "urban", "retro_arcade", "fantasy"]:
        if theme_opt in text:
            visual_direction = theme_opt
            break

    selected_palette = theme_palettes.get(visual_direction, theme_palettes["neon"])

    # 6. Select Structural Design Pattern
    from app.generation.design_patterns import select_design_pattern
    resolved_world_mode = "open_world" if (world_mode == "open_world" or "open world" in text or "open-world" in text) else world_mode
    pattern = select_design_pattern(
        archetype=archetype,
        world_mode=resolved_world_mode,
        scale=scale,
        has_vehicles=any(r.runtime_capability == "VEHICLES" for r in tracked),
        has_factions=any(r.runtime_capability == "FACTIONS" for r in tracked),
        has_threat=any(r.runtime_capability == "THREAT_SYSTEM" for r in tracked),
    )

    # Required vs Optional Capabilities
    required_caps = [
        r.runtime_capability for r in tracked
        if r.confidence == RequirementConfidence.EXPLICIT_REQUIREMENT and r.runtime_capability
    ]
    optional_caps = ["WORLD_TIME", "WORLD_EVENTS", "DASH"]

    return GameGenerationContract(
        raw_prompt=prompt,
        genre=genre,
        archetype=archetype,
        world_mode=resolved_world_mode,
        scale=scale,
        core_loop=core_loop,
        player_goal=player_goal,
        fail_conditions=["Depletion of player health (HP <= 0)", "Excessive threat/timeout if bounded"],
        progression_plan=progression_plan,
        tracked_requirements=tracked,
        required_capabilities=required_caps,
        optional_capabilities=optional_caps,
        unsupported_requests=unsupported,
        visual_direction=visual_direction,
        design_pattern_id=pattern.id,
        palette=selected_palette,
    )

