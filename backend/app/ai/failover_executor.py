"""
Central failover executor for all Gemini AI requests.

Architecture
============
For each request, the executor iterates:

  Model chain (task-specific)
    └─ Eligible credentials (configured order, skipping cooldown)
         └─ Attempt → classify error → record health → decision

Decision table:
  KEY_AUTH_FAILURE  → record failure → try next credential
  RATE_LIMIT        → record failure → try next credential
  TRANSIENT_PROVIDER → record failure → try next credential
  NETWORK_ERROR     → record failure → try next credential
  UNKNOWN           → record failure → try next credential (once per key)
  MODEL_UNAVAILABLE → do NOT charge credential; try next MODEL (not next key)
  INVALID_REQUEST   → raise immediately; no credential/model cycling
  CONTENT_SAFETY    → raise immediately; no cycling
  SCHEMA_PARSING    → raise immediately; no cycling

Outer loop (models): exhausting all credentials for model N triggers model N+1.
Inner loop (keys): try Key 1, then Key 2, ... until success or all exhausted.

STOP immediately on first success.

Key behavior
============
- Key 1 is ALWAYS tried first.
- Key 1 is used for EVERY request when healthy (no proactive rotation).
- The next key is tried ONLY on an eligible failure.
- There is NO round-robin, NO random selection, NO cycling on success.

Safety invariants
=================
- Raw API key strings are NEVER written to logs, stored in the database, or
  returned in API responses.  Only key_index (1-based for display) and
  masked_key (last 4 chars) appear in logs.
- No credential details are included in FailoverResult metadata.
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

    def to_provider_meta(self) -> Dict[str, Any]:
        """Return safe, non-credential metadata suitable for service layer / SSE logs."""
        return {
            "provider": "gemini",
            "model": self.model_used,
            "provider_display_name": "Google Gemini",
            "model_display_name": self.model_used,
            "fallback_used": (self.key_fallbacks_used + self.model_fallbacks_used) > 0,
            "fallback_reason": (
                self.error_class_on_fallback[-1] if self.error_class_on_fallback else None
            ),
            "key_fallbacks": self.key_fallbacks_used,
            "model_fallbacks": self.model_fallbacks_used,
        }


async def execute_with_failover(
    task_type: TaskType,
    system_prompt: str,
    user_prompt: str,
    json_schema: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
    overall_deadline: Optional[float] = None,
    registry: Optional[GeminiKeyRegistry] = None,
) -> FailoverResult:
    """
    Execute a structured AI request using sequential credential failover and
    task-based model routing.

    Parameters
    ----------
    task_type:
        The TaskType enum value — determines the model chain.
    system_prompt:
        System instruction prompt (not logged by this layer).
    user_prompt:
        User/generation prompt (not logged by this layer).
    json_schema:
        Optional JSON schema hint; passed through to GeminiProvider.
    timeout:
        Per-attempt HTTP timeout in seconds.  Defaults to settings.AI_TIMEOUT_SECONDS.
    overall_deadline:
        Maximum total wall-clock seconds across ALL attempts.
        Defaults to settings.AI_OVERALL_DEADLINE_SECONDS.
    registry:
        Credential registry to use; defaults to the global singleton.

    Returns
    -------
    FailoverResult

    Raises
    ------
    AIError or subclass on terminal failures.
    """
    # Import here to avoid circular import at module load time
    from app.ai.hosted_provider import GeminiProvider

    reg = registry if registry is not None else gemini_key_registry
    per_attempt_timeout = timeout or settings.AI_TIMEOUT_SECONDS
    deadline_secs = overall_deadline or settings.AI_OVERALL_DEADLINE_SECONDS
    model_chain = resolve_model_chain(task_type)

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
        eligible_keys = reg.get_eligible_keys()

        if not eligible_keys:
            # All credentials in cooldown — skip to next model (or fail)
            log.warning(
                "[AI] TASK: %s | MODEL: %s | All credentials in cooldown — skipping to next model.",
                task_type.value, model,
            )
            model_fallbacks += 1
            continue

        model_had_eligible_error = False  # Did any key give us a key-failover-eligible error?

        for key_idx, key in eligible_keys:
            # Deadline check before each attempt
            elapsed = time.monotonic() - start_ts
            if elapsed >= deadline_secs:
                log.warning(
                    "[AI] TASK: %s | Overall deadline of %.0fs exceeded after %.1fs — aborting.",
                    task_type.value, deadline_secs, elapsed,
                )
                raise ModelUnavailableError(
                    f"AI generation exceeded overall deadline of {deadline_secs:.0f}s after {elapsed:.1f}s."
                )

            remaining = deadline_secs - elapsed
            attempt_timeout = min(per_attempt_timeout, remaining)
            attempts_total += 1

            log.info(
                "[AI] TASK: %s | MODEL: %s | KEY: #%d | ATTEMPT: %d",
                task_type.value, model, key_idx + 1, attempts_total,
            )

            try:
                provider = GeminiProvider(
                    api_key=key,
                    model=model,
                    timeout=attempt_timeout,
                )
                result_dict, _meta = await provider.generate_structured_with_meta(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    json_schema=json_schema,
                    timeout=attempt_timeout,
                )
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

                # MODEL_UNAVAILABLE — charge the model, not the credential
                if error_class == ProviderErrorClass.MODEL_UNAVAILABLE:
                    log.warning(
                        "[AI] TASK: %s | MODEL: %s | MODEL_UNAVAILABLE — "
                        "will try next model (credential #%d NOT penalised).",
                        task_type.value, model, key_idx + 1,
                    )
                    model_had_eligible_error = True
                    fallback_reasons.append(error_class.value)
                    model_fallbacks += 1
                    break  # Break inner key loop → next model

                # Credential-eligible failures: record health + try next key
                if is_credential_failover_eligible(error_class):
                    await reg.record_failure(key_idx, error_class)
                    key_fallbacks += 1
                    model_had_eligible_error = True
                    fallback_reasons.append(error_class.value)
                    # Log failover intent
                    eligible_remaining = [
                        (i, k) for (i, k) in reg.get_eligible_keys() if i != key_idx
                    ]
                    if eligible_remaining:
                        next_key_idx = eligible_remaining[0][0]
                        log.info(
                            "[AI] FAILOVER: KEY #%d → KEY #%d (reason: %s)",
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

        # All eligible keys exhausted for this model → log and advance to next model
        if model_idx < len(model_chain) - 1:
            next_model = model_chain[model_idx + 1]
            model_fallbacks += 1
            log.warning(
                "[AI] TASK: %s | MODEL: %s credentials exhausted — "
                "FALLBACK → MODEL: %s | KEY: #1",
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
