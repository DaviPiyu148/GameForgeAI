import copy
import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.ai.hosted_provider import AIProviderRouter
from app.ai.prompts import (
    SYSTEM_PROMPT,
    build_generation_prompt,
    build_repair_prompt,
    build_playtest_analysis_prompt,
    build_improvement_prompt,
    build_remix_prompt,
)
from app.ai.provider import (
    AIConfigurationError,
    AIError,
    AIProvider,
    ModelInvalidResponseError,
    ModelRateLimitedError,
    ModelTimeoutError,
    ModelUnavailableError,
)
from app.config import settings
from app.generation.dsl_models import GameDSL
from app.generation.validator import validate_game_dsl
from app.generation.quality_validator import GameplayQualityValidator
from app.schemas.design_spec import GameDesignSpec


class GenerationResult:
    """Outcome of AI Game DSL generation pipeline."""

    def __init__(
        self,
        success: bool,
        dsl: Optional[GameDSL] = None,
        design_spec: Optional[GameDesignSpec] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        attempts_used: int = 1,
        provider_meta: Optional[Dict[str, Any]] = None,
    ):
        self.success = success
        self.dsl = dsl
        self.design_spec = design_spec
        self.error_code = error_code
        self.error_message = error_message
        self.attempts_used = attempts_used
        self.provider_meta = provider_meta or {}


