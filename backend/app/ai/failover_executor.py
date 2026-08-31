"""
Central failover executor for all Gemini AI requests.

Architecture
============
For each request, the executor iterates:

  Model chain (task-specific)
    └─ Eligible credentials (configured order, skipping cooldown)
         └─ Attempt -> classify error -> record health -> decision

Decision table:
  KEY_AUTH_FAILURE  -> record failure -> try next credential
  RATE_LIMIT        -> record failure -> try next credential
  TRANSIENT_PROVIDER -> record failure -> try next credential
  NETWORK_ERROR     -> record failure -> try next credential
  UNKNOWN           -> record failure -> try next credential (once per key)
  MODEL_UNAVAILABLE -> do NOT charge credential; try next MODEL (not next key)
  INVALID_REQUEST   -> raise immediately; no credential/model cycling
  CONTENT_SAFETY    -> raise immediately; no cycling
  SCHEMA_PARSING    -> raise immediately; no cycling

Budgeting & Limits (Approved V1 Rules):
=======================================
1. Dynamic Remaining-Deadline:
   overall_deadline = 60.0s (single wall-clock clock).
   attempt_timeout = min(task_cap, overall_deadline - elapsed).
   If remaining < 3.0s -> abort immediately.
2. Global Interaction Ceiling:
   Hard ceiling of at most 5 total Gemini API calls across all keys, models, and repairs.
3. Pluggable Transport:
   Uses GeminiInteractionsAdapter when AI_TRANSPORT="interactions" (default),
   falling back to GeminiProvider (httpx OpenAI proxy) when AI_TRANSPORT="legacy_http".
4. Safe Logging:
   Raw API key strings are NEVER logged. Only key_index and masked identifiers appear.
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.ai.key_registry import GeminiKeyRegistry, gemini_key_registry
from app.ai.model_router import TaskType, resolve_model_chain
from app.ai.provider import (
    AIConfigurationError,
    AIError,
    ModelInvalidResponseError,
    ModelTimeoutError,
    ModelUnavailableError,
    ProviderErrorClass,
    classify_ai_error,
    is_credential_failover_eligible,
    is_model_fallback_eligible,
)
from app.config import settings

log = logging.getLogger(__name__)

# Hard global limit on total Gemini API calls per request lifecycle
MAX_GLOBAL_ATTEMPTS = 5


@dataclass
class FailoverResult:
    """Rich result from a failover-executor request."""
    result: Dict[str, Any]
    model_used: str
    key_index_used: int                   # 0-based internal index
    attempts_total: int
    key_fallbacks_used: int
    model_fallbacks_used: int
    duration_ms: float
    error_class_on_fallback: Optional[List[str]] = field(default_factory=list)
    interaction_id: Optional[str] = None

    def to_provider_meta(self) -> Dict[str, Any]:
        """Return safe, non-credential metadata suitable for service layer / SSE logs."""
        return {
            "provider": "gemini",
            "model": self.model_used,
            "provider_display_name": "Google Gemini",
            "model_display_name": self.model_used,
            "interaction_id": self.interaction_id,
            "fallback_used": (self.key_fallbacks_used + self.model_fallbacks_used) > 0,
            "fallback_reason": (
                self.error_class_on_fallback[-1] if self.error_class_on_fallback else None
            ),
            "key_fallbacks": self.key_fallbacks_used,
            "model_fallbacks": self.model_fallbacks_used,
        }


def _get_task_attempt_cap(task_type: TaskType, explicit_timeout: Optional[float] = None) -> float:
    """Return task-specific attempt timeout cap."""
    if explicit_timeout is not None:
        return explicit_timeout
    if task_type in (TaskType.GAME_GENERATION, TaskType.REMIX, TaskType.BLUEPRINT):
        return 25.0
    if task_type == TaskType.DSL_PATCH:
        return 15.0
    if task_type == TaskType.PLAYTEST_ANALYSIS:
        return 12.0
    return float(settings.AI_TIMEOUT_SECONDS)


async def execute_with_failover(
    task_type: TaskType,
    system_prompt: str,
    user_prompt: str,
    json_schema: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
    overall_deadline: Optional[float] = None,
    registry: Optional[GeminiKeyRegistry] = None,
    previous_interaction_id: Optional[str] = None,
) -> FailoverResult:
    """
    Execute a structured AI request using sequential credential failover,
    task-based model routing, dynamic remaining-deadline budgeting, and
    global request bounding.
    """
    # Import transport adapters dynamically to prevent circular imports
    from app.ai.gemini_interactions_adapter import GeminiInteractionsAdapter
    from app.ai.hosted_provider import GeminiProvider

    reg = registry if registry is not None else gemini_key_registry
    deadline_secs = overall_deadline or float(settings.AI_OVERALL_DEADLINE_SECONDS)
    model_chain = resolve_model_chain(task_type)
    task_cap = _get_task_attempt_cap(task_type, timeout)
    use_interactions = getattr(settings, "AI_TRANSPORT", "interactions") == "interactions"

    if not reg or reg.pool_size == 0:
        raise AIConfigurationError(
            "No Gemini credentials are configured on the server."
        )
    if not model_chain:
        raise AIConfigurationError(
            f"No model chain configured for task type '{task_type.value}'."
        )

    start_ts = time.monotonic()
    attempts_total = 0
    key_fallbacks = 0
    model_fallbacks = 0
    fallback_reasons: List[str] = []
    last_error: Optional[Exception] = None

    for model_idx, model in enumerate(model_chain):
        # Global interaction limit check
        if attempts_total >= MAX_GLOBAL_ATTEMPTS:
            log.warning(
                "[AI] TASK: %s | Global interaction budget of %d reached — aborting model chain.",
                task_type.value, MAX_GLOBAL_ATTEMPTS,
            )
            break

        eligible_keys = reg.get_eligible_keys()

        if not eligible_keys:
            # All credentials in cooldown — skip to next model (or fail)
            log.warning(
                "[AI] TASK: %s | MODEL: %s | All credentials in cooldown — skipping to next model.",
                task_type.value, model,
            )
            model_fallbacks += 1
            continue

        for key_idx, key in eligible_keys:
            # 1. Global interaction limit check
            if attempts_total >= MAX_GLOBAL_ATTEMPTS:
                log.warning(
                    "[AI] TASK: %s | Global interaction budget of %d reached — aborting attempts.",
                    task_type.value, MAX_GLOBAL_ATTEMPTS,
                )
                break

            # 2. Dynamic Remaining-Deadline Check
            elapsed = time.monotonic() - start_ts
            remaining = deadline_secs - elapsed

            if remaining < 3.0:
                log.warning(
                    "[AI] TASK: %s | Insufficient deadline remaining (%.1fs < 3.0s) — aborting.",
                    task_type.value, remaining,
                )
                raise ModelUnavailableError(
                    f"AI generation exceeded remaining deadline ({remaining:.1f}s remaining of {deadline_secs:.0f}s total)."
                )

            # Allocate dynamic attempt timeout capped at the task cap and remaining time
            attempt_timeout = min(task_cap, remaining)
            attempts_total += 1

            log.info(
                "[AI] TASK: %s | MODEL: %s | KEY: #%d | ATTEMPT: %d (Budget: %.1fs remaining)",
                task_type.value, model, key_idx + 1, attempts_total, remaining,
            )

            try:
                # Select transport based on AI_TRANSPORT configuration
                if use_interactions:
                    provider = GeminiInteractionsAdapter(
                        api_key=key,
                        model=model,
                        timeout=attempt_timeout,
                    )
                else:
                    provider = GeminiProvider(
                        api_key=key,
                        model=model,
                        timeout=attempt_timeout,
                    )

                if hasattr(provider, "generate_structured_with_meta"):
                    # Check if previous_interaction_id is accepted
                    try:
                        result_dict, meta = await provider.generate_structured_with_meta(
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            json_schema=json_schema,
                            timeout=attempt_timeout,
                            previous_interaction_id=previous_interaction_id,
                        )
                    except TypeError:
                        result_dict, meta = await provider.generate_structured_with_meta(
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            json_schema=json_schema,
                            timeout=attempt_timeout,
                        )
                else:
                    result_dict = await provider.generate_structured(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        json_schema=json_schema,
                        timeout=attempt_timeout,
                    )
                    meta = {}

                duration_ms = (time.monotonic() - start_ts) * 1000
                await reg.record_success(key_idx)

                log.info(
                    "[AI] TASK: %s | MODEL: %s | KEY: #%d | RESULT: SUCCESS | %.0fms",
                    task_type.value, model, key_idx + 1, duration_ms,
                )

                return FailoverResult(
                    result=result_dict,
                    model_used=model,
                    key_index_used=key_idx,
                    attempts_total=attempts_total,
                    key_fallbacks_used=key_fallbacks,
                    model_fallbacks_used=model_fallbacks,
                    duration_ms=duration_ms,
                    error_class_on_fallback=fallback_reasons,
                    interaction_id=meta.get("interaction_id"),
                )

            except Exception as exc:
                error_class = classify_ai_error(exc)
                last_error = exc

                log.info(
                    "[AI] TASK: %s | MODEL: %s | KEY: #%d | ERROR: %s",
                    task_type.value, model, key_idx + 1, error_class.value,
                )

                # Errors that must fail immediately — no credential or model cycling
                if error_class == ProviderErrorClass.INVALID_REQUEST:
                    log.error(
                        "[AI] TASK: %s | INVALID_REQUEST — failing immediately (no failover). "
                        "Error: %s", task_type.value, str(exc),
                    )
                    raise

                if error_class == ProviderErrorClass.CONTENT_SAFETY:
                    log.warning(
                        "[AI] TASK: %s | CONTENT_SAFETY — failing immediately (no failover).",
                        task_type.value,
                    )
                    raise

                if error_class == ProviderErrorClass.SCHEMA_PARSING:
                    # Provider succeeded; our parser failed.
                    # Surface this directly to the application validation layer.
                    log.warning(
                        "[AI] TASK: %s | SCHEMA_PARSING — routing to GameForge validation path (no failover).",
                        task_type.value,
                    )
                    raise

                # MODEL_UNAVAILABLE / Model Policy 403 — charge the model, not the credential
                if error_class == ProviderErrorClass.MODEL_UNAVAILABLE:
                    log.warning(
                        "[AI] TASK: %s | MODEL: %s | MODEL_UNAVAILABLE — "
                        "will try next model (credential #%d NOT penalized).",
                        task_type.value, model, key_idx + 1,
                    )
                    fallback_reasons.append(error_class.value)
                    model_fallbacks += 1
                    break  # Break inner key loop -> advance to next model

                # Credential-eligible failures: record health + try next key
                if is_credential_failover_eligible(error_class):
                    await reg.record_failure(key_idx, error_class)
                    key_fallbacks += 1
                    fallback_reasons.append(error_class.value)
                    # Log failover intent
                    eligible_remaining = [
                        (i, k) for (i, k) in reg.get_eligible_keys() if i != key_idx
                    ]
                    if eligible_remaining:
                        next_key_idx = eligible_remaining[0][0]
                        log.info(
                            "[AI] FAILOVER: KEY #%d -> KEY #%d (reason: %s)",
                            key_idx + 1, next_key_idx + 1, error_class.value,
                        )
                    else:
                        log.info(
                            "[AI] KEY #%d exhausted; no more eligible keys for MODEL: %s.",
                            key_idx + 1, model,
                        )
                    continue  # Try next key

                # Any other classified error — conservative: record + try next key once
                await reg.record_failure(key_idx, error_class)
                key_fallbacks += 1
                fallback_reasons.append(error_class.value)
                continue

        # All eligible keys exhausted for this model -> log and advance to next model
        if model_idx < len(model_chain) - 1:
            next_model = model_chain[model_idx + 1]
            model_fallbacks += 1
            log.warning(
                "[AI] TASK: %s | MODEL: %s credentials exhausted — "
                "FALLBACK -> MODEL: %s | KEY: #1",
                task_type.value, model, next_model,
            )
            fallback_reasons.append(f"CREDENTIALS_EXHAUSTED_ON_{model}")

    # All models and all credentials exhausted
    duration_ms = (time.monotonic() - start_ts) * 1000
    log.error(
        "[AI] TASK: %s | All provider options exhausted after %d attempt(s), %.0fms.",
        task_type.value, attempts_total, duration_ms,
    )
    if isinstance(last_error, AIError):
        raise last_error
    if last_error is not None:
        raise ModelUnavailableError(
            f"All configured AI providers are unavailable after {attempts_total} attempt(s)."
        ) from last_error
    raise ModelUnavailableError(
        "No AI providers were eligible for this request."
    )
