"""
Deterministic Normalization and Sanitization Layer for GameForge AI Game DSL.

Converts raw AI output into a canonical candidate DSL dictionary BEFORE strict
Pydantic validation. Resolves recoverable schema drift, legacy aliases, and safe
type coercion locally, eliminating expensive provider repair calls for harmless
formatting variations, while preserving the strict closed-world safety boundary.
"""

from dataclasses import dataclass, field
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from app.schemas.design_spec import HEX_COLOR_REGEX, check_for_script_injection

# ─────────────────────────────────────────────────────────────────────────────
# 1. Structured Validation Issue Model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ValidationIssue:
    """Structured representation of a schema anomaly or validation problem."""
    path: List[Union[str, int]]
    issue_type: str  # UNKNOWN_FIELD, WRONG_TYPE, MALFORMED_JSON, UNSAFE_FIELD, MISSING_REQUIRED, INVALID_ENUM
    message: str
    severity: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    repairability: str = "DETERMINISTIC"  # DETERMINISTIC, SEMANTIC, UNSAFE, UNREPAIRABLE

    @property
    def path_str(self) -> str:
        return " -> ".join(str(p) for p in self.path) if self.path else "root"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Known Safe Fields & Legacy Alias Registry
# ─────────────────────────────────────────────────────────────────────────────

# Explicitly known non-runtime / obsolete fields that can be safely discarded
# without compromising game simulation logic.
KNOWN_SAFE_FIELDS_BY_MODEL: Dict[str, Set[str]] = {
    "LevelDef": {
        "width", "height", "gravity", "background_color", "hazard_density",
        "wave_count", "procedural_seed", "level_id", "id", "stage_number",
        "stage", "name", "stage_id", "difficulty_scaling", "world_mode",
        "grid_size", "tile_size", "density",
    },
    "WorldDef": {
        "density", "grid_size", "tile_size", "ambient_light", "seed",
        "mode", "name", "id", "world_id", "friction",
    },
    "PlayerDef": {
        "x", "y", "health", "lives", "score", "jump", "radius", "invulnerable",
        "role", "class", "avatar", "size",
    },
    "EntityDef": {
        "score", "val", "cost", "pos_x", "pos_y", "size", "tags",
        "category", "target", "ai", "state", "name", "label", "layer",
    },
    "RuleDef": {
        "event", "handler", "condition", "callback", "name", "description",
        "enabled", "priority",
    },
    "UIDef": {
        "score", "health", "hud", "title", "show_hud", "theme",
    },
    "ObjectiveDef": {
        "goal", "target", "count", "time", "id", "name", "title",
    },
    "RegionDef": {
        "width_tiles", "height_tiles", "seed", "population", "zone_type",
        "district_id", "map_icon", "is_unlocked",
    },
    "POIDef": {
        "label", "title", "radius", "tags", "category", "zone",
    },
    "VehicleDef": {
        "gear_count", "fuel", "acceleration_curve", "seats", "weight", "engine",
    },
    "ActorDef": {
        "label", "title", "role", "voice", "npc_type", "faction", "zone",
    },
    "FactionDef": {
        "leader", "headquarters", "motto", "banner", "tier",
    },
    "ThreatSystemDef": {
        "alarm_sound", "hud_color", "visual_cue", "siren",
    },
    "WorldTimeDef": {
        "clock_speed", "sun_angle", "format",
    },
    "WorldEventDef": {
        "cooldown", "spawn_rate", "banner", "frequency",
    },
    "GameMetadata": {
        "version", "author", "created_at", "tags", "platform",
    },
}

# Unsafe field names that MUST NEVER be silently dropped or accepted
UNSAFE_FIELD_NAMES = {
    "script", "runtime_script", "javascript", "eval", "exec",
    "shell", "callback_code", "callback", "function", "onclick", "onload",
    "payload", "cmd", "system", "child_process", "code", "handler_code",
    "custom_script", "run_script", "socket", "xhr", "fetch",
    "__proto__", "constructor", "prototype",
}

UNSAFE_STRING_PATTERNS = [
    r"<script\b", r"javascript:", r"\beval\(", r"\bexec\(", r"__import__",
    r"subprocess\.", r"window\.", r"document\.", r"\.innerHTML",
    r"fetch\(", r"http://", r"https://", r"file://", r"data:",
]


# ─────────────────────────────────────────────────────────────────────────────
# 3. DSL Normalizer Class
# ─────────────────────────────────────────────────────────────────────────────

