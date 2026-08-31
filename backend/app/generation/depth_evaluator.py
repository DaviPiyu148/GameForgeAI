"""
Deterministic Game Depth & Quality Evaluator (Pipeline V2).

Produces structured GenerationQualityReport evaluating:
1. Core loop completeness (Action -> Feedback -> Challenge -> Reward -> Objective -> Fail condition)
2. Objective clarity & diversity across levels
3. Campaign progression & level differentiation
4. Scale-aware quality scoring (Prototype vs Standard vs Campaign)
5. Requirement coverage & cross-system interactions
6. Bounded finale quality
"""

from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Optional, Set, Tuple

from app.generation.dsl_models import GameDSL
from app.generation.generation_config import (
    SCALE_EXPECTATIONS,
    THRESHOLD_ACCEPTABLE_CAMPAIGN,
    THRESHOLD_ACCEPTABLE_PROTOTYPE,
    THRESHOLD_ACCEPTABLE_STANDARD,
    THRESHOLD_REPAIR_FLOOR,
    THRESHOLD_WARNING_FLOOR,
    WEIGHT_CORE_LOOP,
    WEIGHT_CROSS_SYSTEM,
    WEIGHT_FINALE,
    WEIGHT_MECHANIC_COVERAGE,
    WEIGHT_OBJECTIVE_CLARITY,
    WEIGHT_PROGRESSION,
    WEIGHT_VARIETY,
    QualityFailureCode,
)
from app.generation.generation_contract import GameGenerationContract, RequirementConfidence
from app.generation.requirement_coverage import (
    CrossSystemInteraction,
    RequirementCoverageMatrix,
    RequirementStatus,
)


@dataclass
class GenerationQualityReport:
    """Deterministic structural and design health report for generated GameDSL."""
    score: int  # Overall scale-aware score (0 to 100)
    scale: str
    archetype: str
    is_acceptable: bool
    needs_repair: bool
    core_loop_score: float
    objective_score: float
    progression_score: float
    variety_score: float
    mechanic_coverage_score: float
    cross_system_score: float
    finale_score: float
    requirement_statuses: List[RequirementStatus] = field(default_factory=list)
    cross_system_interactions: List[CrossSystemInteraction] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    failure_codes: List[str] = field(default_factory=list)
    missing_requirements: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "scale": self.scale,
            "archetype": self.archetype,
            "is_acceptable": self.is_acceptable,
            "needs_repair": self.needs_repair,
            "subscores": {
                "core_loop": round(self.core_loop_score, 1),
                "objective": round(self.objective_score, 1),
                "progression": round(self.progression_score, 1),
                "variety": round(self.variety_score, 1),
                "mechanic_coverage": round(self.mechanic_coverage_score, 1),
                "cross_system": round(self.cross_system_score, 1),
                "finale": round(self.finale_score, 1),
            },
            "warnings": self.warnings,
            "failure_codes": self.failure_codes,
            "missing_requirements": self.missing_requirements,
        }


