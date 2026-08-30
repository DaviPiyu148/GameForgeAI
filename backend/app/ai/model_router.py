"""
Task-based Gemini model router.

Provides a canonical TaskType enum and resolve_model_chain() that returns the
ordered list of model IDs to try for a given task.  Model chains are configured
through environment variables; the defaults here use the current stable Gemini 3
family.

Rules:
- No service may independently hardcode model IDs.
- Legacy GEMINI_MODEL (if set) is treated as a compatibility override ONLY if no
  task-specific chain is configured for that task.  Task-specific chains always
  take precedence.
- All models in a chain must support:
    * OpenAI-compatible /chat/completions endpoint (response_format: json_object)
  If a model in the configured chain does not support this, remove it from the chain
  and document the decision.

Gemini 3 model IDs used here are the current stable identifiers as of 2026:
  gemini-3.7-flash, gemini-3.6-flash, gemini-3.5-flash, gemini-3.5-flash-lite, gemini-3.1-flash-lite

These are DEFAULT values only.  Override via GEMINI_*_MODELS env vars.
"""
from enum import Enum
from typing import List, Optional

from app.config import settings


class TaskType(str, Enum):
    """
    Canonical task type used by the failover executor to select the model chain.

    Every AI call site in game_generation_service.py must specify one of these.
    """
    GAME_GENERATION = "GAME_GENERATION"    # Full new game DSL generation
    REMIX = "REMIX"                        # Remix / mutation of existing DSL
    DSL_PATCH = "DSL_PATCH"              # Semantic repair / apply improvements / patch
    BLUEPRINT = "BLUEPRINT"              # Blueprint / concept expansion (future)
    PLAYTEST_ANALYSIS = "PLAYTEST_ANALYSIS"  # Playtest critique and recommendations
    DIRECTOR = "DIRECTOR"                # AI Director (future phase)


# ── Default model chains (Gemini 3 stable family) ────────────────────────────
# gemini-3.7-flash  — highest capability, medium thinking, suitable for complex generation
# gemini-3.6-flash  — balanced, reliable fallback
# gemini-3.5-flash  — lighter, good structured-output support
# gemini-3.5-flash-lite — lighter still, suitable for analysis/patch tasks
# gemini-3.1-flash-lite — final fallback for low-complexity tasks
#
# Per the spec: all models in every chain MUST support response_format=json_object.
# These Gemini 3 models expose the OpenAI-compatible endpoint and support structured output.

_DEFAULT_CHAINS: dict[TaskType, List[str]] = {
    TaskType.GAME_GENERATION: [
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
    ],
    TaskType.REMIX: [
        "gemini-3.6-flash",
        "gemini-3.7-flash",
        "gemini-3.5-flash",
    ],
    TaskType.DSL_PATCH: [
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
    ],
    TaskType.BLUEPRINT: [
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
    ],
    TaskType.PLAYTEST_ANALYSIS: [
        "gemini-3.5-flash-lite",
        "gemini-3.6-flash",
        "gemini-3.1-flash-lite",
    ],
    TaskType.DIRECTOR: [
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
    ],
}


def _parse_model_list(raw: Optional[str]) -> List[str]:
    """Parse a comma-separated model list from a config string."""
    if not raw:
        return []
    return [m.strip() for m in raw.split(",") if m.strip()]


def resolve_model_chain(task_type: TaskType) -> List[str]:
    """
    Return the ordered list of model IDs to try for the given task type.

    Priority:
    1. Task-specific GEMINI_*_MODELS env var (e.g. GEMINI_GENERATION_MODELS)
    2. Hardcoded per-task default chain (Gemini 3 stable family)
    3. Legacy GEMINI_MODEL env var (backward compat, only if chain is otherwise empty)

    The legacy GEMINI_MODEL does NOT override a configured task-specific chain.
    """
    # Map task type to the corresponding settings attribute
    task_attr_map: dict[TaskType, str] = {
        TaskType.GAME_GENERATION: "GEMINI_GENERATION_MODELS",
        TaskType.REMIX: "GEMINI_REMIX_MODELS",
        TaskType.DSL_PATCH: "GEMINI_DSL_PATCH_MODELS",
        TaskType.BLUEPRINT: "GEMINI_BLUEPRINT_MODELS",
        TaskType.PLAYTEST_ANALYSIS: "GEMINI_ANALYSIS_MODELS",
        TaskType.DIRECTOR: "GEMINI_DIRECTOR_MODELS",
    }

    attr = task_attr_map.get(task_type)
    if attr:
        env_chain = _parse_model_list(getattr(settings, attr, None))
        if env_chain:
            return env_chain

    # Use hardcoded default for this task
    default_chain = _DEFAULT_CHAINS.get(task_type, [])
    if default_chain:
        return list(default_chain)

    # Legacy GEMINI_MODEL fallback — only if nothing else is configured
    legacy = (getattr(settings, "GEMINI_MODEL", None) or "").strip()
    if legacy and legacy not in ("gemini-3-flash-preview",):
        # Suppress the old preview model from being used as a fallback chain entry
        return [legacy]

    # Absolute last resort — should never reach here if config is sane
    return ["gemini-3.6-flash", "gemini-3.5-flash"]
