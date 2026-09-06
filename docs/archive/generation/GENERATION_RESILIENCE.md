# GameForge AI — Game Generation Resilience & Hardening V1

## Executive Summary

The Game Generation Resilience V1 system eliminates costly and slow LLM repair loops (which previously incurred 150-second timeouts) caused by harmless schema drift, malformed AI output wrappers, legacy aliases, and safe scalar format differences.

Deterministic normalization and sanitization are handled locally before strict schema validation, while maintaining closed-world Pydantic validation (`extra="forbid"`) and strict security boundaries against executable code injection.

---

## Generation Pipeline Architecture

```text
RAW AI OUTPUT
      ↓
STAGE 1: PARSING & SECURITY SCANNING
- Extract JSON from markdown fences (```json ... ```), thought tags (<thought>), or wrappers
- Security scanner: check for unsafe keys (runtime_script, javascript, eval, exec) & script injections (<script>, javascript:)
- Unsafe payloads immediately rejected with UNSAFE_DSL_PAYLOAD (0 LLM repair calls)
      ↓
STAGE 2: DETERMINISTIC NORMALIZATION (dsl_normalizer.py)
- Level world migration: maps levels[i].width/height/gravity directly into levels[i].world
- Known safe non-schema field stripping (e.g. density, seed, lives, tags, comments)
- Legacy alias normalization (spawn_x <- x, max_health <- health, points <- score/val)
- Scalar coercion (string numbers -> ints/floats, hex color formatting)
- Entity type & behavior synonym mapping
      ↓
STAGE 3: STRICT PYDANTIC VALIDATION (validator.py)
- GameDSL.model_validate(normalized) with extra="forbid"
- Strict type, range, and closed enum validation
      ↓
STAGE 4: GAMEPLAY QUALITY & SCALE BUDGET (quality_validator.py)
- Minimum entity counts, rule existence, spawn clearance, spatial feasibility
      ↓
STAGE 5: BOUNDED SEMANTIC REPAIR LOOP (game_generation_service.py)
- Triggered ONLY when genuine semantic repair is required
- Bounded to max 1 repair attempt (AI_REPAIR_MAX_ATTEMPTS = 1)
- Dedicated shorter timeout (AI_REPAIR_TIMEOUT_SECONDS = 45.0s)
- Preserves full error context if repair fails
      ↓
STAGE 6: PROCEDURAL PHASER RUNTIME & VERSION PERSISTENCE
```

---

## Key Components

### 1. `backend/app/generation/dsl_normalizer.py`
Dedicated normalizer and security scanner implementing:
- `check_for_unsafe_content(data, path)`: Recursively scans keys and string values for malicious script execution patterns and prohibited keys.
- `clean_json_text(text)`: Strips markdown code blocks, XML thought tags, and surrounding commentary.
- `normalize_levels(raw, issues)`: Migrates level-placed world properties (`levels[i].width`, `height`, `gravity`, etc.) into `levels[i].world`.
- `normalize_open_world(raw, issues)`: Strips safe schema drift from regions, POIs, actors, vehicles, activities, threat and time systems.
- `normalize(raw)`: Returns `(normalized_dict, List[ValidationIssue])`.

### 2. `backend/app/generation/validator.py`
Integrates `DSLNormalizer` as Stage 1 before `GameDSL.model_validate()`. Emits structured `ValidationIssue` objects classified by repairability (`DETERMINISTIC`, `SEMANTIC`, `UNSAFE`).

### 3. `backend/app/config.py` & Providers
- `AI_REPAIR_TIMEOUT_SECONDS: float = 45.0`
- `AI_REPAIR_MAX_ATTEMPTS: int = 1`
- `AIProvider.generate_structured(..., timeout=...)` & `generate_structured_with_meta(..., timeout=...)` allow targeted timeout overrides without changing standard generation timeouts.

### 4. `backend/app/services/game_generation_service.py`
- Fast fail on security violations (`UNSAFE_DSL_PAYLOAD`) with zero repair calls.
- Fast pass on deterministic schema drift (0 repair provider calls).
- Dedicated 45.0s timeout on semantic repair attempts.
- Graceful error preservation on provider failure or timeout.

---

## Verification & Test Evidence

### Dedicated Test Suite: `backend/tests/test_generation_resilience.py` (10 / 10 Passing)
1. `test_normalizer_recovers_levels_width_deterministically`: Verifies local recovery of `levels[0].width` into `levels[0].world.width`.
2. `test_generation_pipeline_zero_repair_calls_on_levels_width`: Asserted `attempts_used == 1` and `mock_provider.call_count == 1` (0 repair calls).
3. `test_generation_pipeline_short_circuits_on_unsafe_payload_no_repair`: Verified `UNSAFE_DSL_PAYLOAD` returns on attempt 1 with 0 repair calls.
4. `test_semantic_repair_triggers_once_with_dedicated_repair_timeout`: Verified semantic errors invoke at most 1 repair with `timeout=45.0s`.
5. `test_repair_provider_timeout_preserves_original_error_and_fails_gracefully`: Verified timeout logs original validation error and fails gracefully.
6. `test_legacy_aliases_and_scalar_coercion`: Verified numeric strings, hex colors, and legacy aliases normalize cleanly.
7. `test_markdown_codeblock_stripping`: Verified ` ```json ` fences and wrappers extract cleanly.
8. `test_unsafe_runtime_script_is_rejected_never_silently_dropped`: Verified `runtime_script` is flagged as unsafe and never ignored.
9. `test_script_tag_injection_in_text_field_rejected`: Verified `<script>` in strings triggers `UNSAFE_CONTENT`.
10. `test_open_world_safe_drift_normalization`: Verified Open World safe schema drift cleans deterministically.

### Full Test Suite
- **Backend Tests**: `360 passed, 0 failed` in `pytest tests/ -q`
- **Frontend Build**: `tsc -b && vite build` succeeded with 0 errors
