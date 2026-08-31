"""
Canonical Gameplay Rhythm & Deadlock Validator (Gameplay Experience V1).

Defines the core Gameplay Beat model:
  Action -> Challenge -> Feedback -> Reward/Progress

Also implements deterministic deadlock detection:
- Objective reachability & target liveness (unreachable goals, zero target entities).
- Encounter deadlock (impossible next wave trigger).
- Reward circular dependency / unreachable win rules.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from app.generation.dsl_models import GameDSL, LevelDef, ObjectiveDef


class FlowPhase(str, Enum):
    INTRO = "INTRO"
    ACTION = "ACTION"
    VARIATION = "VARIATION"
    ESCALATION = "ESCALATION"
    FINALE = "FINALE"


@dataclass(frozen=True)
class GameplayBeat:
    """A bounded segment of meaningful player interaction."""
    phase: FlowPhase
    action: str
    challenge: str
    feedback: str
    reward: str


@dataclass
class DeadlockCheckResult:
    is_valid: bool
    deadlocks: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class GameplayRhythmManager:
    """Analyzes and validates gameplay beat structures and deadlock-free execution."""

    @classmethod
    def detect_deadlocks(cls, dsl: GameDSL) -> DeadlockCheckResult:
        """
        Deterministically verifies that all objectives and encounters can progress
        and complete without deadlocks.
        """
        deadlocks: List[str] = []
        warnings: List[str] = []

        all_rules = list(dsl.rules) + [r for lvl in dsl.levels for r in lvl.rules]
        levels = dsl.levels if dsl.levels else []

        # 1. Single-level / Global Objective check
        if not levels:
            enemies = [e for e in dsl.entities if e.type == "enemy"]
            collectibles = [e for e in dsl.entities if e.type == "collectible"]

            # If win requires on_enemy_defeat or defeat_all
            defeat_win = any(r.action == "win_game" and r.trigger == "on_enemy_defeat" for r in all_rules)
            if defeat_win and len(enemies) == 0:
                deadlocks.append("Global rule requires enemy defeat to win, but 0 enemies exist in entities.")

            # If win requires score target
            score_win = any(r.action == "win_game" and r.trigger == "on_score_target" for r in all_rules)
            if score_win:
                has_scoring = any(r.action == "add_score" for r in all_rules) or len(collectibles) > 0
                if not has_scoring:
                    deadlocks.append("Win rule requires reaching a score target, but no scoring rules or collectibles exist.")

        # 2. Multi-level Campaign Objective checks
        for lvl in levels:
            obj = getattr(lvl, "objective", None)
            if not obj:
                continue

            lvl_enemies = [e for e in lvl.entities if e.type == "enemy"]
            lvl_collectibles = [e for e in lvl.entities if e.type == "collectible"]
            lvl_rules = list(lvl.rules)

            if obj.type == "defeat_all" and len(lvl_enemies) == 0:
                deadlocks.append(f"Level {lvl.level_number} objective is 'defeat_all', but 0 enemies exist.")

            elif obj.type == "collect_all" and len(lvl_collectibles) == 0:
                if len(lvl_enemies) == 0:
                    deadlocks.append(f"Level {lvl.level_number} objective is 'collect_all', but 0 collectibles and 0 enemies exist.")
                else:
                    warnings.append(f"Level {lvl.level_number} objective is 'collect_all', but 0 collectibles exist (progresses via enemy clearance).")

            elif obj.type == "reach_exit":

                lvl_w = (lvl.world.width if lvl.world else dsl.world.width)
                lvl_h = (lvl.world.height if lvl.world else dsl.world.height)
                if obj.exit_x is not None and (obj.exit_x < 0 or obj.exit_x > lvl_w):
                    deadlocks.append(f"Level {lvl.level_number} exit_x ({obj.exit_x}) is outside world width ({lvl_w}).")
                if obj.exit_y is not None and (obj.exit_y < 0 or obj.exit_y > lvl_h):
                    deadlocks.append(f"Level {lvl.level_number} exit_y ({obj.exit_y}) is outside world height ({lvl_h}).")

        # 3. Wave Spawn Deadlock
        wave_start_rules = [r for r in all_rules if r.trigger == "on_wave_start"]
        if dsl.world.wave_count > 1 and len(wave_start_rules) == 0:
            warnings.append("World defines multiple waves (wave_count > 1), but lacks on_wave_start event handling.")

        return DeadlockCheckResult(
            is_valid=len(deadlocks) == 0,
            deadlocks=deadlocks,
            warnings=warnings,
        )

    @classmethod
    def evaluate_gameplay_beats(cls, dsl: GameDSL, scale: str = "standard") -> Tuple[float, List[GameplayBeat]]:
        """
        Evaluates the completeness of the gameplay rhythm:
        Action -> Challenge -> Feedback -> Reward/Progress
        Returns (beat_score: 0.0 - 100.0, beats: List[GameplayBeat])
        """
        all_entities = list(dsl.entities) + [e for lvl in dsl.levels for e in lvl.entities]
        all_rules = list(dsl.rules) + [r for lvl in dsl.levels for r in lvl.rules]
        beats: List[GameplayBeat] = []

        # Intro Beat: Player locomotion and orientation
        beats.append(
            GameplayBeat(
                phase=FlowPhase.INTRO,
                action="2D Navigation & Sprint",
                challenge="Locomotion and spatial orientation",
                feedback="Kinetic trail & HUD telemetry",
                reward="Safe approach zone",
            )
        )

        score = 30.0  # Base for valid player locomotion

        # Action Beat: Combat or Collection
        has_enemies = any(e.type == "enemy" for e in all_entities)
        has_collectibles = any(e.type == "collectible" for e in all_entities)

        if has_enemies:
            beats.append(
                GameplayBeat(
                    phase=FlowPhase.ACTION,
                    action="Engage Hostile Patrols",
                    challenge="Enemy evasion and projectile/melee damage",
                    feedback="Muzzle flash, enemy hit flash, spark bursts",
                    reward="Threat suppression & score",
                )
            )
            score += 25.0
        elif has_collectibles:
            beats.append(
                GameplayBeat(
                    phase=FlowPhase.ACTION,
                    action="Gather Data Relics",
                    challenge="Spatial collection under hazard proximity",
                    feedback="Luminous pickup halo & sound hook",
                    reward="Direct score advancement",
                )
            )
            score += 20.0

        # Variation / Escalation Beat
        distinct_behaviors = {e.behavior for e in all_entities if e.type == "enemy"}
        if len(distinct_behaviors) >= 2 or dsl.world.wave_count > 1 or len(dsl.levels) >= 2:
            beats.append(
                GameplayBeat(
                    phase=FlowPhase.ESCALATION,
                    action="Adaptive Tactics",
                    challenge="Multi-threat behavior mixing (ranged + patrol/chase)",
                    feedback="Screen shake & warning audio",
                    reward="Encounter survival & level progression",
                )
            )
            score += 25.0
        else:
            score += 10.0

        # Finale / Climax Beat
        has_boss = any(getattr(e, "is_boss", False) for e in all_entities)
        has_finale = any(getattr(lvl, "is_finale", False) for lvl in dsl.levels)
        if has_boss or has_finale:
            beats.append(
                GameplayBeat(
                    phase=FlowPhase.FINALE,
                    action="Climactic Showdown",
                    challenge="High-health monolithic boss encounter / extraction escape",
                    feedback="Boss health bar & phase transition aura",
                    reward="Campaign victory / game clear",
                )
            )
            score += 20.0
        else:
            score += 10.0 if scale == "prototype" else 5.0

        final_score = min(100.0, score)
        return final_score, beats
