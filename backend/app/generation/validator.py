import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from pydantic import ValidationError

from app.generation.dsl_models import GameDSL


@dataclass
class ValidationResult:
    """Machine-readable result of Game DSL validation."""
    is_valid: bool
    dsl: Optional[GameDSL] = None
    errors: List[str] = field(default_factory=list)
    raw_data: Optional[Dict[str, Any]] = None

    def get_error_summary(self) -> str:
        """Formatted bullet points of errors for repair prompts."""
        if not self.errors:
            return "No errors."
        return "\n".join(f"- {err}" for err in self.errors)


def validate_game_dsl(data: Union[str, Dict[str, Any]]) -> ValidationResult:
    """
    Validate candidate JSON or dictionary against GameDSL schema.
    
    Returns machine-readable ValidationResult suitable for bounded repair.
    """
    raw_dict: Dict[str, Any]
    if isinstance(data, str):
        try:
            raw_dict = json.loads(data)
        except json.JSONDecodeError as e:
            return ValidationResult(
                is_valid=False,
                errors=[f"Invalid JSON format: {str(e)}"],
                raw_data=None,
            )
    elif isinstance(data, dict):
        raw_dict = dict(data)
    else:
        return ValidationResult(
            is_valid=False,
            errors=[f"Expected dict or JSON string, received {type(data).__name__}"],
            raw_data=None,
        )

    # Safe deterministic structural pre-normalization
    normalized = dict(raw_dict)
    if "schema_version" not in normalized:
        normalized["schema_version"] = "2.0"

    # Normalize metadata
    if "metadata" not in normalized or not isinstance(normalized["metadata"], dict):
        normalized["metadata"] = {}
    else:
        normalized["metadata"] = dict(normalized["metadata"])

    for field_name in ("title", "genre", "description", "archetype"):
        if field_name in normalized and field_name not in normalized["metadata"]:
            normalized["metadata"][field_name] = normalized.pop(field_name)
        elif field_name in normalized:
            normalized.pop(field_name, None)

    # Normalize world.theme
    if "world" in normalized and isinstance(normalized["world"], dict):
        normalized["world"] = dict(normalized["world"])
        if "theme" in normalized and "theme" not in normalized["world"]:
            normalized["world"]["theme"] = normalized.pop("theme")
        elif "theme" in normalized:
            normalized.pop("theme", None)

    # Normalize rules and entities id
    if "rules" in normalized and isinstance(normalized["rules"], list):
        for idx, rule in enumerate(normalized["rules"]):
            if isinstance(rule, dict):
                if "id" not in rule:
                    rule["id"] = f"rule_{idx + 1}"
                if isinstance(rule.get("trigger"), dict):
                    trig_dict = rule["trigger"]
                    rule["trigger"] = trig_dict.get("type", "on_collide_enemy")
                if isinstance(rule.get("action"), dict):
                    act_dict = rule["action"]
                    rule["action"] = act_dict.get("type", "damage_player")
                    if "params" not in rule or not rule["params"]:
                        rule["params"] = {k: v for k, v in act_dict.items() if k != "type"}

    if "entities" in normalized and isinstance(normalized["entities"], list):
        for idx, ent in enumerate(normalized["entities"]):
            if isinstance(ent, dict) and "id" not in ent:
                ent["id"] = f"entity_{idx + 1}"

    try:
        validated_dsl = GameDSL.model_validate(normalized)
        return ValidationResult(
            is_valid=True,
            dsl=validated_dsl,
            errors=[],
            raw_data=normalized,
        )
    except ValidationError as exc:
        formatted_errors: List[str] = []
        for err in exc.errors():
            loc = " -> ".join(str(l) for l in err.get("loc", []))
            msg = err.get("msg", "Validation error")
            formatted_errors.append(f"Field '{loc}': {msg}")

        return ValidationResult(
            is_valid=False,
            dsl=None,
            errors=formatted_errors,
            raw_data=raw_dict,
        )
    except ValueError as val_err:
        return ValidationResult(
            is_valid=False,
            dsl=None,
            errors=[str(val_err)],
            raw_data=raw_dict,
        )
