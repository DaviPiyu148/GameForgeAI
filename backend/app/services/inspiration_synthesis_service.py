"""
Inspiration Synthesis service (Step 4: Discovery -> Inspiration -> Studio).

Deterministic, rule-based composition of 2–5 attached inspirations into
a structured GameForge design proposal.
ZERO Gemini / external LLM calls.
"""
import logging
from typing import Dict, List, Set, Tuple
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.project_inspiration import ProjectInspiration
from app.repositories.project_inspiration_repo import (
    ProjectInspirationRepository,
    project_inspiration_repository,
)
from app.schemas.blueprint import BlueprintObjective
from app.schemas.inspiration_synthesis import (
    InspirationSynthesisProposal,
    SourceAttribution,
    SynthesisConflict,
)
from app.schemas.project import BuildParams
from app.services.project_service import project_service, ProjectService

logger = logging.getLogger(__name__)


class InsufficientInspirationsError(Exception):
    """Raised when fewer than 2 inspirations are available for synthesis."""


class ExcessiveInspirationsError(Exception):
    """Raised when more than 5 inspirations are provided."""


# Canonical keyword-to-mechanic mapping
MECHANIC_RULES: List[Tuple[str, List[str], str]] = [
    (
        "DeckBuilding",
        ["deckbuilder", "deck", "card game", "card battler", "hand management"],
        "Deck-driven tactical action selection",
    ),
    (
        "GridTactics",
        ["turn-based", "tactical", "grid", "turn-based combat", "turn-based strategy", "hex"],
        "Turn-based grid positioning and zone control",
    ),
    (
        "ProceduralProgression",
        ["roguelike", "roguelite", "procedural", "permadeath", "dungeon crawler"],
        "Procedural encounter generation with run modifiers",
    ),
    (
        "ResourceCrafting",
        ["survival", "crafting", "base building", "resource management", "mining"],
        "Resource gathering and inventory crafting",
    ),
    (
        "ProjectileBarrage",
        ["shooter", "bullet hell", "shmup", "top-down shooter", "twin stick"],
        "High-density projectile patterns and evasion",
    ),
    (
        "PrecisionLocomotion",
        ["platformer", "metroidvania", "precision platformer", "parkour", "jump"],
        "Momentum-based jumping and obstacle traversal",
    ),
    (
        "SkillTreeProgression",
        ["rpg", "action rpg", "hack and slash", "character customization", "level up"],
        "Talent tree unlocks and attribute scaling",
    ),
    (
        "StealthEvasion",
        ["stealth", "hidden", "evasion", "assassin", "shadow"],
        "Line-of-sight evasion and covert objectives",
    ),
    (
        "LogicObstacles",
        ["puzzle", "physics puzzle", "logic", "sokoban", "brain"],
        "Environmental logic switches and puzzle chambers",
    ),
    (
        "WaveDefense",
        ["tower defense", "defense", "horde", "wave", "arena survival"],
        "Escalating horde defense and perimeter fortification",
    ),
]


