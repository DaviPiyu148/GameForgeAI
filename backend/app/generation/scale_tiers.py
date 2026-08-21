"""
Phase 5: declarative structural budget table for generation "scale" tiers.

Each tier declares soft target ranges (min, max) for level count, entities per
level, and rules per level. These are deliberately kept strictly inside the
existing hard schema ceilings enforced by app.generation.dsl_models (GameDSL.levels
max_length=5, LevelDef.entities max_length=30, LevelDef.rules max_length=15) --
this module never raises those ceilings, it only narrows the AI's target window
within them and gives GameplayQualityValidator a floor to nudge toward.
"""
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class ScaleBudget:
    """Structural budget (min, max) ranges for a single generation scale tier."""
    scale: str
    level_count: Tuple[int, int]
    entities_per_level: Tuple[int, int]
    rules_per_level: Tuple[int, int]


_SCALE_BUDGETS: Dict[str, ScaleBudget] = {
    "prototype": ScaleBudget(
        scale="prototype",
        level_count=(1, 2),
        entities_per_level=(4, 8),
        rules_per_level=(2, 5),
    ),
    "standard": ScaleBudget(
        scale="standard",
        level_count=(2, 3),
        entities_per_level=(8, 14),
        rules_per_level=(3, 8),
    ),
    "campaign": ScaleBudget(
        scale="campaign",
        level_count=(3, 5),
        entities_per_level=(10, 20),
        rules_per_level=(4, 12),
    ),
}

_DEFAULT_SCALE = "standard"


def get_scale_budget(scale: str) -> ScaleBudget:
    """
    Look up the structural budget for a scale tier.

    Unknown/empty/None values fall back to the 'standard' tier rather than
    raising -- callers on the generation hot path (prompt building, validation)
    must never fail a build merely because an unrecognized scale string slipped
    through; 'standard' is a safe, reasonable default in that case.
    """
    key = (scale or _DEFAULT_SCALE).strip().lower()
    return _SCALE_BUDGETS.get(key, _SCALE_BUDGETS[_DEFAULT_SCALE])