class GameDepthEvaluator:
    """Deterministic quality and depth evaluator for GameDSL."""

    @classmethod
    def evaluate(
        cls,
        dsl: GameDSL,
        contract: GameGenerationContract,
    ) -> GenerationQualityReport:
        scale = contract.scale.lower()
        archetype = dsl.metadata.archetype.lower()
        scale_cfg = SCALE_EXPECTATIONS.get(scale, SCALE_EXPECTATIONS["standard"])

        warnings: List[str] = []
        failure_codes: List[str] = []

        all_entities = list(dsl.entities) + [e for lvl in dsl.levels for e in lvl.entities]
        all_rules = list(dsl.rules) + [r for lvl in dsl.levels for r in lvl.rules]
        levels = dsl.levels if dsl.levels else []

        # ─────────────────────────────────────────────────────────────────────
        # 1. Core Loop Completeness Score (0 - 100)
        # ─────────────────────────────────────────────────────────────────────
        core_loop_score = 0.0

        # Action: Player can move and has abilities
        has_action = dsl.player.speed > 0 and (dsl.player.attack_type != "none" or dsl.player.dash_speed > 0 or dsl.player.jump_power > 0)
        if has_action:
            core_loop_score += 20.0

        # Challenge: Enemies or Hazards exist
        has_challenge = any(e.type in ("enemy", "hazard") for e in all_entities) or dsl.world.wave_count > 1
        if has_challenge:
            core_loop_score += 20.0
        else:
            if archetype in ("survival", "shooter", "arena"):
                failure_codes.append(QualityFailureCode.MISSING_CORE_LOOP)
                warnings.append(f"{archetype.capitalize()} game lacks challenge: 0 enemies or hazards present.")

        # Reward / Feedback: Collectibles or Score rules
        has_reward = any(e.type == "collectible" for e in all_entities) or any(r.action == "add_score" for r in all_rules)
        if has_reward:
            core_loop_score += 20.0

        # Objective: Level has clear objective or rule with win_game
        has_win_rule = any(r.action == "win_game" for r in all_rules)
        has_level_objs = any(getattr(lvl, "objective", None) is not None for lvl in levels)
        if has_win_rule or has_level_objs or dsl.open_world is not None:
            core_loop_score += 20.0
        else:
            warnings.append("No explicit win_game rule or level objective defined.")
            if scale != "prototype":
                failure_codes.append(QualityFailureCode.MISSING_OBJECTIVE)

        # Fail Condition: Player takes damage / can lose
        has_fail_rule = any(r.action in ("lose_game", "damage_player") for r in all_rules) or any(e.damage > 0 for e in all_entities if e.type == "enemy")
        if has_fail_rule:
            core_loop_score += 20.0
        else:
            warnings.append("No reachable fail or damage conditions detected.")
            failure_codes.append(QualityFailureCode.INVALID_FAIL_CONDITION)

        # ─────────────────────────────────────────────────────────────────────
        # 2. Objective Clarity & Diversity Score (0 - 100)
        # ─────────────────────────────────────────────────────────────────────
        objective_score = 0.0
        if has_win_rule or dsl.open_world is not None:
            objective_score += 40.0

        # Measure diversity across multi-level games
        unique_objs: Set[str] = set()
        level_obj_list: List[str] = []
        for lvl in levels:
            if getattr(lvl, "objective", None):
                unique_objs.add(lvl.objective.type)
                level_obj_list.append(lvl.objective.type)

        if scale == "prototype":
            objective_score += 60.0  # Prototypes don't need multiple objective types
        else:
            has_adjacent_repeats = False
            if len(level_obj_list) >= 2:
                for i in range(len(level_obj_list) - 1):
                    if level_obj_list[i] == level_obj_list[i+1]:
                        has_adjacent_repeats = True
                        break

            if len(unique_objs) >= scale_cfg["min_unique_objectives"] and not has_adjacent_repeats:
                objective_score += 60.0
            elif has_adjacent_repeats and scale == "campaign":
                objective_score += 25.0
                warnings.append("Repeated adjacent objective: Consecutive levels share identical objective structures.")
                failure_codes.append(QualityFailureCode.REPEATED_ADJACENT_OBJECTIVES)
            elif len(levels) > 1 and len(unique_objs) <= 1:
                objective_score += 20.0
                warnings.append(f"Repeated objective: All levels share identical objective type '{list(unique_objs)[0] if unique_objs else 'default'}'.")
                if scale == "campaign":
                    failure_codes.append(QualityFailureCode.LOW_VARIETY)
            else:
                objective_score += 40.0


        # ─────────────────────────────────────────────────────────────────────
        # 3. Progression & Escalation Score (0 - 100)
        # ─────────────────────────────────────────────────────────────────────
        progression_score = 0.0
        if scale == "prototype":
            # Prototypes are judged simply on loop existence, not multi-level escalation
            progression_score = 90.0 if core_loop_score >= 80.0 else 60.0
        else:
            if len(levels) < scale_cfg["min_levels"]:
                progression_score = 25.0
                warnings.append(f"Insufficient scale: Requested '{scale}' with target {scale_cfg['min_levels']}+ levels, but only {len(levels)} generated.")
                failure_codes.append(QualityFailureCode.INSUFFICIENT_LEVEL_DEPTH)
            else:
                progression_score += 40.0
                # Check level-over-level variation in entity counts or speed
                escalates = False
                if len(levels) >= 2:
                    ent_counts = [len(lvl.entities) for lvl in levels]
                    if ent_counts[-1] >= ent_counts[0]:
                        escalates = True
                if escalates or dsl.world.wave_count > 1:
                    progression_score += 40.0
                else:
                    warnings.append("Levels lack progression: Enemy counts/hazards do not escalate across levels.")
                    if scale == "campaign":
                        failure_codes.append(QualityFailureCode.INSUFFICIENT_PROGRESSION)

                # Introduction -> Climax progression marker
                has_finale_marker = any(getattr(lvl, "is_finale", False) for lvl in levels)
                if has_finale_marker:
                    progression_score += 20.0

        # ─────────────────────────────────────────────────────────────────────
        # 4. Content Variety Score (0 - 100)
        # ─────────────────────────────────────────────────────────────────────
        variety_score = 0.0
        distinct_behaviors = {e.behavior for e in all_entities if e.type == "enemy"}
        if len(distinct_behaviors) >= scale_cfg["min_distinct_behaviors"]:
            variety_score += 50.0
        else:
            variety_score += max(20.0, len(distinct_behaviors) * 20.0)
            if scale == "campaign" and len(distinct_behaviors) < 2:
                warnings.append("Low enemy variety: All enemies share a single behavioral AI pattern.")
                failure_codes.append(QualityFailureCode.LOW_VARIETY)

        # Level visual & layout differentiation
        if len(levels) <= 1:
            variety_score += 50.0
        else:
            unique_themes = {getattr(getattr(lvl, "world", None), "theme", None) for lvl in levels}
            unique_bg = {getattr(getattr(lvl, "world", None), "background_color", None) for lvl in levels}
            if len(unique_themes) > 1 or len(unique_bg) > 1:
                variety_score += 50.0
            else:
                variety_score += 25.0
                warnings.append("Levels share identical themes and visual background colors.")

        # ─────────────────────────────────────────────────────────────────────
        # 5. Requirement Coverage & Cross-System Score (0 - 100)
        # ─────────────────────────────────────────────────────────────────────
        statuses, interactions = RequirementCoverageMatrix.evaluate(contract, dsl)
        
        passed_reqs = sum(1 for s in statuses if s.status == "PASS")
        total_reqs = max(1, len(statuses))
        mechanic_coverage_score = (passed_reqs / total_reqs) * 100.0

        missing_requirements = [s.name for s in statuses if s.status in ("FAIL", "UNSUPPORTED")]
        if any(s.status == "UNSUPPORTED" for s in statuses):
            failure_codes.append(QualityFailureCode.UNSUPPORTED_CAPABILITY)
            warnings.append(f"Unsupported capabilities requested: {', '.join(missing_requirements)}.")

        if any(s.status == "FAIL" and s.confidence == RequirementConfidence.EXPLICIT_REQUIREMENT for s in statuses):
            failure_codes.append(QualityFailureCode.LOW_SYSTEM_COVERAGE)
            warnings.append(f"Explicit requirements missing from DSL: {', '.join(missing_requirements)}.")

        # Cross-System score
        verified_interactions = sum(1 for i in interactions if i.verified)
        if len(interactions) == 0:
            # Linear games without open world don't heavily mandate multiple systems
            cross_system_score = 90.0 if scale == "prototype" else 75.0
        else:
            cross_system_score = (verified_interactions / len(interactions)) * 100.0
            if cross_system_score < 50.0:
                warnings.append("Requested systems co-exist but lack meaningful gameplay relationships (e.g. Threat not linked to Activities).")
                failure_codes.append(QualityFailureCode.PASSIVE_SYSTEM_DETECTED)

        # Audit dead rules
        dead_rules = RequirementCoverageMatrix.audit_rule_liveness(dsl)
        dead_rule_penalty = 0.0
        if dead_rules:
            dead_rule_penalty = min(25.0, len(dead_rules) * 10.0)
            failure_codes.append(QualityFailureCode.DEAD_RULE_DETECTED)
            for r_id, r_reason in dead_rules:
                warnings.append(f"Dead rule detected: rule '{r_id}' ({r_reason}).")


        # ─────────────────────────────────────────────────────────────────────
        # 6. Finale Quality Score (0 - 100)
        # ─────────────────────────────────────────────────────────────────────
        finale_score = 0.0
        has_boss = any(getattr(e, "is_boss", False) for e in all_entities)
        has_finale_lvl = any(getattr(lvl, "is_finale", False) for lvl in levels)

        if scale == "prototype":
            finale_score = 100.0  # Not required for prototype scale
        else:
            if has_boss or has_finale_lvl:
                finale_score = 100.0
            else:
                finale_score = 30.0
                if scale == "campaign":
                    warnings.append("Campaign scale lacks a climax or designated finale level.")

        # ─────────────────────────────────────────────────────────────────────
        # 7. Total Scale-Aware Weighted Score
        # ─────────────────────────────────────────────────────────────────────
        raw_score = ((
            (core_loop_score * WEIGHT_CORE_LOOP) +
            (objective_score * WEIGHT_OBJECTIVE_CLARITY) +
            (progression_score * WEIGHT_PROGRESSION) +
            (variety_score * WEIGHT_VARIETY) +
            (mechanic_coverage_score * WEIGHT_MECHANIC_COVERAGE) +
            (cross_system_score * WEIGHT_CROSS_SYSTEM) +
            (finale_score * WEIGHT_FINALE)
        ) / 100.0) - dead_rule_penalty

        overall_score = int(math.floor(max(0.0, min(100.0, raw_score))))


        # Determine acceptability based on scale threshold
        threshold = THRESHOLD_ACCEPTABLE_PROTOTYPE if scale == "prototype" else (
            THRESHOLD_ACCEPTABLE_STANDARD if scale == "standard" else THRESHOLD_ACCEPTABLE_CAMPAIGN
        )

        is_acceptable = overall_score >= threshold and not any(
            code in (QualityFailureCode.MISSING_CORE_LOOP, QualityFailureCode.UNSUPPORTED_CAPABILITY)
            for code in failure_codes
        )

        needs_repair = (
            not is_acceptable and
            overall_score >= THRESHOLD_REPAIR_FLOOR and
            QualityFailureCode.UNSAFE_DSL not in failure_codes
        )

        return GenerationQualityReport(
            score=overall_score,
            scale=scale,
            archetype=archetype,
            is_acceptable=is_acceptable,
            needs_repair=needs_repair,
            core_loop_score=core_loop_score,
            objective_score=objective_score,
            progression_score=progression_score,
            variety_score=variety_score,
            mechanic_coverage_score=mechanic_coverage_score,
            cross_system_score=cross_system_score,
            finale_score=finale_score,
            requirement_statuses=statuses,
            cross_system_interactions=interactions,
            warnings=warnings,
            failure_codes=failure_codes,
            missing_requirements=missing_requirements,
        )