class DSLNormalizer:
    """
    Deterministic normalization engine for AI-generated Game DSL payloads.
    """

    @classmethod
    def clean_json_text(cls, raw: str) -> str:
        """Strip reasoning tags, markdown fences, and isolated prose."""
        cleaned = raw.strip()
        # 1. Remove reasoning / think tags
        cleaned = re.sub(r"<(?:thought|think)>.*?</(?:thought|think)>", "", cleaned, flags=re.DOTALL | re.IGNORECASE).strip()
        # 2. Strip markdown codeblocks
        if "```" in cleaned:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
            if match:
                cleaned = match.group(1).strip()
            else:
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(r"\s*```$", "", cleaned).strip()
        # 3. Extract outermost balanced JSON object if surrounded by prose
        if not (cleaned.startswith("{") and cleaned.endswith("}")):
            first_brace = cleaned.find("{")
            last_brace = cleaned.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                cleaned = cleaned[first_brace : last_brace + 1]
        return cleaned.strip()

    @classmethod
    def check_for_unsafe_content(cls, data: Any, path: List[Union[str, int]]) -> Optional[ValidationIssue]:
        """Deep scan for dangerous code execution strings or unsafe field names."""
        if isinstance(data, dict):
            for k, v in data.items():
                k_str = str(k).lower().strip()
                if k_str in UNSAFE_FIELD_NAMES:
                    return ValidationIssue(
                        path=path + [k],
                        issue_type="UNSAFE_FIELD",
                        message=f"Disallowed unsafe field name detected: '{k}'",
                        severity="CRITICAL",
                        repairability="UNSAFE",
                    )
                issue = cls.check_for_unsafe_content(v, path + [k])
                if issue:
                    return issue
        elif isinstance(data, list):
            for idx, item in enumerate(data):
                issue = cls.check_for_unsafe_content(item, path + [idx])
                if issue:
                    return issue
        elif isinstance(data, str):
            for pattern in UNSAFE_STRING_PATTERNS:
                if re.search(pattern, data, re.IGNORECASE):
                    return ValidationIssue(
                        path=path,
                        issue_type="UNSAFE_CONTENT",
                        message=f"Prohibited script or executable code pattern detected in field: '{data[:50]}'",
                        severity="CRITICAL",
                        repairability="UNSAFE",
                    )
        return None

    @classmethod
    def coerce_int(cls, val: Any, default: Optional[int] = None, *args, **kwargs) -> Any:
        """Safely parse numeric strings or floats to int without clamping out-of-bounds numbers."""
        if val is None:
            return default
        if isinstance(val, bool):
            return int(val)
        if isinstance(val, int):
            return val
        if isinstance(val, float):
            return int(val)
        if isinstance(val, str):
            s = val.strip()
            try:
                f_val = float(s)
                return int(f_val)
            except (ValueError, TypeError):
                return val
        return val

    @classmethod
    def coerce_float(cls, val: Any, default: Optional[float] = None, *args, **kwargs) -> Any:
        """Safely parse numeric strings to float without clamping out-of-bounds numbers."""
        if val is None:
            return default
        if isinstance(val, bool):
            return float(val)
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            try:
                return float(val.strip())
            except (ValueError, TypeError):
                return val
        return val

    @classmethod
    def coerce_bool(cls, val: Any, default: bool) -> bool:
        """Safely coerce booleans or string booleans."""
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, str):
            low = val.strip().lower()
            if low in ("true", "1", "yes", "on"):
                return True
            if low in ("false", "0", "no", "off"):
                return False
        return default

    @classmethod
    def coerce_hex_color(cls, val: Any, default: Optional[str] = None) -> Any:
        """Add leading '#' to bare 6-char hex strings while leaving other strings for Pydantic regex validation."""
        if val is None:
            return default
        if not isinstance(val, str):
            return val
        s = val.strip()
        if not s.startswith("#") and re.match(r"^[0-9a-fA-F]{6}$", s):
            return f"#{s}"
        return val

    @classmethod
    def normalize_metadata(cls, raw: Dict[str, Any], issues: List[ValidationIssue]) -> Optional[Dict[str, Any]]:
        """Normalize game metadata section."""
        if "metadata" not in raw and not any(f in raw for f in ("title", "genre", "description", "archetype")):
            return None

        meta = dict(raw.get("metadata") or {})
        # Flatten top-level metadata fields if mistakenly placed in root
        for f in ("title", "genre", "description", "archetype"):
            if f in raw and f not in meta:
                meta[f] = raw.pop(f)
                issues.append(ValidationIssue(
                    path=["metadata", f],
                    issue_type="MIGRATED_ROOT_FIELD",
                    message=f"Migrated root '{f}' into metadata.{f}",
                ))

        meta["title"] = str(meta.get("title") or "Game Prototype").strip()[:100]
        meta["genre"] = str(meta.get("genre") or "Action").strip()[:50]
        meta["description"] = str(meta.get("description") or "A playable prototype.").strip()[:500]

        if "archetype" in meta and meta["archetype"] is not None:
            arch = str(meta["archetype"]).lower().strip()
            # Canonical aliases
            arch_alias = {
                "dungeon_crawler": "dungeon",
                "space_shooter": "shooter",
                "boss_rush": "survival",
                "action": "survival",
                "arcade": "survival",
            }
            if arch in arch_alias:
                meta["archetype"] = arch_alias[arch]
            else:
                meta["archetype"] = arch

        return meta

    @classmethod
    def normalize_world(cls, raw: Dict[str, Any], issues: List[ValidationIssue]) -> Optional[Dict[str, Any]]:
        """Normalize WorldDef dictionary."""
        if "world" not in raw and "theme" not in raw:
            return None

        w = dict(raw.get("world") or {})
        # Pull top-level theme if present
        if "theme" in raw and "theme" not in w:
            w["theme"] = raw.pop("theme")

        # Strip / drop safe unknown fields
        safe_drop = KNOWN_SAFE_FIELDS_BY_MODEL["WorldDef"]
        for k in list(w.keys()):
            if k in safe_drop:
                w.pop(k)
                issues.append(ValidationIssue(
                    path=["world", k],
                    issue_type="UNKNOWN_FIELD",
                    message=f"Stripped safe non-schema field 'world.{k}'",
                ))

        if "width" in w:
            w["width"] = cls.coerce_int(w["width"])
        if "height" in w:
            w["height"] = cls.coerce_int(w["height"])
        if "gravity" in w:
            w["gravity"] = cls.coerce_int(w["gravity"])
        if "background_color" in w:
            w["background_color"] = cls.coerce_hex_color(w["background_color"])

        valid_world_themes = {"cyberpunk", "retro_arcade", "dungeon", "space", "neon", "minimal", "wasteland", "urban", "colony", "fantasy"}
        if "theme" in w and w["theme"] is not None:
            theme = str(w["theme"]).lower().strip()
            theme_alias = {
                "cyber": "cyberpunk",
                "scifi": "space",
                "sci_fi": "space",
                "retro": "retro_arcade",
                "pixel": "retro_arcade",
                "dark": "dungeon",
                "cave": "dungeon",
            }
            if theme in theme_alias:
                w["theme"] = theme_alias[theme]
            elif theme in valid_world_themes:
                w["theme"] = theme
            else:
                w["theme"] = "neon"
        elif "theme" in w:
            w["theme"] = "neon"

        if "difficulty_scaling" in w:
            w["difficulty_scaling"] = cls.coerce_float(w["difficulty_scaling"])
        if "wave_count" in w:
            w["wave_count"] = cls.coerce_int(w["wave_count"])
        if "hazard_density" in w:
            w["hazard_density"] = cls.coerce_int(w["hazard_density"])

        if "world_mode" in w and w["world_mode"] is not None:
            wm = str(w["world_mode"]).lower().strip()
            w["world_mode"] = wm

        return w

    @classmethod
    def normalize_player(cls, raw: Dict[str, Any], issues: List[ValidationIssue]) -> Optional[Dict[str, Any]]:
        """Normalize PlayerDef dictionary."""
        if "player" not in raw:
            return None

        p = dict(raw.get("player") or {})

        # Handle legacy aliases
        if "x" in p and "spawn_x" not in p:
            p["spawn_x"] = p.pop("x")
            issues.append(ValidationIssue(path=["player", "x"], issue_type="LEGACY_ALIAS", message="Normalized player.x -> player.spawn_x"))
        if "y" in p and "spawn_y" not in p:
            p["spawn_y"] = p.pop("y")
            issues.append(ValidationIssue(path=["player", "y"], issue_type="LEGACY_ALIAS", message="Normalized player.y -> player.spawn_y"))
        if "health" in p and "max_health" not in p:
            p["max_health"] = p.pop("health")
            issues.append(ValidationIssue(path=["player", "health"], issue_type="LEGACY_ALIAS", message="Normalized player.health -> player.max_health"))
        if "jump" in p and "jump_power" not in p:
            p["jump_power"] = p.pop("jump")
            issues.append(ValidationIssue(path=["player", "jump"], issue_type="LEGACY_ALIAS", message="Normalized player.jump -> player.jump_power"))

        # Strip safe unknown fields
        for k in list(p.keys()):
            if k in KNOWN_SAFE_FIELDS_BY_MODEL["PlayerDef"]:
                p.pop(k)
                issues.append(ValidationIssue(path=["player", k], issue_type="UNKNOWN_FIELD", message=f"Stripped safe non-schema field 'player.{k}'"))

        if "name" in p and p["name"] is not None:
            p["name"] = str(p["name"]).strip()
        if "spawn_x" in p:
            p["spawn_x"] = cls.coerce_int(p["spawn_x"])
        if "spawn_y" in p:
            p["spawn_y"] = cls.coerce_int(p["spawn_y"])
        if "speed" in p:
            p["speed"] = cls.coerce_int(p["speed"])
        if "jump_power" in p:
            p["jump_power"] = cls.coerce_int(p["jump_power"])
        if "max_health" in p:
            p["max_health"] = cls.coerce_int(p["max_health"])
        if "width" in p:
            p["width"] = cls.coerce_int(p["width"])
        if "height" in p:
            p["height"] = cls.coerce_int(p["height"])
        if "color" in p:
            p["color"] = cls.coerce_hex_color(p["color"])
        if "dash_speed" in p:
            p["dash_speed"] = cls.coerce_int(p["dash_speed"])
        if "dash_cooldown" in p:
            p["dash_cooldown"] = cls.coerce_float(p["dash_cooldown"])
        if "stamina" in p:
            p["stamina"] = cls.coerce_int(p["stamina"])

        if "attack_type" in p and p["attack_type"] is not None:
            p["attack_type"] = str(p["attack_type"]).lower().strip()
        if "attack_damage" in p:
            p["attack_damage"] = cls.coerce_int(p["attack_damage"])
        if "attack_cooldown" in p:
            p["attack_cooldown"] = cls.coerce_float(p["attack_cooldown"])
        if "weapon_color" in p:
            p["weapon_color"] = cls.coerce_hex_color(p["weapon_color"])

        return p

    @classmethod
    def normalize_entity(cls, ent: Any, default_id: str, issues: List[ValidationIssue], path: List[Union[str, int]]) -> Dict[str, Any]:
        """Normalize a single EntityDef dictionary."""
        if not isinstance(ent, dict):
            return {
                "id": default_id,
                "type": "enemy",
                "x": 400,
                "y": 300,
            }
        e = dict(ent)

        # Handle aliases
        if "score" in e and "points" not in e:
            e["points"] = e.pop("score")
            issues.append(ValidationIssue(path=path + ["score"], issue_type="LEGACY_ALIAS", message="Normalized entity.score -> points"))
        if "val" in e and "points" not in e:
            e["points"] = e.pop("val")
        if "pos_x" in e and "x" not in e:
            e["x"] = e.pop("pos_x")
        if "pos_y" in e and "y" not in e:
            e["y"] = e.pop("pos_y")
        if "size" in e:
            sz = e.pop("size")
            if "width" not in e:
                e["width"] = sz
            if "height" not in e:
                e["height"] = sz

        # Strip safe unknown fields
        for k in list(e.keys()):
            if k in KNOWN_SAFE_FIELDS_BY_MODEL["EntityDef"]:
                e.pop(k)
                issues.append(ValidationIssue(path=path + [k], issue_type="UNKNOWN_FIELD", message=f"Stripped safe non-schema field 'entity.{k}'"))

        # ID
        if "id" in e and e["id"] is not None:
            e["id"] = str(e["id"]).strip()
        else:
            e["id"] = default_id

        # Type mapping
        VALID_ENTITY_TYPES = {"enemy", "collectible", "obstacle", "platform", "hazard"}
        if "type" in e and e["type"] is not None:
            raw_type = str(e["type"]).lower().strip()
            if "boss" in raw_type:
                e["is_boss"] = True
            if raw_type not in VALID_ENTITY_TYPES:
                if any(w in raw_type for w in ("coin", "gem", "item", "star", "chest", "orb", "loot", "pickup", "key", "crystal", "point")):
                    e["type"] = "collectible"
                elif any(w in raw_type for w in ("monster", "drone", "creature", "mob", "alien", "bot", "zombie", "turret", "soldier", "bad_guy", "enemy", "boss")):
                    e["type"] = "enemy"
                elif any(w in raw_type for w in ("wall", "block", "rock", "barrier", "crate", "tree", "structure", "pillar", "box")):
                    e["type"] = "obstacle"
                elif any(w in raw_type for w in ("floor", "ground", "ledge", "bridge")):
                    e["type"] = "platform"
                elif any(w in raw_type for w in ("lava", "spike", "fire", "laser", "acid", "pit", "saw", "mine", "trap")):
                    e["type"] = "hazard"
                else:
                    e["type"] = raw_type
            else:
                e["type"] = raw_type

        if "x" in e:
            e["x"] = cls.coerce_int(e["x"])
        if "y" in e:
            e["y"] = cls.coerce_int(e["y"])
        if "width" in e:
            w_val = cls.coerce_int(e["width"])
            if isinstance(w_val, int) and w_val > 500:
                w_val = 500
            e["width"] = w_val
        if "height" in e:
            h_val = cls.coerce_int(e["height"])
            if isinstance(h_val, int) and h_val > 500:
                h_val = 500
            e["height"] = h_val
        if "speed" in e:
            e["speed"] = cls.coerce_int(e["speed"])
        if "health" in e:
            e["health"] = cls.coerce_int(e["health"])
        if "points" in e:
            e["points"] = cls.coerce_int(e["points"])
        if "damage" in e:
            e["damage"] = cls.coerce_int(e["damage"])
        if "fire_rate" in e:
            e["fire_rate"] = cls.coerce_float(e["fire_rate"])
        if "patrol_radius" in e:
            e["patrol_radius"] = cls.coerce_int(e["patrol_radius"])
        if "detection_radius" in e:
            e["detection_radius"] = cls.coerce_int(e["detection_radius"])
        if "color" in e:
            e["color"] = cls.coerce_hex_color(e["color"])

        # Boss attributes
        if "is_boss" in e:
            is_boss = cls.coerce_bool(e["is_boss"], False)
            e["is_boss"] = is_boss
            if is_boss and e.get("health", 0) < 150:
                e["health"] = 200
        if "boss_phases" in e:
            e["boss_phases"] = cls.coerce_int(e["boss_phases"])
        if "telegraph_ms" in e:
            e["telegraph_ms"] = cls.coerce_int(e["telegraph_ms"])

        # Behavior
        VALID_BEHAVIORS = {"patrol", "chase", "stationary", "bounce", "float", "flee", "guard", "ranged_attack"}
        if "behavior" in e and e["behavior"] is not None:
            raw_beh = str(e["behavior"]).lower().strip()
            if raw_beh not in VALID_BEHAVIORS:
                if any(w in raw_beh for w in ("shoot", "range", "fire", "gun", "laser", "projectile")):
                    e["behavior"] = "ranged_attack"
                elif any(w in raw_beh for w in ("chase", "follow", "hunt", "pursue", "aggro", "seek")):
                    e["behavior"] = "chase"
                elif any(w in raw_beh for w in ("static", "idle", "none", "stay", "fixed", "still", "stand", "stop")):
                    e["behavior"] = "stationary"
                elif any(w in raw_beh for w in ("bounce", "rebound", "pong")):
                    e["behavior"] = "bounce"
                elif any(w in raw_beh for w in ("float", "hover", "fly", "glide", "sine")):
                    e["behavior"] = "float"
                elif any(w in raw_beh for w in ("flee", "run", "escape", "retreat", "avoid")):
                    e["behavior"] = "flee"
                elif any(w in raw_beh for w in ("guard", "defend", "sentry", "protect", "zone")):
                    e["behavior"] = "guard"
                else:
                    e["behavior"] = raw_beh
            else:
                e["behavior"] = raw_beh

        return e

    @classmethod
    def normalize_rule(cls, rule: Any, default_id: str, issues: List[ValidationIssue], path: List[Union[str, int]]) -> Dict[str, Any]:
        """Normalize a single RuleDef dictionary."""
        if not isinstance(rule, dict):
            return {
                "id": default_id,
                "trigger": "on_collide_enemy",
                "action": "damage_player",
                "params": {"damage": 15},
            }
        r = dict(rule)

        # Aliases
        if "event" in r and "trigger" not in r:
            r["trigger"] = r.pop("event")
        if "handler" in r and "action" not in r:
            r["action"] = r.pop("handler")

        # Strip safe unknown fields
        for k in list(r.keys()):
            if k in KNOWN_SAFE_FIELDS_BY_MODEL["RuleDef"]:
                r.pop(k)
                issues.append(ValidationIssue(path=path + [k], issue_type="UNKNOWN_FIELD", message=f"Stripped safe non-schema field 'rule.{k}'"))

        r["id"] = str(r.get("id") or default_id).strip()[:50]

        # Trigger
        VALID_TRIGGERS = {
            "on_collect", "on_collide_enemy", "on_reach_goal", "on_score_target",
            "on_time_limit", "on_player_death", "on_wave_start", "on_dash",
            "on_hazard_touch", "on_enemy_defeat", "on_checkpoint", "on_powerup_expire",
        }
        if "trigger" in r and r["trigger"] is not None:
            trig = r["trigger"]
            if isinstance(trig, dict):
                trig = trig.get("type", "on_collide_enemy")
            trig_str = str(trig).lower().strip()
            if trig_str in VALID_TRIGGERS:
                r["trigger"] = trig_str
            else:
                trigger_alias = {
                    "collect": "on_collect",
                    "on_item_collect": "on_collect",
                    "on_gem_collect": "on_collect",
                    "collide": "on_collide_enemy",
                    "on_hit_enemy": "on_collide_enemy",
                    "on_enemy_collision": "on_collide_enemy",
                    "reach_goal": "on_reach_goal",
                    "on_goal": "on_reach_goal",
                    "on_win": "on_reach_goal",
                    "score_target": "on_score_target",
                    "time_limit": "on_time_limit",
                    "player_death": "on_player_death",
                    "hazard_touch": "on_hazard_touch",
                    "enemy_defeat": "on_enemy_defeat",
                    "dash": "on_dash",
                }
                if trig_str in trigger_alias:
                    r["trigger"] = trigger_alias[trig_str]
                else:
                    r["trigger"] = trig_str

        # Action
        VALID_ACTIONS = {
            "add_score", "damage_player", "heal_player", "win_game", "lose_game",
            "spawn_entity", "speed_boost", "trigger_screen_shake", "spawn_wave",
            "grant_powerup", "activate_checkpoint", "spawn_particles", "knockback_target",
        }
        params = dict(r.get("params") or {}) if isinstance(r.get("params"), dict) else {}
        if "action" in r and r["action"] is not None:
            act = r["action"]
            if isinstance(act, dict):
                for k, v in act.items():
                    if k != "type" and k not in params:
                        params[k] = v
                act = act.get("type", "damage_player")
            act_str = str(act).lower().strip()
            if act_str in VALID_ACTIONS:
                r["action"] = act_str
            else:
                action_alias = {
                    "score": "add_score",
                    "increase_score": "add_score",
                    "win": "win_game",
                    "victory": "win_game",
                    "lose": "lose_game",
                    "game_over": "lose_game",
                    "heal": "heal_player",
                    "damage": "damage_player",
                    "hurt": "damage_player",
                    "wave": "spawn_wave",
                    "boost": "speed_boost",
                }
                if act_str in action_alias:
                    r["action"] = action_alias[act_str]
                else:
                    r["action"] = act_str
        r["params"] = params

        return r

    @classmethod
    def normalize_levels(cls, raw: Dict[str, Any], issues: List[ValidationIssue]) -> List[Dict[str, Any]]:
        """
        Normalize campaign levels array.
        Resolves the specific schema drift where the model emits world/stage fields
        (such as `width`, `height`, `gravity`, `theme`, `hazard_density`) directly on `LevelDef`.
        """
        levels = raw.get("levels")
        if not isinstance(levels, list):
            return []

        norm_levels: List[Dict[str, Any]] = []
        for idx, lvl in enumerate(levels):
            if not isinstance(lvl, dict):
                continue
            l = dict(lvl)

            # 1. Check for world fields placed directly on level (e.g. levels[0].width)
            level_world_fields = {"width", "height", "gravity", "background_color", "hazard_density", "wave_count", "difficulty_scaling"}
            found_world_fields = {k: l.pop(k) for k in list(l.keys()) if k in level_world_fields and l[k] is not None}
            # Also clean up any None world fields on level without migrating them
            for k in list(l.keys()):
                if k in level_world_fields and l[k] is None:
                    l.pop(k)

            if found_world_fields:
                issues.append(ValidationIssue(
                    path=["levels", idx, list(found_world_fields.keys())[0]],
                    issue_type="MIGRATED_LEVEL_WORLD_FIELD",
                    message=f"Migrated level-level world fields {list(found_world_fields.keys())} into levels[{idx}].world",
                ))
                # If level does not have its own world dict, create one with these fields
                if "world" not in l or not isinstance(l.get("world"), dict):
                    # Inherit base world defaults and overlay level fields
                    base_world = dict(raw.get("world") or {})
                    # Only copy non-null fields from base_world
                    base_world = {bk: bv for bk, bv in base_world.items() if bv is not None}
                    base_world.update(found_world_fields)
                    l["world"] = base_world
                else:
                    l["world"].update(found_world_fields)

            # If level.world is None or not a dict, remove it so LevelDef defaults to None
            if "world" in l and (l["world"] is None or not isinstance(l["world"], dict)):
                l.pop("world", None)

            # 2. Extract / clean level metadata & legacy fields
            raw_num = l.get("level_number", l.get("level_id", l.get("id", l.get("stage_number", l.get("stage", idx + 1)))))
            if isinstance(raw_num, int):
                l["level_number"] = max(1, min(10, raw_num))
            elif isinstance(raw_num, str):
                digits = re.findall(r"\d+", raw_num)
                l["level_number"] = int(digits[0]) if digits else (idx + 1)
            else:
                l["level_number"] = idx + 1

            if "title" not in l or not isinstance(l.get("title"), str) or not l["title"].strip():
                l["title"] = l.get("name", f"Level {l['level_number']}")

            # Clean theme if present on level
            if "theme" in l:
                if l["theme"] is None:
                    l.pop("theme", None)
                elif isinstance(l["theme"], str):
                    lvl_th = l["theme"].lower().strip()
                    valid_lvl_themes = {"cyberpunk", "retro_arcade", "dungeon", "space", "neon", "minimal"}
                    theme_alias = {
                        "cyber": "cyberpunk",
                        "scifi": "space",
                        "sci_fi": "space",
                        "retro": "retro_arcade",
                        "pixel": "retro_arcade",
                        "dark": "dungeon",
                        "cave": "dungeon",
                    }
                    if lvl_th in theme_alias:
                        l["theme"] = theme_alias[lvl_th]
                    elif lvl_th in valid_lvl_themes:
                        l["theme"] = lvl_th
                    else:
                        # Unknown level theme - drop it safely so schema validator doesn't reject
                        l.pop("theme", None)

            # Strip known safe non-schema fields on LevelDef
            for k in list(l.keys()):
                if k in KNOWN_SAFE_FIELDS_BY_MODEL["LevelDef"]:
                    l.pop(k)
                    issues.append(ValidationIssue(
                        path=["levels", idx, k],
                        issue_type="UNKNOWN_FIELD",
                        message=f"Stripped safe non-schema field 'levels[{idx}].{k}'",
                    ))

            # Normalize level world if present
            if "world" in l and isinstance(l["world"], dict):
                l["world"] = cls.normalize_world({"world": l["world"]}, issues)

            # Normalize spawn coordinates
            if "spawn_x" in l:
                l["spawn_x"] = cls.coerce_int(l["spawn_x"], 400, 0, 3840)
            if "spawn_y" in l:
                l["spawn_y"] = cls.coerce_int(l["spawn_y"], 300, 0, 2160)

            # Normalize Objective
            obj = dict(l.get("objective") or {}) if isinstance(l.get("objective"), dict) else {}
            if isinstance(l.get("objective"), str):
                obj = {"description": l["objective"]}
            obj_type = str(obj.get("type") or "collect_all").lower().strip()
            valid_obj_types = {"collect_all", "defeat_all", "reach_exit", "survive_time", "score_target"}
            obj["type"] = obj_type if obj_type in valid_obj_types else "collect_all"
            obj["target_count"] = cls.coerce_int(obj.get("target_count"), 1, 1, 100)
            obj["target_score"] = cls.coerce_int(obj.get("target_score"), 100, 0, 100000)
            obj["time_limit_seconds"] = cls.coerce_int(obj.get("time_limit_seconds"), 0, 0, 600)
            obj["description"] = str(obj.get("description") or "Complete stage objective").strip()[:150]
            # Strip objective non-schema fields
            for ok in list(obj.keys()):
                if ok in KNOWN_SAFE_FIELDS_BY_MODEL["ObjectiveDef"]:
                    obj.pop(ok)
            l["objective"] = obj

            # Normalize entities in level
            lvl_ents = l.get("entities") or []
            if isinstance(lvl_ents, list):
                l["entities"] = [
                    cls.normalize_entity(e, f"lvl{l['level_number']}_ent_{e_idx+1}", issues, ["levels", idx, "entities", e_idx])
                    for e_idx, e in enumerate(lvl_ents)
                ][:30]

            # Normalize rules in level
            lvl_rules = l.get("rules") or []
            if isinstance(lvl_rules, list):
                l["rules"] = [
                    cls.normalize_rule(r, f"lvl{l['level_number']}_rule_{r_idx+1}", issues, ["levels", idx, "rules", r_idx])
                    for r_idx, r in enumerate(lvl_rules)
                ][:15]

            l["completion_message"] = str(l.get("completion_message") or "LEVEL COMPLETE!").strip()[:100]
            l["is_finale"] = cls.coerce_bool(l.get("is_finale"), False)

            norm_levels.append(l)

        return norm_levels[:5]

    @classmethod
    def normalize(cls, raw: Union[str, Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], List[ValidationIssue]]:
        """
        Main entrypoint: Parse, scan for unsafe code, and deterministically normalize
        a candidate DSL payload.
        
        Returns:
            (normalized_dict_or_None, list_of_issues)
        """
        issues: List[ValidationIssue] = []

        # 1. Parse JSON
        parsed: Dict[str, Any]
        if isinstance(raw, str):
            cleaned_text = cls.clean_json_text(raw)
            try:
                parsed = json.loads(cleaned_text)
            except json.JSONDecodeError as err:
                issues.append(ValidationIssue(
                    path=["root"],
                    issue_type="MALFORMED_JSON",
                    message=f"JSON decoding error: {str(err)}",
                    severity="HIGH",
                    repairability="SEMANTIC",
                ))
                return None, issues
        elif isinstance(raw, dict):
            parsed = dict(raw)
        else:
            issues.append(ValidationIssue(
                path=["root"],
                issue_type="INVALID_TYPE",
                message=f"Expected JSON string or dict, got {type(raw).__name__}",
                severity="HIGH",
                repairability="SEMANTIC",
            ))
            return None, issues

        # 2. Extract from wrapper if needed (e.g. {"design_spec": ..., "dsl": ...})
        if "dsl" in parsed and isinstance(parsed["dsl"], dict):
            dsl_candidate = dict(parsed["dsl"])
        else:
            dsl_candidate = dict(parsed)

        # 3. Scan for unsafe code injection
        unsafe_issue = cls.check_for_unsafe_content(dsl_candidate, [])
        if unsafe_issue:
            issues.append(unsafe_issue)
            return None, issues

        # 4. Perform deterministic normalization across all sub-components
        normalized: Dict[str, Any] = {}
        normalized["schema_version"] = str(dsl_candidate.get("schema_version") or "3.0")
        if normalized["schema_version"] not in ("1.0", "2.0", "3.0"):
            normalized["schema_version"] = "3.0"

        normalized["metadata"] = cls.normalize_metadata(dsl_candidate, issues)
        normalized["world"] = cls.normalize_world(dsl_candidate, issues)
        normalized["player"] = cls.normalize_player(dsl_candidate, issues)

        # Top-level entities
        raw_ents = dsl_candidate.get("entities") or []
        if isinstance(raw_ents, list):
            normalized["entities"] = [
                cls.normalize_entity(e, f"entity_{e_idx+1}", issues, ["entities", e_idx])
                for e_idx, e in enumerate(raw_ents)
            ][:30]
        else:
            normalized["entities"] = []

        # Top-level rules
        raw_rules = dsl_candidate.get("rules") or []
        if isinstance(raw_rules, list):
            normalized["rules"] = [
                cls.normalize_rule(r, f"rule_{r_idx+1}", issues, ["rules", r_idx])
                for r_idx, r in enumerate(raw_rules)
            ][:20]
        else:
            normalized["rules"] = []

        # UI
        raw_ui = dict(dsl_candidate.get("ui") or {}) if isinstance(dsl_candidate.get("ui"), dict) else {}
        for k in list(raw_ui.keys()):
            if k in KNOWN_SAFE_FIELDS_BY_MODEL["UIDef"]:
                raw_ui.pop(k)
        normalized["ui"] = {
            "show_health": cls.coerce_bool(raw_ui.get("show_health"), True),
            "show_score": cls.coerce_bool(raw_ui.get("show_score"), True),
            "show_stamina": cls.coerce_bool(raw_ui.get("show_stamina"), True),
            "show_wave": cls.coerce_bool(raw_ui.get("show_wave"), True),
            "show_objectives": cls.coerce_bool(raw_ui.get("show_objectives"), True),
            "status_text": str(raw_ui.get("status_text") or "PLAY PROTOTYPE").strip()[:100],
        }

        # Multi-Level Campaigns (includes levels[0].width normalization!)
        normalized["levels"] = cls.normalize_levels(dsl_candidate, issues)

    @classmethod
    def normalize_open_world(cls, raw_ow: Dict[str, Any], issues: List[ValidationIssue]) -> Dict[str, Any]:
        """Normalize OpenWorldDef dictionary and strip known safe non-schema fields from submodels."""
        ow = dict(raw_ow)

        # 1. Regions
        if "regions" in ow and isinstance(ow["regions"], list):
            norm_regions = []
            for r_idx, reg in enumerate(ow["regions"]):
                if isinstance(reg, dict):
                    r = dict(reg)
                    for k in list(r.keys()):
                        if k in KNOWN_SAFE_FIELDS_BY_MODEL["RegionDef"]:
                            r.pop(k)
                            issues.append(ValidationIssue(
                                path=["open_world", "regions", r_idx, k],
                                issue_type="UNKNOWN_FIELD",
                                message=f"Stripped safe non-schema field 'open_world.regions[{r_idx}].{k}'",
                            ))
                    norm_regions.append(r)
            ow["regions"] = norm_regions

        # 2. Vehicles
        if "vehicles" in ow and isinstance(ow["vehicles"], list):
            norm_vehs = []
            for v_idx, veh in enumerate(ow["vehicles"]):
                if isinstance(veh, dict):
                    v = dict(veh)
                    for k in list(v.keys()):
                        if k in KNOWN_SAFE_FIELDS_BY_MODEL["VehicleDef"]:
                            v.pop(k)
                            issues.append(ValidationIssue(
                                path=["open_world", "vehicles", v_idx, k],
                                issue_type="UNKNOWN_FIELD",
                                message=f"Stripped safe non-schema field 'open_world.vehicles[{v_idx}].{k}'",
                            ))
                    norm_vehs.append(v)
            ow["vehicles"] = norm_vehs

        # 3. POIs
        if "pois" in ow and isinstance(ow["pois"], list):
            norm_pois = []
            for p_idx, poi in enumerate(ow["pois"]):
                if isinstance(poi, dict):
                    p = dict(poi)
                    if "label" in p and "name" not in p:
                        p["name"] = p.pop("label")
                    if "title" in p and "name" not in p:
                        p["name"] = p.pop("title")
                    for k in list(p.keys()):
                        if k in KNOWN_SAFE_FIELDS_BY_MODEL["POIDef"]:
                            p.pop(k)
                            issues.append(ValidationIssue(
                                path=["open_world", "pois", p_idx, k],
                                issue_type="UNKNOWN_FIELD",
                                message=f"Stripped safe non-schema field 'open_world.pois[{p_idx}].{k}'",
                            ))
                    norm_pois.append(p)
            ow["pois"] = norm_pois

        # 4. Activities
        if "activities" in ow and isinstance(ow["activities"], list):
            norm_acts = []
            for a_idx, act in enumerate(ow["activities"]):
                if isinstance(act, dict):
                    a = dict(act)
                    if "name" in a and "title" not in a:
                        a["title"] = a.pop("name")
                    for k in list(a.keys()):
                        if k in KNOWN_SAFE_FIELDS_BY_MODEL.get("ActivityDef", set()):
                            a.pop(k)
                    norm_acts.append(a)
            ow["activities"] = norm_acts

        # 5. Actors
        if "actors" in ow and isinstance(ow["actors"], list):
            norm_actors = []
            for act_idx, actor in enumerate(ow["actors"]):
                if isinstance(actor, dict):
                    ac = dict(actor)
                    if "label" in ac and "name" not in ac:
                        ac["name"] = ac.pop("label")
                    if "title" in ac and "name" not in ac:
                        ac["name"] = ac.pop("title")
                    for k in list(ac.keys()):
                        if k in KNOWN_SAFE_FIELDS_BY_MODEL["ActorDef"]:
                            ac.pop(k)
                    norm_actors.append(ac)
            ow["actors"] = norm_actors

        # 6. Factions
        if "factions" in ow and isinstance(ow["factions"], list):
            norm_facs = []
            for f_idx, fac in enumerate(ow["factions"]):
                if isinstance(fac, dict):
                    f = dict(fac)
                    for k in list(f.keys()):
                        if k in KNOWN_SAFE_FIELDS_BY_MODEL["FactionDef"]:
                            f.pop(k)
                    norm_facs.append(f)
            ow["factions"] = norm_facs

        # 7. Threat System
        if "threat_system" in ow and isinstance(ow["threat_system"], dict):
            ts = dict(ow["threat_system"])
            for k in list(ts.keys()):
                if k in KNOWN_SAFE_FIELDS_BY_MODEL["ThreatSystemDef"]:
                    ts.pop(k)
            ow["threat_system"] = ts

        # 8. Time System
        if "time_system" in ow and isinstance(ow["time_system"], dict):
            tm = dict(ow["time_system"])
            for k in list(tm.keys()):
                if k in KNOWN_SAFE_FIELDS_BY_MODEL["WorldTimeDef"]:
                    tm.pop(k)
            ow["time_system"] = tm

        # 9. Events
        if "events" in ow and isinstance(ow["events"], list):
            norm_evts = []
            for e_idx, evt in enumerate(ow["events"]):
                if isinstance(evt, dict):
                    ev = dict(evt)
                    for k in list(ev.keys()):
                        if k in KNOWN_SAFE_FIELDS_BY_MODEL["WorldEventDef"]:
                            ev.pop(k)
                    norm_evts.append(ev)
            ow["events"] = norm_evts

        return ow

    @classmethod
    def normalize(cls, raw: Union[str, Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], List[ValidationIssue]]:
        """
        Main entrypoint: Parse, scan for unsafe code, and deterministically normalize
        a candidate DSL payload.
        
        Returns:
            (normalized_dict_or_None, list_of_issues)
        """
        issues: List[ValidationIssue] = []

        # 1. Parse JSON
        parsed: Dict[str, Any]
        if isinstance(raw, str):
            cleaned_text = cls.clean_json_text(raw)
            try:
                parsed = json.loads(cleaned_text)
            except json.JSONDecodeError as err:
                issues.append(ValidationIssue(
                    path=["root"],
                    issue_type="MALFORMED_JSON",
                    message=f"JSON decoding error: {str(err)}",
                    severity="HIGH",
                    repairability="SEMANTIC",
                ))
                return None, issues
        elif isinstance(raw, dict):
            parsed = dict(raw)
        else:
            issues.append(ValidationIssue(
                path=["root"],
                issue_type="INVALID_TYPE",
                message=f"Expected JSON string or dict, got {type(raw).__name__}",
                severity="HIGH",
                repairability="SEMANTIC",
            ))
            return None, issues

        # 2. Extract from wrapper if needed (e.g. {"design_spec": ..., "dsl": ...})
        if "dsl" in parsed and isinstance(parsed["dsl"], dict):
            dsl_candidate = dict(parsed["dsl"])
        else:
            dsl_candidate = dict(parsed)

        # 3. Scan for unsafe code injection
        unsafe_issue = cls.check_for_unsafe_content(dsl_candidate, [])
        if unsafe_issue:
            issues.append(unsafe_issue)
            return None, issues

        # 4. Perform deterministic normalization across all sub-components
        normalized: Dict[str, Any] = {}
        normalized["schema_version"] = str(dsl_candidate.get("schema_version") or "3.0")
        if normalized["schema_version"] not in ("1.0", "2.0", "3.0"):
            normalized["schema_version"] = "3.0"

        norm_meta = cls.normalize_metadata(dsl_candidate, issues)
        if norm_meta is not None:
            normalized["metadata"] = norm_meta

        norm_world = cls.normalize_world(dsl_candidate, issues)
        if norm_world is not None:
            normalized["world"] = norm_world

        norm_player = cls.normalize_player(dsl_candidate, issues)
        if norm_player is not None:
            normalized["player"] = norm_player

        # Top-level entities
        raw_ents = dsl_candidate.get("entities")
        if isinstance(raw_ents, list):
            normalized["entities"] = [
                cls.normalize_entity(e, f"entity_{e_idx+1}", issues, ["entities", e_idx])
                for e_idx, e in enumerate(raw_ents)
            ]
        elif raw_ents is not None:
            normalized["entities"] = raw_ents

        # Top-level rules
        raw_rules = dsl_candidate.get("rules")
        if isinstance(raw_rules, list):
            normalized["rules"] = [
                cls.normalize_rule(r, f"rule_{r_idx+1}", issues, ["rules", r_idx])
                for r_idx, r in enumerate(raw_rules)
            ]
        elif raw_rules is not None:
            normalized["rules"] = raw_rules

        # UI
        raw_ui = dict(dsl_candidate.get("ui") or {}) if isinstance(dsl_candidate.get("ui"), dict) else {}
        for k in list(raw_ui.keys()):
            if k in KNOWN_SAFE_FIELDS_BY_MODEL["UIDef"]:
                raw_ui.pop(k)
        if "ui" in dsl_candidate or raw_ui:
            normalized["ui"] = {
                "show_health": cls.coerce_bool(raw_ui.get("show_health"), True),
                "show_score": cls.coerce_bool(raw_ui.get("show_score"), True),
                "show_stamina": cls.coerce_bool(raw_ui.get("show_stamina"), True),
                "show_wave": cls.coerce_bool(raw_ui.get("show_wave"), True),
                "show_objectives": cls.coerce_bool(raw_ui.get("show_objectives"), True),
                "status_text": str(raw_ui.get("status_text") or "PLAY PROTOTYPE").strip()[:100],
            }

        # Multi-Level Campaigns (includes levels[0].width normalization!)
        if "levels" in dsl_candidate:
            normalized["levels"] = cls.normalize_levels(dsl_candidate, issues)

        # Normalize Open World if present
        if "open_world" in dsl_candidate and isinstance(dsl_candidate["open_world"], dict):
            normalized["open_world"] = cls.normalize_open_world(dsl_candidate["open_world"], issues)

        return normalized, issues