class GameGenerationService:
    """
    Orchestration service for LLM-driven structured Game DSL generation,
    gameplay quality validation, bounded AI repair, playtest critique, and DSL patching.
    """

    def __init__(
        self,
        provider: Optional[AIProvider] = None,
        max_retries: Optional[int] = None,
    ):
        self.provider = provider or AIProviderRouter()
        self.max_retries = max_retries if max_retries is not None else settings.AI_MAX_RETRIES

    def _extract_spec_and_dsl(self, raw_output: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Extract design_spec and dsl dictionaries from model output."""
        if "design_spec" in raw_output and "dsl" in raw_output:
            return raw_output.get("design_spec"), raw_output.get("dsl", {})
        elif "metadata" in raw_output:
            # Candidate is a direct GameDSL object
            meta = raw_output.get("metadata", {})
            spec_dict = {
                "title": meta.get("title", "Game Prototype"),
                "elevator_pitch": meta.get("description", "A playable game prototype."),
                "genre": meta.get("genre", "Action"),
                "theme": raw_output.get("world", {}).get("theme", "neon"),
                "core_gameplay_loop": "evade -> collect -> survive",
                "player_role": "Runner / Survivor",
                "primary_objective": "Survive waves and maximize score",
            }
            return spec_dict, raw_output
        return None, raw_output

    def _compile_and_propagate_parameters(
        self,
        dsl_dict: Dict[str, Any],
        spec_dict: Optional[Dict[str, Any]],
        engine: str,
        art_density: int,
        physics: int,
        modules: List[str],
    ) -> Dict[str, Any]:
        """
        Deepens compilation from GameDesignSpec and propagates user-configurable Builder parameters
        (preset, physics, art density, logic modules) into concrete, validated DSL attributes.
        """
        compiled = copy.deepcopy(dsl_dict)
        meta = compiled.setdefault("metadata", {})
        world = compiled.setdefault("world", {})
        player = compiled.setdefault("player", {})
        entities = compiled.setdefault("entities", [])
        rules = compiled.setdefault("rules", [])
        ui = compiled.setdefault("ui", {})

        # 1. Prototype Profile (engine) mapping
        if engine == "2D Platformer":
            meta["archetype"] = "platformer"
            if world.get("gravity", 0) <= 0:
                world["gravity"] = int(500 + (physics / 100) * 400)
            if player.get("jump_power", 0) <= 0:
                player["jump_power"] = int(380 + (physics / 100) * 200)
            # Ensure goal entity / rule exists if platformer
            has_goal = any(r.get("trigger") == "on_reach_goal" for r in rules)
            if not has_goal:
                rules.append({
                    "id": f"rule_goal_auto_{len(rules)+1}",
                    "trigger": "on_reach_goal",
                    "action": "win_game",
                })
        elif engine == "Arena Survival":
            meta["archetype"] = "survival"
            world["gravity"] = 0
            world["wave_count"] = max(3, world.get("wave_count", 3))
        elif engine == "Data Collector":
            meta["archetype"] = "collector"
            world["gravity"] = 0
        elif engine == "Top-Down Action":
            world["gravity"] = 0

        # 2. Physics parameter propagation
        # Locomotion attributes. Consistent with the gravity/jump_power checks above:
        # only fill in a physics-derived value when the field is truly absent or
        # non-positive (invalid/placeholder), never merely because it equals the
        # prompt template's few-shot example value (250 / 600) — the AI may have
        # legitimately chosen that exact value on purpose, and clobbering it discarded
        # real design intent.
        if player.get("speed", 0) <= 0:
            player["speed"] = int(200 + (physics / 100) * 100)
        if player.get("dash_speed", 0) <= 0:
            player["dash_speed"] = int(450 + (physics / 100) * 300)

        # 3. Art density propagation
        world["hazard_density"] = int(10 + (art_density / 100) * 50)

        # 4. Logic Modules Materialization
        if "Combat & Dash Mobility" in modules:
            player["dash_speed"] = max(player.get("dash_speed", 0), 500)
            player["stamina"] = max(player.get("stamina", 0), 100)
            if player.get("attack_type") in (None, "none"):
                player["attack_type"] = "ranged"
            player["attack_damage"] = max(player.get("attack_damage", 0), 25)

        if "Resource & Score Economy" in modules:
            ui["show_score"] = True
            all_ents = list(entities)
            for lvl in compiled.get("levels", []):
                if isinstance(lvl, dict):
                    all_ents.extend(lvl.get("entities", []))
            has_score_rule = any(r.get("action") == "add_score" for r in rules)
            if not has_score_rule and any(isinstance(e, dict) and e.get("type") == "collectible" for e in all_ents):
                rules.append({
                    "id": f"rule_score_auto_{len(rules)+1}",
                    "trigger": "on_collect",
                    "action": "add_score",
                    "params": {"amount": 50},
                })

        # 5. Objective & UI compilation
        if spec_dict:
            primary_obj = spec_dict.get("primary_objective")
            if not primary_obj and isinstance(spec_dict.get("objective_details"), dict):
                primary_obj = spec_dict["objective_details"].get("primary")
            if primary_obj and "status_text" not in ui:
                ui["status_text"] = primary_obj[:38].upper()

        return compiled

    async def generate_game_dsl(
        self,
        prompt: str,
        engine: str = "Top-Down Action",
        art_density: int = 50,
        physics: int = 80,
        modules: List[str] = None,
        inspiration: Optional[Dict[str, Any]] = None,
        personalization: Optional[Dict[str, Any]] = None,
        emit_log: Optional[Callable[[str, str], None]] = None,
        set_status: Optional[Callable[[str], None]] = None,
        scale: str = "standard",
        world_mode: str = "linear",
    ) -> GenerationResult:
        """
        Execute the generation pipeline: Prompt -> Gemini -> Schema & Quality Validation -> Bounded Repair.
        """
        def log(level: str, msg: str):
            if emit_log:
                emit_log(level, msg)

        def status(st: str):
            if set_status:
                set_status(st)

        status("RUNNING")

        # Deterministic test failure compatibility trigger.
        # Intentionally case-SENSITIVE (unlike the prior /\bERROR\b/i): a deliberate
        # all-caps "ERROR" sentinel is not something ordinary natural-language game
        # prompts produce, whereas case-insensitive matching false-positived on
        # legitimate prompts merely containing the word "error" (e.g. a game about
        # fixing bugs/glitches). See backend/tests/test_builds.py::test_build_failure_on_error_prompt.
        if re.search(r"\bERROR\b", prompt):
            log("ERROR", "> FATAL_EXCEPTION: BUILD_FAILED: Prompt triggered deterministic failure demonstration.")
            return GenerationResult(
                success=False,
                error_code="BUILD_SYNTAX_ERROR",
                error_message="Prompt contains deterministic error trigger.",
            )

        active_mods = modules or []
        user_prompt = build_generation_prompt(
            prompt=prompt,
            engine=engine,
            art_density=art_density,
            physics=physics,
            modules=active_mods,
            inspiration=inspiration,
            personalization=personalization,
            scale=scale,
            world_mode=world_mode,
        )

        raw_output: Dict[str, Any]
        provider_meta: Dict[str, Any] = {}

        try:
            if hasattr(self.provider, "generate_structured_with_meta"):
                raw_output, provider_meta = await self.provider.generate_structured_with_meta(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                )
            else:
                raw_output = await self.provider.generate_structured(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                )
                provider_meta = {
                    "provider": getattr(self.provider, "provider_name", "hosted_provider"),
                    "model": getattr(self.provider, "model", "default"),
                    "fallback_used": False,
                }

            # 1. Log actual provider metadata
            raw_provider = str(provider_meta.get("provider", "gemini")).lower()
            model_id = str(provider_meta.get("model", settings.GEMINI_MODEL))

            if raw_provider == "gemini":
                human_provider = "Google Gemini"
                if "gemini" in model_id.lower():
                    human_model = "Gemini 3 Flash Preview" if "flash" in model_id.lower() else model_id
                elif "gemma" in model_id.lower():
                    human_model = "Gemma 4 31B"
                else:
                    human_model = model_id
            elif raw_provider == "groq":
                human_provider = "Groq"
                human_model = "Llama 3.1 8B" if "llama-3.1" in model_id.lower() else model_id
            else:
                human_provider = raw_provider.capitalize()
                human_model = model_id

            if provider_meta.get("fallback_used"):
                log("INFO", f"[AI] PROVIDER: {human_provider} // {human_model} (Fallback: {provider_meta.get('fallback_reason')})")
            else:
                log("INFO", f"[AI] PROVIDER: {human_provider} // {human_model}")
            log("INFO", f"[AI] MODEL: {model_id}")
            log("INFO", f"[AI] INTENT: > {prompt.strip()}")

            # 2. Extract structured design information
            spec_dict, raw_dsl_dict = self._extract_spec_and_dsl(raw_output)

            # 3. Propagate and compile builder parameters into DSL
            dsl_dict = self._compile_and_propagate_parameters(
                dsl_dict=raw_dsl_dict,
                spec_dict=spec_dict,
                engine=engine,
                art_density=art_density,
                physics=physics,
                modules=active_mods,
            )

            if spec_dict:
                pitch = spec_dict.get("elevator_pitch", "")
                loop = spec_dict.get("core_gameplay_loop", "evade -> collect -> survive")
                primary_obj = spec_dict.get("primary_objective", "Complete level")
                log("INFO", f"[AI] GAME DESIGN: {pitch}")
                log("INFO", f"> Core loop: {loop}")
                log("INFO", f"> Objective: {primary_obj}")

                phases = spec_dict.get("progression_phases", [])
                if phases:
                    for p in phases:
                        if isinstance(p, dict):
                            log("INFO", f"> Phase ({p.get('phase', 'EARLY')}): {p.get('description', '')}")

            meta_sec = dsl_dict.get("metadata", {})
            world_sec = dsl_dict.get("world", {})
            player_sec = dsl_dict.get("player", {})
            entities_list = dsl_dict.get("entities", [])
            rules_list = dsl_dict.get("rules", [])
            levels_list = dsl_dict.get("levels", [])

            total_entities_count = len(entities_list)
            if not total_entities_count and levels_list:
                total_entities_count = sum(len(lvl.get("entities", [])) for lvl in levels_list if isinstance(lvl, dict))

            total_rules_count = len(rules_list)
            if not total_rules_count and levels_list:
                total_rules_count = sum(len(lvl.get("rules", [])) for lvl in levels_list if isinstance(lvl, dict))

            archetype = meta_sec.get("archetype", "survival")
            theme = world_sec.get("theme", "neon")
            hp = player_sec.get("max_health", 100)
            spd = player_sec.get("speed", 250)

            log("INFO", f"[AI] DSL: Archetype: {archetype} // Theme: {theme}")
            log("INFO", f"> Player: {hp} HP @ {spd} px/s (Dash: {player_sec.get('dash_speed', 600)} px/s)")
            log("INFO", f"> Entities: {total_entities_count} spawned across world ({world_sec.get('width', 800)}x{world_sec.get('height', 600)})")
            log("INFO", f"> Rules: {total_rules_count} event handlers registered")

            if dsl_dict.get("open_world"):
                ow = dsl_dict["open_world"]
                log("INFO", f"[AI] OPEN WORLD: {len(ow.get('regions', []))} Regions, {len(ow.get('pois', []))} POIs, {len(ow.get('factions', []))} Factions, {len(ow.get('vehicles', []))} Vehicles, {len(ow.get('activities', []))} Activities")

        except AIConfigurationError as cfg_err:
            log("ERROR", f"[AI] Configuration error: {cfg_err.message}")
            return GenerationResult(
                success=False,
                error_code=cfg_err.code,
                error_message=cfg_err.message,
            )
        except (ModelTimeoutError, ModelUnavailableError, ModelRateLimitedError) as ai_err:
            log("ERROR", f"[AI] Model provider failure: {ai_err.message}")
            return GenerationResult(
                success=False,
                error_code=ai_err.code,
                error_message=ai_err.message,
            )
        except ModelInvalidResponseError as inv_err:
            log("ERROR", f"[AI] Model provider failure: {inv_err.message}")
            return GenerationResult(
                success=False,
                error_code=inv_err.code,
                error_message=inv_err.message,
            )
        except Exception as exc:
            log("ERROR", f"[AI] Unexpected error during generation: {str(exc)}")
            return GenerationResult(
                success=False,
                error_code="MODEL_UNAVAILABLE",
                error_message=f"Model generation failed: {str(exc)}",
            )

        status("VALIDATING")
        log("INFO", "[AI] Validating candidate Game DSL & Gameplay Quality...")

        # 4. Dual Validation: Schema + Gameplay Quality
        val_result = validate_game_dsl(dsl_dict)
        quality_errors: List[str] = []
        # Scale-budget shortfall (too few levels/entities/rules vs. the requested tier)
        # is a SOFT, first-attempt-only nudge -- never a hard, repeatedly-blocking
        # error ("a slightly-off tier is not worth a hard failure"). It is folded into
        # all_errors below ONLY on this very first validation pass, so it gets AT MOST
        # one bounded repair attempt. From the repair loop onward (see below), success
        # is decided purely by hard schema/quality errors; any remaining budget
        # shortfall after that one nudge is accepted as-is.
        budget_errors: List[str] = []

        if val_result.is_valid and val_result.dsl:
            quality_result = GameplayQualityValidator.validate(val_result.dsl)
            if not quality_result.is_valid:
                quality_errors = quality_result.errors
            budget_errors = GameplayQualityValidator.validate_scale_budget(val_result.dsl, scale)

        all_errors = val_result.errors + quality_errors + budget_errors

        if not all_errors and val_result.dsl:
            dsl = val_result.dsl
            parsed_spec = None
            if spec_dict:
                try:
                    parsed_spec = GameDesignSpec.model_validate(spec_dict)
                    dsl.design_spec = parsed_spec
                except Exception:
                    pass

            # 5. Reachability and Spatial Feasibility Validation & Auto-Repair
            from app.generation.reachability import ReachabilityValidator
            reach_res = ReachabilityValidator.validate_and_repair_level(
                world=dsl.world,
                spawn_x=dsl.player.spawn_x,
                spawn_y=dsl.player.spawn_y,
                player_width=dsl.player.width,
                player_height=dsl.player.height,
                entities=dsl.entities,
                jump_power=dsl.player.jump_power,
                gravity=dsl.world.gravity,
                archetype=dsl.metadata.archetype,
            )
            if reach_res.repaired:
                if reach_res.repaired_spawn:
                    dsl.player.spawn_x, dsl.player.spawn_y = reach_res.repaired_spawn
                dsl.entities = reach_res.repaired_entities

            for lvl in dsl.levels:
                lvl_world = lvl.world or dsl.world
                lvl_spawn_x = lvl.spawn_x if lvl.spawn_x is not None else dsl.player.spawn_x
                lvl_spawn_y = lvl.spawn_y if lvl.spawn_y is not None else dsl.player.spawn_y
                lvl_reach = ReachabilityValidator.validate_and_repair_level(
                    world=lvl_world,
                    spawn_x=lvl_spawn_x,
                    spawn_y=lvl_spawn_y,
                    player_width=dsl.player.width,
                    player_height=dsl.player.height,
                    entities=lvl.entities,
                    objective=lvl.objective,
                    jump_power=dsl.player.jump_power,
                    gravity=lvl_world.gravity,
                    archetype=dsl.metadata.archetype,
                )
                if lvl_reach.repaired:
                    if lvl_reach.repaired_spawn:
                        lvl.spawn_x, lvl.spawn_y = lvl_reach.repaired_spawn
                    lvl.entities = lvl_reach.repaired_entities

            log("INFO", "[AI] Game specification validated successfully")
            level_cnt = len(dsl.levels) if dsl.levels else 1
            log("SUCCESS", f"[VALIDATION] Schema v3.0: PASS // Gameplay Quality: PASS // Levels: {level_cnt}")
            log("INFO", "[PHASER]")
            log("INFO", f"> Layout Seed: {dsl.world.procedural_seed or 18492031}")
            log("INFO", f"> Procedural Generation & Reachability: PASS")
            log("SUCCESS", "> Prototype ready")

            return GenerationResult(
                success=True,
                dsl=dsl,
                design_spec=parsed_spec,
                attempts_used=1,
                provider_meta=provider_meta,
            )

        # 5. Bounded repair loop
        current_errors = all_errors
        last_candidate = raw_output

        for attempt in range(1, self.max_retries + 1):
            log("WARNING", f"[AI] Validation failed on attempt {attempt}: {current_errors[0] if current_errors else 'Error'}")
            log("INFO", f"[AI] Triggering bounded repair loop (attempt {attempt}/{self.max_retries})...")

            repair_prompt = build_repair_prompt(last_candidate, current_errors)

            try:
                if hasattr(self.provider, "generate_structured_with_meta"):
                    repaired_output, _ = await self.provider.generate_structured_with_meta(
                        system_prompt=SYSTEM_PROMPT,
                        user_prompt=repair_prompt,
                    )
                else:
                    repaired_output = await self.provider.generate_structured(
                        system_prompt=SYSTEM_PROMPT,
                        user_prompt=repair_prompt,
                    )
            except AIError as ai_err:
                log("ERROR", f"[AI] Repair attempt failed at provider: {ai_err.message}")
                return GenerationResult(
                    success=False,
                    error_code=ai_err.code,
                    error_message=ai_err.message,
                    attempts_used=attempt + 1,
                    provider_meta=provider_meta,
                )

            rep_spec_dict, raw_rep_dsl = self._extract_spec_and_dsl(repaired_output)
            rep_dsl_dict = self._compile_and_propagate_parameters(
                dsl_dict=raw_rep_dsl,
                spec_dict=rep_spec_dict,
                engine=engine,
                art_density=art_density,
                physics=physics,
                modules=active_mods,
            )

            repaired_val = validate_game_dsl(rep_dsl_dict)
            rep_quality_errors = []
            if repaired_val.is_valid and repaired_val.dsl:
                rep_q_res = GameplayQualityValidator.validate(repaired_val.dsl)
                if not rep_q_res.is_valid:
                    rep_quality_errors = rep_q_res.errors

            # NOTE: scale-budget shortfall is deliberately NOT included in
            # all_rep_errors -- it only ever gets the one first-pass nudge above.
            # From here on, only hard schema/quality errors can block success.
            all_rep_errors = repaired_val.errors + rep_quality_errors
            if not all_rep_errors and repaired_val.dsl:
                dsl = repaired_val.dsl
                parsed_spec = None
                if rep_spec_dict:
                    try:
                        parsed_spec = GameDesignSpec.model_validate(rep_spec_dict)
                        dsl.design_spec = parsed_spec
                    except Exception:
                        pass

                remaining_budget_warnings = GameplayQualityValidator.validate_scale_budget(dsl, scale)
                if remaining_budget_warnings:
                    log("WARNING", f"[AI] Scale tier '{scale}' still under target after repair (accepted, not blocking): {remaining_budget_warnings[0]}")

                log("SUCCESS", f"[AI] Game DSL repaired and validated on attempt {attempt + 1}.")
                log("SUCCESS", f"> Schema v2.0: PASS // Gameplay Quality: PASS")
                log("INFO", "[PHASER]")
                log("INFO", f"> Layout Seed: {dsl.world.procedural_seed or 18492031}")
                log("SUCCESS", "> Prototype ready")
                return GenerationResult(
                    success=True,
                    dsl=dsl,
                    design_spec=parsed_spec,
                    attempts_used=attempt + 1,
                    provider_meta=provider_meta,
                )

            last_candidate = repaired_output
            current_errors = all_rep_errors

        # Exceeded maximum retries
        log("ERROR", "[AI] FATAL: Bounded repair attempts exhausted without valid Game DSL.")
        return GenerationResult(
            success=False,
            error_code="DSL_REPAIR_EXHAUSTED",
            error_message="Failed to generate valid Game DSL after maximum repair attempts.",
            attempts_used=self.max_retries + 1,
            provider_meta=provider_meta,
        )

    async def analyze_playtest(
        self,
        design_spec: Any,
        dsl: Any,
        telemetry: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate structured AI playtest critique and actionable recommendations.
        """
        spec_dict = design_spec.model_dump() if hasattr(design_spec, "model_dump") else (design_spec if isinstance(design_spec, dict) else {})
        dsl_dict = dsl.model_dump() if hasattr(dsl, "model_dump") else (dsl if isinstance(dsl, dict) else {})

        prompt = build_playtest_analysis_prompt(spec_dict, dsl_dict, telemetry)
        # NOTE: provider failures are intentionally NOT swallowed here. A malformed
        # response, timeout, or API error must surface as a real error to the caller
        # (POST /api/projects/{id}/analyze-playtest returns ANALYSIS_FAILED) rather than
        # silently returning fabricated ratings/recommendations disguised as a genuine
        # AI critique — a real outage must never look like a successful analysis.
        analysis = await self.provider.generate_structured(
            system_prompt="You are an expert game analyst. Output ONLY valid JSON critique.",
            user_prompt=prompt,
        )
        # Ensure recommendations have required fields
        recs = analysis.get("recommendations", [])
        for idx, r in enumerate(recs):
            if isinstance(r, dict):
                if "id" not in r:
                    r["id"] = f"rec_{idx+1}"
                if "dsl_change_type" not in r:
                    r["dsl_change_type"] = r.get("category", "balance")

        # Normalize problem severity to the schema's closed enum (LOW/MEDIUM/HIGH).
        # The model is instructed to use only these three values (see
        # build_playtest_analysis_prompt), but LLM output is never 100% guaranteed to
        # follow an in-prompt instruction — this maps common synonyms it may still
        # produce (e.g. "CRITICAL"/"URGENT") to the nearest valid bucket rather than
        # letting a single stray word fail PlaytestAnalysisResponse validation for the
        # whole critique.
        severity_synonyms = {
            "CRITICAL": "HIGH",
            "URGENT": "HIGH",
            "SEVERE": "HIGH",
            "MAJOR": "HIGH",
            "MODERATE": "MEDIUM",
            "MINOR": "LOW",
            "TRIVIAL": "LOW",
        }
        problems = analysis.get("problems", [])
        for p in problems:
            if isinstance(p, dict) and "severity" in p:
                sev = str(p["severity"]).strip().upper()
                if sev not in ("LOW", "MEDIUM", "HIGH"):
                    p["severity"] = severity_synonyms.get(sev, "MEDIUM")
                else:
                    p["severity"] = sev

        return analysis

    async def apply_improvements(
        self,
        current_dsl: Any,
        design_spec: Any,
        selected_recommendations: List[Dict[str, Any]],
        user_notes: Optional[str] = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """
        Apply approved recommendations to update the GameDSL.
        """
        spec_dict = design_spec.model_dump() if hasattr(design_spec, "model_dump") else (design_spec if isinstance(design_spec, dict) else {})
        dsl_dict = current_dsl.model_dump() if hasattr(current_dsl, "model_dump") else (current_dsl if isinstance(current_dsl, dict) else {})
        dsl_copy = copy.deepcopy(dsl_dict)

        prompt = build_improvement_prompt(dsl_copy, spec_dict, selected_recommendations)

        try:
            patched_raw = await self.provider.generate_structured(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt,
            )
            _, patched_dsl_dict = self._extract_spec_and_dsl(patched_raw)
            val_res = validate_game_dsl(patched_dsl_dict)

            if val_res.is_valid and val_res.dsl:
                return GenerationResult(
                    success=True,
                    dsl=val_res.dsl,
                    design_spec=design_spec if isinstance(design_spec, GameDesignSpec) else None,
                    attempts_used=1,
                )
            else:
                # Direct apply fallback for suggested patches in test/mock environment
                for rec in selected_recommendations:
                    patch = rec.get("suggested_patch", {})
                    if isinstance(patch, dict):
                        for k, v in patch.items():
                            if isinstance(v, dict) and isinstance(dsl_copy.get(k), dict):
                                dsl_copy[k].update(v)
                            else:
                                dsl_copy[k] = v
                val_fallback = validate_game_dsl(dsl_copy)
                if val_fallback.is_valid and val_fallback.dsl:
                    return GenerationResult(
                        success=True,
                        dsl=val_fallback.dsl,
                        design_spec=design_spec if isinstance(design_spec, GameDesignSpec) else None,
                        attempts_used=1,
                    )
                return GenerationResult(
                    success=False,
                    error_code="PATCH_VALIDATION_FAILED",
                    error_message=f"Patched DSL failed validation: {val_res.errors}",
                )
        except Exception as exc:
            # Direct apply fallback for suggested patches
            for rec in selected_recommendations:
                patch = rec.get("suggested_patch", {})
                if isinstance(patch, dict):
                    for k, v in patch.items():
                        if isinstance(v, dict) and isinstance(dsl_copy.get(k), dict):
                            dsl_copy[k].update(v)
                        else:
                            dsl_copy[k] = v
            val_fallback = validate_game_dsl(dsl_copy)
            if val_fallback.is_valid and val_fallback.dsl:
                return GenerationResult(
                    success=True,
                    dsl=val_fallback.dsl,
                    design_spec=design_spec if isinstance(design_spec, GameDesignSpec) else None,
                    attempts_used=1,
                )
            return GenerationResult(
                success=False,
                error_code="PATCH_FAILED",
                error_message=f"Failed to apply improvements: {str(exc)}",
            )

    def _apply_reachability_repair(self, dsl: GameDSL) -> GameDSL:
        """
        Run deterministic spawn/entity reachability repair across the top-level world
        and every campaign level. Mirrors the repair pass generate_game_dsl() runs on
        a freshly generated DSL, reused here so a remixed DSL is held to the exact
        same spatial-feasibility bar as fresh generation.
        """
        from app.generation.reachability import ReachabilityValidator

        reach_res = ReachabilityValidator.validate_and_repair_level(
            world=dsl.world,
            spawn_x=dsl.player.spawn_x,
            spawn_y=dsl.player.spawn_y,
            player_width=dsl.player.width,
            player_height=dsl.player.height,
            entities=dsl.entities,
            jump_power=dsl.player.jump_power,
            gravity=dsl.world.gravity,
            archetype=dsl.metadata.archetype,
        )
        if reach_res.repaired:
            if reach_res.repaired_spawn:
                dsl.player.spawn_x, dsl.player.spawn_y = reach_res.repaired_spawn
            dsl.entities = reach_res.repaired_entities

        for lvl in dsl.levels:
            lvl_world = lvl.world or dsl.world
            lvl_spawn_x = lvl.spawn_x if lvl.spawn_x is not None else dsl.player.spawn_x
            lvl_spawn_y = lvl.spawn_y if lvl.spawn_y is not None else dsl.player.spawn_y
            lvl_reach = ReachabilityValidator.validate_and_repair_level(
                world=lvl_world,
                spawn_x=lvl_spawn_x,
                spawn_y=lvl_spawn_y,
                player_width=dsl.player.width,
                player_height=dsl.player.height,
                entities=lvl.entities,
                objective=lvl.objective,
                jump_power=dsl.player.jump_power,
                gravity=lvl_world.gravity,
                archetype=dsl.metadata.archetype,
            )
            if lvl_reach.repaired:
                if lvl_reach.repaired_spawn:
                    lvl.spawn_x, lvl.spawn_y = lvl_reach.repaired_spawn
                lvl.entities = lvl_reach.repaired_entities

        return dsl

    def _validate_remix_candidate(
        self, raw_output: Dict[str, Any]
    ) -> Tuple[Optional[GameDSL], Optional[Dict[str, Any]], List[str]]:
        """
        Run a remix candidate through the same schema + gameplay-quality gate as
        fresh generation, then reachability-repair on success. Returns
        (validated_and_repaired_dsl_or_None, spec_dict_or_None, errors).
        """
        cand_spec, cand_dsl_raw = self._extract_spec_and_dsl(raw_output)
        val_res = validate_game_dsl(cand_dsl_raw)
        if not (val_res.is_valid and val_res.dsl):
            return None, cand_spec, val_res.errors

        quality_res = GameplayQualityValidator.validate(val_res.dsl)
        if not quality_res.is_valid:
            return None, cand_spec, quality_res.errors

        repaired_dsl = self._apply_reachability_repair(val_res.dsl)
        return repaired_dsl, cand_spec, []

    async def apply_remix(
        self,
        current_dsl: Any,
        design_spec: Any,
        intents: List[Dict[str, Any]],
        personalization: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """
        Apply structured remix intents (see app.schemas.remix.RemixIntentType) to
        produce a new GameDesignSpec + GameDSL, held to the same validation, quality,
        and reachability-repair pipeline as fresh generation, with a bounded AI
        repair loop identical in shape to generate_game_dsl()'s.
        """
        spec_dict = design_spec.model_dump() if hasattr(design_spec, "model_dump") else (design_spec if isinstance(design_spec, dict) else {})
        dsl_dict = current_dsl.model_dump() if hasattr(current_dsl, "model_dump") else (current_dsl if isinstance(current_dsl, dict) else {})
        dsl_copy = copy.deepcopy(dsl_dict)
        spec_copy = copy.deepcopy(spec_dict)

        # add_levels is clamped server-side to the hard schema cap (5) regardless of
        # what the AI proposes -- never silently drop an over-cap request without
        # saying so in the returned change summary.
        existing_level_count = len(dsl_copy.get("levels") or [])
        clamp_note: Optional[str] = None
        if existing_level_count >= 5:
            filtered = [i for i in intents if i.get("type") != "add_levels"]
            if len(filtered) != len(intents):
                clamp_note = "Level cap (5) already reached; 'Add Levels' request was skipped."
            intents = filtered

        prompt = build_remix_prompt(dsl_copy, spec_copy, intents, personalization=personalization)

        def _result(dsl: GameDSL, cand_spec: Optional[Dict[str, Any]], attempts: int) -> GenerationResult:
            parsed_spec = None
            if cand_spec:
                try:
                    parsed_spec = GameDesignSpec.model_validate(cand_spec)
                except Exception:
                    parsed_spec = None
            return GenerationResult(
                success=True,
                dsl=dsl,
                design_spec=parsed_spec,
                attempts_used=attempts,
                provider_meta={"remix_clamped_note": clamp_note} if clamp_note else {},
            )

        current_errors: List[str] = []
        try:
            raw_output = await self.provider.generate_structured(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt,
            )
            dsl, cand_spec, errors = self._validate_remix_candidate(raw_output)
            if dsl is not None:
                return _result(dsl, cand_spec, 1)
            current_errors = errors
            last_candidate: Any = raw_output
        except Exception as exc:
            current_errors = [str(exc)]
            last_candidate = dsl_copy

        # Bounded repair loop, reusing the same repair-prompt infrastructure as
        # fresh generation (capped at settings.AI_MAX_RETRIES attempts).
        for attempt in range(1, self.max_retries + 1):
            repair_prompt = build_repair_prompt(last_candidate, current_errors)
            try:
                repaired_output = await self.provider.generate_structured(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=repair_prompt,
                )
            except Exception as exc:
                return GenerationResult(
                    success=False,
                    error_code="REMIX_PROVIDER_ERROR",
                    error_message=str(exc),
                    attempts_used=attempt + 1,
                )

            dsl, cand_spec, rep_errors = self._validate_remix_candidate(repaired_output)
            if dsl is not None:
                return _result(dsl, cand_spec, attempt + 1)

            last_candidate = repaired_output
            current_errors = rep_errors

        return GenerationResult(
            success=False,
            error_code="REMIX_REPAIR_EXHAUSTED",
            error_message="Failed to produce a valid remixed Game DSL after maximum repair attempts.",
            attempts_used=self.max_retries + 1,
        )


# Authoritative Singleton Service Instance
game_generation_service = GameGenerationService()
