"""
Centralized Configuration for GameForge AI Game Generation Pipeline V2.

Contains all quality thresholds, score component weights, scale-tier expectations,
and structural bounds. Eliminates magic numbers from generation validators and evaluators.
"""

from typing import Any, Dict, List, Set, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# 1. Quality Scoring Weights (Sum = 100.0)
# ─────────────────────────────────────────────────────────────────────────────

WEIGHT_CORE_LOOP: float = 25.0
WEIGHT_OBJECTIVE_CLARITY: float = 15.0
WEIGHT_PROGRESSION: float = 15.0
WEIGHT_VARIETY: float = 15.0
WEIGHT_MECHANIC_COVERAGE: float = 15.0
WEIGHT_CROSS_SYSTEM: float = 10.0
WEIGHT_FINALE: float = 5.0


# ─────────────────────────────────────────────────────────────────────────────
# 2. Quality Evaluation Thresholds
# ─────────────────────────────────────────────────────────────────────────────

# Minimum overall score required for unconditional acceptance
THRESHOLD_ACCEPTABLE_PROTOTYPE: float = 60.0
THRESHOLD_ACCEPTABLE_STANDARD: float = 68.0
THRESHOLD_ACCEPTABLE_CAMPAIGN: float = 72.0

# Threshold below which a generation is flagged for warning vs repair
THRESHOLD_WARNING_FLOOR: float = 50.0
THRESHOLD_REPAIR_FLOOR: float = 35.0  # Scores below this with repairable issues trigger AI repair


# ─────────────────────────────────────────────────────────────────────────────
# 3. Scale-Aware Expectations
# ─────────────────────────────────────────────────────────────────────────────

SCALE_EXPECTATIONS: Dict[str, Dict[str, Any]] = {
    "prototype": {
        "min_levels": 1,
        "max_levels": 2,
        "min_entities_per_level": 4,
        "min_rules_per_level": 2,
        "require_escalation": False,
        "require_finale": False,
        "min_unique_objectives": 1,
        "min_distinct_behaviors": 1,
    },
    "standard": {
        "min_levels": 2,
        "max_levels": 3,
        "min_entities_per_level": 6,
        "min_rules_per_level": 3,
        "require_escalation": True,
        "require_finale": True,
        "min_unique_objectives": 1,
        "min_distinct_behaviors": 2,
    },
    "campaign": {
        "min_levels": 3,
        "max_levels": 5,
        "min_entities_per_level": 8,
        "min_rules_per_level": 4,
        "require_escalation": True,
        "require_finale": True,
        "min_unique_objectives": 2,
        "min_distinct_behaviors": 3,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# 4. Standard Quality Failure Codes
# ─────────────────────────────────────────────────────────────────────────────

class QualityFailureCode:
    MISSING_CORE_LOOP = "MISSING_CORE_LOOP"
    MISSING_OBJECTIVE = "MISSING_OBJECTIVE"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    INSUFFICIENT_LEVEL_DEPTH = "INSUFFICIENT_LEVEL_DEPTH"
    LOW_SYSTEM_COVERAGE = "LOW_SYSTEM_COVERAGE"
    INVALID_WIN_CONDITION = "INVALID_WIN_CONDITION"
    INVALID_FAIL_CONDITION = "INVALID_FAIL_CONDITION"
    INVALID_REFERENCE = "INVALID_REFERENCE"
    LOW_VARIETY = "LOW_VARIETY"
    INSUFFICIENT_PROGRESSION = "INSUFFICIENT_PROGRESSION"
    UNSAFE_DSL = "UNSAFE_DSL"
    REPEATED_ADJACENT_OBJECTIVES = "REPEATED_ADJACENT_OBJECTIVES"
    DISCONNECTED_SYSTEMS = "DISCONNECTED_SYSTEMS"
    DEAD_RULE_DETECTED = "DEAD_RULE_DETECTED"
    PASSIVE_SYSTEM_DETECTED = "PASSIVE_SYSTEM_DETECTED"
    GAMEPLAY_DEADLOCK_DETECTED = "GAMEPLAY_DEADLOCK_DETECTED"
    WEAK_GAMEPLAY_LOOP = "WEAK_GAMEPLAY_LOOP"
    OTHER = "OTHER"





# ─────────────────────────────────────────────────────────────────────────────
# 5. Compiler Progress Stages (Exactly 10 Deterministic Stages)
# ─────────────────────────────────────────────────────────────────────────────

COMPILER_STAGES: List[Tuple[str, str]] = [
    ("SYS", "Understanding game request"),
    ("AI", "Building game design"),
    ("AI", "Mapping runtime capabilities"),
    ("AI", "Generating GameDSL"),
    ("VALIDATION", "Schema validation"),
    ("VALIDATION", "Gameplay quality"),
    ("REPAIR", "Deterministic normalization/repair"),
    ("PHASER", "Runtime compilation"),
    ("PHASER", "Runtime verification"),
    ("SYS", "Build complete"),
]
COMPILER_STAGES_V2 = COMPILER_STAGES