class InspirationSynthesisService:
    """Service that deterministically synthesizes structured design proposals from inspirations."""

    def __init__(
        self,
        repo: ProjectInspirationRepository = project_inspiration_repository,
        proj_svc: ProjectService = project_service,
    ) -> None:
        self.repo = repo
        self.proj_svc = proj_svc

    def synthesize(
        self,
        db: Session,
        project_id: str,
        user_id: str,
    ) -> InspirationSynthesisProposal:
        """
        Synthesize a structured design proposal from 2–5 attached inspirations.
        Does NOT modify the project's Blueprint.
        """
        # 1. Verify project ownership
        project = self.proj_svc._get_owned_project(db, project_id, user_id=user_id)

        # 2. Fetch inspirations
        inspirations = self.repo.list_by_project(db, project_id)
        count = len(inspirations)

        if count < 2:
            raise InsufficientInspirationsError(
                f"Inspiration synthesis requires 2 to 5 attached inspirations (found {count})."
            )
        if count > 5:
            raise ExcessiveInspirationsError(
                f"Inspiration synthesis supports a maximum of 5 inspirations (found {count})."
            )

        return self._compute_proposal(project, inspirations)

    def _compute_proposal(
        self,
        project: Project,
        inspirations: List[ProjectInspiration],
    ) -> InspirationSynthesisProposal:
        """Pure deterministic proposal computation from project and inspiration snapshots."""
        source_titles = [i.title for i in inspirations]
        source_app_ids = [i.steam_app_id for i in inspirations]

        # 1. Normalize tags, genres, player_modes per inspiration
        game_metadata_map: Dict[str, Dict[str, Any]] = {}
        for insp in inspirations:
            raw_tags = insp.tags if isinstance(insp.tags, list) else []
            raw_genres = insp.genres if isinstance(insp.genres, list) else []
            raw_modes = insp.player_modes if isinstance(insp.player_modes, list) else []

            all_keywords = {str(k).lower().strip() for k in raw_tags + raw_genres if str(k).strip()}
            game_metadata_map[insp.steam_app_id] = {
                "title": insp.title,
                "genres": [str(g).strip() for g in raw_genres if str(g).strip()],
                "tags": [str(t).strip() for t in raw_tags if str(t).strip()],
                "modes": [str(m).strip() for m in raw_modes if str(m).strip()],
                "keywords": all_keywords,
            }

        # 2. Extract Shared Anchors (occurring in >= 2 inspirations)
        shared_anchors: List[str] = []
        genre_counts: Dict[str, List[str]] = {}
        tag_counts: Dict[str, List[str]] = {}
        mode_counts: Dict[str, List[str]] = {}

        for app_id, meta in game_metadata_map.items():
            for g in meta["genres"]:
                genre_counts.setdefault(g.lower(), []).append(g)
            for t in meta["tags"]:
                tag_counts.setdefault(t.lower(), []).append(t)
            for m in meta["modes"]:
                mode_counts.setdefault(m.lower(), []).append(m)

        for _, instances in genre_counts.items():
            if len(instances) >= 2:
                shared_anchors.append(f"Genre: {instances[0]}")
        for _, instances in tag_counts.items():
            if len(instances) >= 2:
                shared_anchors.append(f"Tag: #{instances[0]}")
        for _, instances in mode_counts.items():
            if len(instances) >= 2:
                shared_anchors.append(f"Mode: {instances[0]}")

        # 3. Mapped Mechanics with Traceable Source Attribution
        attributions: List[SourceAttribution] = []
        active_mechanics: List[str] = []
        inspiration_mechanic_hits: Dict[str, int] = {app_id: 0 for app_id in source_app_ids}

        for mech_name, keywords, _ in MECHANIC_RULES:
            contributing_app_ids: List[str] = []
            contributing_titles: List[str] = []
            matched_keywords: Set[str] = set()

            for app_id, meta in game_metadata_map.items():
                intersection = meta["keywords"].intersection(set(keywords))
                if intersection:
                    contributing_app_ids.append(app_id)
                    contributing_titles.append(meta["title"])
                    matched_keywords.update(intersection)
                    inspiration_mechanic_hits[app_id] += 1

            if contributing_app_ids:
                active_mechanics.append(mech_name)
                attributions.append(
                    SourceAttribution(
                        element=mech_name,
                        category="mechanic",
                        source_steam_app_ids=contributing_app_ids,
                        source_titles=contributing_titles,
                        trigger_attributes=sorted(list(matched_keywords)),
                    )
                )

        # Fallback if no specific mechanic keyword matched: provide baseline mechanics from project
        if not active_mechanics:
            active_mechanics = ["SkillTreeProgression", "WaveDefense"]
            attributions.append(
                SourceAttribution(
                    element="SkillTreeProgression",
                    category="mechanic",
                    source_steam_app_ids=source_app_ids,
                    source_titles=source_titles,
                    trigger_attributes=["Project Context Fallback"],
                )
            )

        # 4. Complementary Anchors (Mechanics supported across distinct inspirations)
        complementary_anchors: List[str] = []
        if len(active_mechanics) >= 2:
            complementary_anchors.append(f"Composite: {' + '.join(active_mechanics[:3])}")

        # 5. Detect Incompatible Conflicts
        conflicts: List[SynthesisConflict] = []

        # Conflict A: Single-player vs Multiplayer exclusive
        has_single = any("single-player" in [m.lower() for m in meta["modes"]] for meta in game_metadata_map.values())
        has_multi = any(
            any(m.lower() in ["multi-player", "multiplayer", "pvp", "online pvp", "co-op"] for m in meta["modes"])
            for meta in game_metadata_map.values()
        )
        single_sources = [m["title"] for m in game_metadata_map.values() if "single-player" in [x.lower() for x in m["modes"]]]
        multi_sources = [
            m["title"]
            for m in game_metadata_map.values()
            if any(x.lower() in ["multi-player", "multiplayer", "pvp", "co-op"] for x in m["modes"])
        ]

        if has_single and has_multi and len(set(single_sources).intersection(set(multi_sources))) == 0:
            conflicts.append(
                SynthesisConflict(
                    field="player_modes",
                    description="Inspirations include mutually exclusive Single-player only and Multiplayer references.",
                    conflicting_sources=[f"{s} (Single-player)" for s in single_sources] + [f"{m} (Multiplayer)" for m in multi_sources],
                    options=["Single-Player Campaign Focus", "Cooperative Multiplayer Mode"],
                    resolution_status="UNRESOLVED",
                )
            )

        # Conflict B: Turn-Based vs High-Twitch Real-Time Bullet Hell
        if "GridTactics" in active_mechanics and "ProjectileBarrage" in active_mechanics:
            tactics_sources = [m["title"] for m in game_metadata_map.values() if "GridTactics" in [a.element for a in attributions if m["title"] in a.source_titles]]
            barrage_sources = [m["title"] for m in game_metadata_map.values() if "ProjectileBarrage" in [a.element for a in attributions if m["title"] in a.source_titles]]
            conflicts.append(
                SynthesisConflict(
                    field="combat_tempo",
                    description="Synthesis combines turn-based grid tactics with real-time projectile dodging.",
                    conflicting_sources=tactics_sources + barrage_sources,
                    options=["Turn-Based Tactical Phases with Action Attacks", "Active-Time Pausable Tactical Combat"],
                    resolution_status="UNRESOLVED",
                )
            )

        # 6. No-Copy Guard (Single-source dominance detection)
        total_hits = sum(inspiration_mechanic_hits.values()) or 1
        is_single_dominant = False
        dominant_title = None

        for app_id, hits in inspiration_mechanic_hits.items():
            if hits / total_hits >= 0.75 and len(active_mechanics) >= 3:
                is_single_dominant = True
                dominant_title = game_metadata_map[app_id]["title"]
                break

        # 7. Proposed Genre, Archetype, and Theme
        proposed_genres = [project.genre]
        for _, instances in genre_counts.items():
            if instances[0] not in proposed_genres:
                proposed_genres.append(instances[0])
        proposed_genre = " ".join(proposed_genres[:3])

        # Archetype inference
        if "PrecisionLocomotion" in active_mechanics:
            proposed_archetype = "platformer"
        elif "ProjectileBarrage" in active_mechanics:
            proposed_archetype = "shooter"
        elif "GridTactics" in active_mechanics or "DeckBuilding" in active_mechanics:
            proposed_archetype = "arena"
        elif "ResourceCrafting" in active_mechanics:
            proposed_archetype = "survival"
        else:
            proposed_archetype = getattr(project, "parameters", {}).get("engine", "survival") if hasattr(project, "parameters") else "survival"

        # Theme inference
        all_kw = {kw for m in game_metadata_map.values() for kw in m["keywords"]}
        if any(t in all_kw for t in ["cyberpunk", "sci-fi", "space", "robots", "futuristic"]):
            proposed_theme = "cyberpunk"
        elif any(t in all_kw for t in ["dungeon", "fantasy", "magic", "dark fantasy"]):
            proposed_theme = "dungeon"
        elif any(t in all_kw for t in ["retro", "arcade", "pixel"]):
            proposed_theme = "retro_arcade"
        elif any(t in all_kw for t in ["wasteland", "post-apocalyptic"]):
            proposed_theme = "wasteland"
        else:
            proposed_theme = "neon"

        # 8. Abstract Gameplay Loop
        loop_steps = []
        if "ProceduralProgression" in active_mechanics:
            loop_steps.append("Infiltrate procedural sector")
        else:
            loop_steps.append("Deploy into tactical encounter")

        if "GridTactics" in active_mechanics or "DeckBuilding" in active_mechanics:
            loop_steps.append("Execute card-driven tactical positioning")
        elif "ProjectileBarrage" in active_mechanics:
            loop_steps.append("Evade projectile patterns while engaging targets")
        else:
            loop_steps.append("Defeat hostile entities and collect key modifiers")

        if "ResourceCrafting" in active_mechanics:
            loop_steps.append("Harvest tactical resources and craft loadout upgrades")
        elif "SkillTreeProgression" in active_mechanics:
            loop_steps.append("Upgrade talent proficiencies")
        else:
            loop_steps.append("Acquire combat score multipliers")

        loop_steps.append("Defeat zone apex to advance forward milestone")
        gameplay_loop = " -> ".join(loop_steps)

        # 9. Design Objectives
        design_objectives = [
            BlueprintObjective(
                level_number=1,
                type="PRIMARY",
                description=f"Survive procedural wave encounters utilizing {active_mechanics[0]} mechanics.",
            ),
            BlueprintObjective(
                level_number=1,
                type="SECONDARY",
                description=f"Maximize tactical synergy between {active_mechanics[min(1, len(active_mechanics)-1)]} and environment.",
            ),
            BlueprintObjective(
                level_number=1,
                type="MASTERY",
                description="Complete the sector with zero structural vitality depletion.",
            ),
        ]

        # 10. Recommended Parameters
        recommended_parameters = BuildParams(
            engine=proposed_archetype,
            art_density=60,
            physics=75 if proposed_archetype in ["shooter", "platformer"] else 45,
            scale="standard",
            world_mode="campaign" if "ProceduralProgression" in active_mechanics else "linear",
            modules=["InventorySystem", "HealthBar", "ScoreTracker", "WeaponUpgrade"],
        )

        # 11. Confidence Calculation
        unresolved_conflicts = [c for c in conflicts if c.resolution_status == "UNRESOLVED"]
        if len(shared_anchors) >= 1 and len(unresolved_conflicts) == 0 and not is_single_dominant:
            confidence = "HIGH"
            explanation = f"High coherence: {len(shared_anchors)} shared attribute anchors with zero blocking conflicts."
        elif len(unresolved_conflicts) <= 1 and not is_single_dominant:
            confidence = "MEDIUM"
            explanation = "Solid complementary mechanics identified with 1 design decision requiring developer review."
        else:
            confidence = "LOW"
            explanation = "Multi-source synthesis includes conflicting gameplay tempos or single-source dominance."

        return InspirationSynthesisProposal(
            project_id=project.id,
            inspiration_count=len(inspirations),
            source_titles=source_titles,
            proposed_title=f"Design Synthesis: {proposed_genre}",
            proposed_genre=proposed_genre,
            proposed_archetype=proposed_archetype,
            proposed_theme=proposed_theme,
            proposed_player_modes=["Single-player Focus"] if not has_multi else ["Single-player", "Cooperative Mode"],
            proposed_mechanics=active_mechanics[:6],
            gameplay_loop=gameplay_loop,
            progression_direction="Branching unlock paths with procedural loadout modifications",
            design_objectives=design_objectives,
            recommended_parameters=recommended_parameters,
            shared_anchors=shared_anchors,
            complementary_anchors=complementary_anchors,
            conflicts=conflicts,
            source_attribution=attributions,
            is_single_source_dominant=is_single_dominant,
            dominant_source_title=dominant_title,
            confidence=confidence,
            confidence_explanation=explanation,
        )


inspiration_synthesis_service = InspirationSynthesisService()
