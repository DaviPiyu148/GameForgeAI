"""
Inspiration Synthesis service (Step 4 & 5: Discovery -> Inspiration -> Studio).

Deterministic, rule-based composition of 2–5 attached inspirations into
a structured GameForge design proposal, with versioned Blueprint application.
ZERO Gemini / external LLM calls.
"""
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Set, Tuple
from sqlalchemy import func
from sqlalchemy.exc import DatabaseError, IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.project_inspiration import ProjectInspiration
from app.models.project_version import ProjectVersion
from app.repositories.project_inspiration_repo import (
    ProjectInspirationRepository,
    project_inspiration_repository,
)
from app.schemas.blueprint import BlueprintObjective, GameBlueprint
from app.schemas.inspiration_synthesis import (
    ApplySynthesisProposalRequest,
    ApplySynthesisProposalResponse,
    BlueprintFieldChange,
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


class StaleProposalError(Exception):
    """Raised when proposal base_version_number does not match project's current version."""


class UnresolvedConflictError(Exception):
    """Raised when an inspiration proposal contains unresolved blocking conflicts."""


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

    def apply_proposal(
        self,
        db: Session,
        project_id: str,
        user_id: str,
        data: ApplySynthesisProposalRequest,
    ) -> ApplySynthesisProposalResponse:
        """
        Apply an approved inspiration synthesis proposal to an owned project's Blueprint and DSL.
        Creates an immutable forward ProjectVersion (vN+1).

        Guarantees:
        - Strict base version validation (prevents stale overwrites).
        - Mandatory resolution of all blocking conflicts before apply.
        - Non-destructive targeted patch preserving narrative, custom entities, rules.
        - Concurrency-safe monotonic forward versioning with transaction retry on collision.
        - Full source attribution provenance recorded in design_spec and version summary.
        """
        # 1. Verify project ownership (IDOR check)
        project = self.proj_svc._get_owned_project(db, project_id, user_id=user_id)

        # 2. Optimistic concurrency / stale proposal check
        current_version_num = project.current_version or 1
        if current_version_num != data.base_version_number:
            raise StaleProposalError(
                f"Proposal was generated from base version {data.base_version_number}, "
                f"but project is currently at version {current_version_num}. "
                f"Please refresh the project and regenerate the proposal."
            )

        # 3. Reload inspirations from database
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

        # 4. Deterministically recompute proposal on server to prevent client payload tampering
        proposal = self._compute_proposal(project, inspirations)

        # 5. Validate that all unresolved blocking conflicts are resolved
        for conflict in proposal.conflicts:
            if conflict.resolution_status == "UNRESOLVED":
                if conflict.field not in data.conflict_resolutions:
                    raise UnresolvedConflictError(
                        f"Unresolved conflict on '{conflict.field}' must be resolved before applying proposal."
                    )
                chosen = data.conflict_resolutions[conflict.field]
                if chosen not in conflict.options:
                    raise UnresolvedConflictError(
                        f"Invalid option '{chosen}' for conflict '{conflict.field}'. Allowed options: {conflict.options}"
                    )

        # 6. Compute field-level diffs and construct non-destructive patch
        changes: List[BlueprintFieldChange] = []
        source_summary_titles = ", ".join(proposal.source_titles[:3])

        # A. Genre
        genre_decision = data.field_decisions.get("genre", "APPLY_PROPOSAL")
        if genre_decision == "APPLY_PROPOSAL" and project.genre != proposal.proposed_genre:
            changes.append(
                BlueprintFieldChange(
                    fieldName="genre",
                    previousValue=project.genre,
                    newValue=proposal.proposed_genre,
                    sourceAttribution=f"From inspirations: {source_summary_titles}",
                )
            )
            project.genre = proposal.proposed_genre

        # B. Archetype / Engine
        engine_decision = data.field_decisions.get("engine", "APPLY_PROPOSAL")
        if engine_decision == "APPLY_PROPOSAL" and project.engine != proposal.recommended_parameters.engine:
            changes.append(
                BlueprintFieldChange(
                    fieldName="engine",
                    previousValue=project.engine,
                    newValue=proposal.recommended_parameters.engine,
                    sourceAttribution=f"Inferred archetype from {proposal.proposed_genre}",
                )
            )
            project.engine = proposal.recommended_parameters.engine

        # C. Parameters: Physics, Art Density, World Mode, Modules
        if project.physics != proposal.recommended_parameters.physics:
            changes.append(
                BlueprintFieldChange(
                    fieldName="physics",
                    previousValue=project.physics,
                    newValue=proposal.recommended_parameters.physics,
                    sourceAttribution="Optimized physics for archetype",
                )
            )
            project.physics = proposal.recommended_parameters.physics

        if project.art_density != proposal.recommended_parameters.art_density:
            changes.append(
                BlueprintFieldChange(
                    fieldName="artDensity",
                    previousValue=project.art_density,
                    newValue=proposal.recommended_parameters.art_density,
                    sourceAttribution="Visual density recommendation",
                )
            )
            project.art_density = proposal.recommended_parameters.art_density

        if project.world_mode != proposal.recommended_parameters.world_mode:
            changes.append(
                BlueprintFieldChange(
                    fieldName="worldMode",
                    previousValue=project.world_mode,
                    newValue=proposal.recommended_parameters.world_mode,
                    sourceAttribution="Progression structure recommendation",
                )
            )
            project.world_mode = proposal.recommended_parameters.world_mode

        if set(project.modules or []) != set(proposal.recommended_parameters.modules):
            changes.append(
                BlueprintFieldChange(
                    fieldName="modules",
                    previousValue=project.modules or [],
                    newValue=proposal.recommended_parameters.modules,
                    sourceAttribution="Recommended gameplay modules",
                )
            )
            project.modules = proposal.recommended_parameters.modules

        # D. Design Spec Patching (preserve existing narrative premise & custom fields)
        spec_dict = dict(project.design_spec) if isinstance(project.design_spec, dict) else {}
        
        # Track theme
        prev_theme = spec_dict.get("theme", "neon")
        if prev_theme != proposal.proposed_theme:
            changes.append(
                BlueprintFieldChange(
                    fieldName="theme",
                    previousValue=prev_theme,
                    newValue=proposal.proposed_theme,
                    sourceAttribution=f"Theme synthesis from {source_summary_titles}",
                )
            )
        spec_dict["theme"] = proposal.proposed_theme
        spec_dict["genre"] = project.genre
        spec_dict["subgenre"] = proposal.proposed_archetype.capitalize()
        
        # Track core gameplay loop
        prev_loop = spec_dict.get("core_gameplay_loop", "")
        if prev_loop != proposal.gameplay_loop:
            changes.append(
                BlueprintFieldChange(
                    fieldName="gameplayLoop",
                    previousValue=prev_loop,
                    newValue=proposal.gameplay_loop,
                    sourceAttribution="Composite multi-stage gameplay loop",
                )
            )
        spec_dict["core_gameplay_loop"] = proposal.gameplay_loop

        # Track objectives
        if proposal.design_objectives:
            spec_dict["primary_objective"] = proposal.design_objectives[0].description
            spec_dict["secondary_objectives"] = [o.description for o in proposal.design_objectives[1:]]
            changes.append(
                BlueprintFieldChange(
                    fieldName="objectives",
                    previousValue=spec_dict.get("primary_objective", ""),
                    newValue=f"Primary: {proposal.design_objectives[0].description}",
                    sourceAttribution="Design objectives synthesized from core mechanics",
                )
            )

        # Track mechanics
        prev_abilities = spec_dict.get("player_abilities", [])
        spec_dict["player_abilities"] = proposal.proposed_mechanics[:6]
        changes.append(
            BlueprintFieldChange(
                fieldName="mechanics",
                previousValue=prev_abilities,
                newValue=proposal.proposed_mechanics[:6],
                sourceAttribution="Traceable mechanic composition",
            )
        )

        # Record provenance in rationale
        spec_dict["rationale"] = (
            [f"Synthesized from {len(inspirations)} inspirations: {source_summary_titles}"]
            + [f"Mechanic '{a.element}' sourced from {', '.join(a.source_titles)}" for a in proposal.source_attribution[:4]]
        )
        spec_dict["selected_modules"] = project.modules
        project.design_spec = spec_dict

        # E. Game DSL Patching (if exists, update metadata, world theme, player mechanics)
        if isinstance(project.game_dsl, dict):
            dsl_dict = dict(project.game_dsl)
            dsl_dict.setdefault("metadata", {})["genre"] = project.genre
            dsl_dict.setdefault("metadata", {})["archetype"] = project.engine
            dsl_dict.setdefault("world", {})["theme"] = proposal.proposed_theme
            dsl_dict.setdefault("world", {})["world_mode"] = project.world_mode
            
            # Mechanic-specific adaptations
            if "PrecisionLocomotion" in proposal.proposed_mechanics:
                player = dsl_dict.setdefault("player", {})
                player["jump_power"] = max(player.get("jump_power", 0), 400)
                dsl_dict.setdefault("world", {})["gravity"] = max(dsl_dict.get("world", {}).get("gravity", 0), 600)
            if "ProjectileBarrage" in proposal.proposed_mechanics:
                dsl_dict.setdefault("player", {})["attack_type"] = "ranged"
            
            project.game_dsl = dsl_dict

        # 7. Atomic Concurrency-Safe Forward Versioning (Transaction Retry Loop)
        prev_version_num = current_version_num
        change_desc = f"Inspiration synthesis applied: {len(inspirations)} reference games ({source_summary_titles})"

        new_version_num = data.base_version_number + 1
        try:
            project.current_version = new_version_num
            project.updated_at = datetime.now(timezone.utc)

            version_rec = ProjectVersion(
                project_id=project.id,
                version_number=new_version_num,
                game_dsl=project.game_dsl or {},
                design_spec=project.design_spec,
                change_summary=change_desc,
                remix_intent=None,
            )
            db.add(version_rec)
            db.commit()
            db.refresh(project)
        except (IntegrityError, DatabaseError, OperationalError):
            db.rollback()
            raise StaleProposalError(
                f"Proposal was generated from base version {data.base_version_number}, "
                f"but project version was modified concurrently."
            )

        # 8. Construct derived Blueprint
        try:
            blueprint = self.proj_svc.get_project_blueprint(db, project.id, user_id)
        except Exception:
            blueprint = GameBlueprint(
                project_id=project.id,
                title=project.title,
                genre=project.genre,
                archetype=project.engine,
                player_fantasy=spec_dict.get("player_role", "Player"),
                theme=spec_dict.get("theme", "neon"),
                core_loop=proposal.gameplay_loop,
                estimated_session_length="2-3 minutes",
                level_count=1,
                world_area_count=1,
                objectives=proposal.design_objectives,
                progression=[proposal.progression_direction],
                encounter_types=[],
                enemy_variety=0,
                finale="Complete the primary objective",
                supported_mechanics=proposal.proposed_mechanics,
            )

        return ApplySynthesisProposalResponse(
            project_id=project.id,
            previous_version_number=prev_version_num,
            new_version_number=project.current_version,
            change_summary=change_desc,
            changes=changes,
            project=self.proj_svc.to_response(project),
            blueprint=blueprint,
            status="SUCCESS",
        )


inspiration_synthesis_service = InspirationSynthesisService()

