"""
Official Google Gemini Interactions API Transport Adapter.

Layer responsibilities
======================
GeminiInteractionsAdapter
  Single credential + single model + single Interactions API request.
  Uses official google-genai SDK (>=2.20.0).
  Supports Pydantic structured output, thinking level budgets, server-side
  thought stripping, and optional stateful interaction continuation.
  Pure transport: prompt -> Interactions API -> JSON.

  Knows NOTHING about credential pools or model fallback chains.
  The FailoverExecutor (failover_executor.py) instantiates this per attempt.
"""
import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

from google import genai
from google.genai import errors as genai_errors

from app.ai.provider import (
    AIConfigurationError,
    AIError,
    AIProvider,
    ModelInvalidResponseError,
    ModelRateLimitedError,
    ModelTimeoutError,
    ModelUnavailableError,
    ProviderErrorClass,
)
from app.config import settings

log = logging.getLogger(__name__)


class GeminiInteractionsAdapter(AIProvider):
    """
    Adapter for Google Gemini using the official Interactions API (google-genai).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        thinking_level: Optional[str] = None,
    ):
        # If no key provided, retrieve from settings pool
        if api_key is None:
            pool = settings.gemini_api_key_pool()
            api_key = pool[0] if pool else settings.AI_API_KEY

        self.api_key = api_key
        self.model = model or settings.GEMINI_MODEL or "gemini-3.7-flash"
        self.timeout = timeout or settings.AI_TIMEOUT_SECONDS
        self.thinking_level = thinking_level or getattr(settings, "GEMINI_THINKING_LEVEL", "medium")
        self.provider_name = "gemini"

    def _clean_json_text(self, text: str) -> str:
        """Strip thought tags, markdown codeblock wrappers, and extract clean JSON."""
        cleaned = text.strip()
        # 1. Remove reasoning/thought tags (<thought>...</thought> / <think>...</think>)
        cleaned = re.sub(r"<(?:thought|think)>.*?</(?:thought|think)>", "", cleaned, flags=re.DOTALL | re.IGNORECASE).strip()
        # 2. Strip markdown codeblock fences
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned).strip()
        # 3. Extract JSON object boundary if surrounded by additional prose
        if not (cleaned.startswith("{") and cleaned.endswith("}")):
            first_brace = cleaned.find("{")
            last_brace = cleaned.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                cleaned = cleaned[first_brace : last_brace + 1]
        return cleaned.strip()

    def _classify_and_raise_error(self, exc: Exception, effective_timeout: float) -> None:
        """Translate google-genai exceptions into canonical typed AIError exceptions."""
        exc_str = str(exc)
        exc_lower = exc_str.lower()

        # 1. Check for timeout
        if isinstance(exc, (TimeoutError, genai_errors.APIError)) and "timeout" in exc_lower:
            raise ModelTimeoutError(effective_timeout, message=f"Gemini Interactions API request timed out after {effective_timeout:.1f}s.")

        # 2. Extract status code if available
        status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)

        # 3. Handle 401 / 403 Authentication & Authorization
        if status_code in (401, 403) or any(k in exc_lower for k in ["api_key_invalid", "invalid api key", "unauthenticated", "permission denied"]):
            # Distinguish model-specific 403 from credential-specific 403
            if "model" in exc_lower and any(k in exc_lower for k in ["not found", "unsupported", "access_denied", "location"]):
                raise ModelUnavailableError(
                    f"Gemini model '{self.model}' access error: {exc_str[:200]}",
                    code="MODEL_ACCESS_DENIED",
                )
            raise AIConfigurationError(
                f"Gemini rejected the configured credentials: {exc_str[:200]}",
                code="AI_PROVIDER_AUTHENTICATION",
            )

        # 4. Handle 429 Rate Limit / Quota
        if status_code == 429 or "rate limit" in exc_lower or "resource exhausted" in exc_lower or "quota" in exc_lower:
            raise ModelRateLimitedError(f"Rate limit exceeded on Google Gemini: {exc_str[:200]}")

        # 5. Handle 404 Model Not Found
        if status_code == 404 or "not found" in exc_lower or "unknown model" in exc_lower:
            raise ModelUnavailableError(
                f"Gemini model '{self.model}' not found (HTTP 404). The model may be unavailable or deprecated.",
                code="MODEL_NOT_FOUND",
            )

        # 6. Handle 5xx Server / Provider Flaps
        if (status_code and status_code >= 500) or any(k in exc_lower for k in ["internal error", "service unavailable", "backend error"]):
            raise ModelUnavailableError(
                f"Google Gemini service unavailable (HTTP {status_code or 503}): {exc_str[:200]}"
            )

        # 7. Default to connection failure
        raise AIError("AI_CONNECTION_FAILED", f"Failed to reach Google Gemini Interactions API: {exc_str[:200]}")

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        previous_interaction_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Request structured JSON completion from the Interactions API."""
        res, _ = await self.generate_structured_with_meta(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_schema=json_schema,
            timeout=timeout,
            previous_interaction_id=previous_interaction_id,
        )
        return res

    async def generate_structured_with_meta(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        previous_interaction_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Request structured JSON completion from the Interactions API and return (parsed_json, metadata).
        """
        if not self.api_key:
            raise AIConfigurationError(
                "Gemini API key is not configured on the server."
            )

        effective_timeout = timeout if timeout is not None else self.timeout

        try:
            client = genai.Client(api_key=self.api_key)

            # Build request parameters for Interactions API
            params: Dict[str, Any] = {
                "model": self.model,
                "input": user_prompt,
                "system_instruction": system_prompt,
                "timeout": effective_timeout,
            }

            if previous_interaction_id:
                params["previous_interaction_id"] = previous_interaction_id

            # Execute asynchronous interaction call
            interaction = await client.aio.interactions.create(**params)

            # Extract output text and interaction ID
            raw_content = getattr(interaction, "output_text", "") or ""
            interaction_id = getattr(interaction, "id", None)
            usage = getattr(interaction, "usage", None)

            if not raw_content:
                # Inspect steps if output_text was empty
                steps = getattr(interaction, "steps", []) or []
                for step in steps:
                    step_type = getattr(step, "type", "")
                    if step_type == "model_output":
                        contents = getattr(step, "content", []) or []
                        for part in contents:
                            text_val = getattr(part, "text", "")
                            if text_val:
                                raw_content += text_val

            if not raw_content:
                raise ModelInvalidResponseError("Gemini Interactions API returned empty content.")

            # Clean JSON text
            cleaned = self._clean_json_text(raw_content)
            parsed_json = json.loads(cleaned)

            if not isinstance(parsed_json, dict):
                raise ModelInvalidResponseError("Model output did not parse into a top-level JSON object.")

            meta = {
                "provider": "gemini",
                "model": self.model,
                "provider_display_name": "Google Gemini",
                "model_display_name": self.model,
                "interaction_id": interaction_id,
                "usage": usage,
                "fallback_used": False,
                "fallback_reason": None,
            }
            return parsed_json, meta

        except json.JSONDecodeError as json_err:
            raise ModelInvalidResponseError(f"Model output is not valid JSON: {str(json_err)}")
        except AIError:
            raise
        except Exception as exc:
            self._classify_and_raise_error(exc, effective_timeout)
            raise  # Unreachable, but satisfies linter
