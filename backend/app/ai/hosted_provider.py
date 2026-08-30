"""
Gemini/Groq AI provider HTTP adapters.

Layer responsibilities
======================
GeminiProvider
  Single credential + single model + single HTTP request.
  Knows NOTHING about credential pools, model chains, or failover policy.
  Pure transport: prompt → HTTP → JSON.

GroqProvider / HostedOpenAIProvider
  Legacy / test-fixture providers.  Same single-request interface.

AIProviderRouter
  Backward-compatible facade used by GameGenerationService.
  Delegates to the central failover executor (failover_executor.py).
  Accepts an optional task_type parameter for task-specific routing.
  When task_type is not provided, defaults to GAME_GENERATION.

Removed in V2
=============
RotatingGeminiProvider — eliminated.  It performed proactive round-robin
rotation on EVERY request, which is the opposite of the desired behavior.
The new architecture keeps Key 1 as the stable primary credential and only
advances to Key 2 on an eligible failure.
"""
import json
import re
from typing import Any, Dict, Optional, Tuple

import httpx

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


class BaseHostedProvider(AIProvider):
    """
    Base adapter for OpenAI-compatible REST API providers (Gemini, Groq, OpenAI).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        provider_name: str = "hosted_provider",
    ):
        self.api_key = api_key
        self.model = model or "default"
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = timeout or settings.AI_TIMEOUT_SECONDS
        self.provider_name = provider_name

    def _clean_json_text(self, text: str) -> str:
        """Strip thought tags, markdown codeblock wrappers, and extract clean JSON."""
        cleaned = text.strip()
        # 1. Remove reasoning/thought tags (e.g. <thought>...</thought> emitted by reasoning models)
        cleaned = re.sub(r"<(?:thought|think)>.*?</(?:thought|think)>", "", cleaned, flags=re.DOTALL | re.IGNORECASE).strip()
        # 2. Strip markdown codeblocks
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned).strip()
        # 3. Extract JSON object boundary if surrounded by other prose
        if not (cleaned.startswith("{") and cleaned.endswith("}")):
            first_brace = cleaned.find("{")
            last_brace = cleaned.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                cleaned = cleaned[first_brace : last_brace + 1]
        return cleaned.strip()

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Request structured JSON completion from the hosted provider endpoint.
        """
        res, _ = await self.generate_structured_with_meta(system_prompt, user_prompt, json_schema, timeout=timeout)
        return res

    async def generate_structured_with_meta(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Request structured JSON completion and return (parsed_json, metadata).
        """
        if not self.api_key:
            raise AIConfigurationError(
                f"{self.provider_name.capitalize()} API key is not configured on the server."
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }

        url = f"{self.base_url}/chat/completions"
        effective_timeout = timeout if timeout is not None else self.timeout

        try:
            async with httpx.AsyncClient(timeout=effective_timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException:
            raise ModelTimeoutError(effective_timeout)
        except httpx.NetworkError as net_err:
            raise ModelUnavailableError(
                f"Network error connecting to {self.provider_name} provider: {str(net_err)}"
            )
        except Exception as exc:
            raise AIError("AI_CONNECTION_FAILED", f"Failed to reach {self.provider_name} provider: {str(exc)}")

        if response.status_code in (401, 403) or (
            response.status_code == 400 and any(msg in response.text.lower() for msg in ["invalid auth key", "api key not valid", "api_key_invalid", "invalid_argument"])
        ):
            raise AIConfigurationError(
                f"{self.provider_name.capitalize()} rejected the configured credentials: {response.text[:200]}",
                code="AI_PROVIDER_AUTHENTICATION",
            )
        elif response.status_code == 429:
            raise ModelRateLimitedError(f"Rate limit exceeded on {self.provider_name} provider.")
        elif response.status_code == 404:
            raise ModelUnavailableError(
                f"{self.provider_name.capitalize()} model '{self.model}' not found (HTTP 404). "
                "The model may be unavailable, deprecated, or the model ID may be incorrect.",
                code="MODEL_NOT_FOUND",
            )
        elif response.status_code >= 500:
            raise ModelUnavailableError(
                f"{self.provider_name.capitalize()} provider returned server error (HTTP {response.status_code})."
            )
        elif response.status_code != 200:
            raise AIError(
                "PROVIDER_HTTP_ERROR",
                f"{self.provider_name.capitalize()} returned unexpected status HTTP {response.status_code}: {response.text[:200]}",
                status_code=response.status_code,
            )

        try:
            res_data = response.json()
            choices = res_data.get("choices", [])
            if not choices:
                raise ModelInvalidResponseError("No completion choices returned by model.")

            raw_content = choices[0].get("message", {}).get("content", "")
            if not raw_content:
                raise ModelInvalidResponseError("Model returned empty content.")

            cleaned = self._clean_json_text(raw_content)
            parsed_json = json.loads(cleaned)
            if not isinstance(parsed_json, dict):
                raise ModelInvalidResponseError("Model output did not parse into a top-level JSON object.")

            provider_display = "Google Gemini" if self.provider_name == "gemini" else self.provider_name.capitalize()
            model_display = self.model

            meta = {
                "provider": self.provider_name,
                "model": self.model,
                "provider_display_name": provider_display,
                "model_display_name": model_display,
                "fallback_used": False,
                "fallback_reason": None,
            }
            return parsed_json, meta

        except json.JSONDecodeError as json_err:
            raise ModelInvalidResponseError(f"Model output is not valid JSON: {str(json_err)}")


class GeminiProvider(BaseHostedProvider):
    """
    Single-credential, single-model Google Gemini HTTP adapter.

    This class handles ONE credential and ONE model per instance.
    It knows nothing about credential pools, model chains, or failover.
    The failover executor (failover_executor.py) instantiates this per attempt.

    The public interface is identical to V1 GeminiProvider so existing test
    mocks that patch GeminiProvider directly continue to work.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        # When api_key is explicitly provided (by the failover executor), use it directly.
        # When api_key is None (legacy / direct instantiation), fall back to the first
        # configured pool key or the legacy GEMINI_API_KEY setting.
        if api_key is None:
            pool = settings.gemini_api_key_pool()
            api_key = pool[0] if pool else settings.AI_API_KEY
        resolved_model = model or settings.GEMINI_MODEL or "gemini-3.6-flash"
        resolved_url = base_url or settings.GEMINI_BASE_URL or "https://generativelanguage.googleapis.com/v1beta/openai"

        super().__init__(
            api_key=api_key,
            model=resolved_model,
            base_url=resolved_url,
            timeout=timeout or settings.AI_TIMEOUT_SECONDS,
            provider_name="gemini",
        )


class GroqProvider(BaseHostedProvider):
    """
    Fallback Generative AI Provider: Groq.
    Used exclusively on infrastructure availability failures when configured.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        resolved_key = api_key if api_key is not None else (settings.GROQ_API_KEY)
        resolved_model = model if model is not None else (settings.GROQ_MODEL or "llama-3.1-8b-instant")
        resolved_url = base_url if base_url is not None else (settings.GROQ_BASE_URL or "https://api.groq.com/openai/v1")

        super().__init__(
            api_key=resolved_key,
            model=resolved_model,
            base_url=resolved_url,
            timeout=timeout or settings.AI_TIMEOUT_SECONDS,
            provider_name="groq",
        )


class HostedOpenAIProvider(BaseHostedProvider):
    """
    Legacy OpenAI-compatible adapter for test fixtures and generic provider tests.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        super().__init__(
            api_key=api_key or settings.AI_API_KEY,
            model=model or settings.AI_MODEL or "gpt-4o-mini",
            base_url=base_url or settings.AI_BASE_URL or "https://api.openai.com/v1",
            timeout=timeout or settings.AI_TIMEOUT_SECONDS,
            provider_name="openai",
        )


class AIProviderRouter(AIProvider):
    """
    Backward-compatible provider router facade.

    V2 behavior: delegates to execute_with_failover() from failover_executor.py.
    - Sequential credential failover (no proactive rotation / round-robin)
    - Task-based model routing
    - Error-class-gated failover eligibility

    Accepts an optional `task_type` (TaskType enum or None).
    When task_type is None, defaults to TaskType.GAME_GENERATION.

    The `primary` and `fallback` constructor arguments are retained for test
    mock compatibility.  When a mock `primary` is injected, routing delegates
    to it directly (bypassing the failover executor) so test mocks continue to work.
    """

    def __init__(
        self,
        primary: Optional[AIProvider] = None,
        fallback: Optional[AIProvider] = None,
        task_type: Optional[Any] = None,
    ):
        # When a mock primary is injected (test context), use it directly.
        self.primary = primary
        self.fallback = fallback  # Retained for backward compat; not used in V2 direct path
        self._task_type = task_type

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        result, _ = await self.generate_structured_with_meta(system_prompt, user_prompt, json_schema, timeout=timeout)
        return result

    async def generate_structured_with_meta(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        task_type: Optional[Any] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Execute with failover routing.

        When a mock `primary` has been injected (test context), delegates to it
        directly so existing test mocks that patch GeminiProvider or inject a
        mock primary into AIProviderRouter continue to work without change.
        """
        resolved_task = task_type or self._task_type

        # Test-mock compatibility: if a mock primary was injected, use it directly
        if self.primary is not None:
            if hasattr(self.primary, "generate_structured_with_meta"):
                return await self.primary.generate_structured_with_meta(
                    system_prompt, user_prompt, json_schema, timeout=timeout
                )
            res = await self.primary.generate_structured(system_prompt, user_prompt, json_schema, timeout=timeout)
            return res, {
                "provider": getattr(self.primary, "provider_name", "primary"),
                "model": getattr(self.primary, "model", "default"),
                "fallback_used": False,
                "fallback_reason": None,
            }

        # V2 path: use the central failover executor
        from app.ai.failover_executor import execute_with_failover
        from app.ai.model_router import TaskType

        effective_task = resolved_task if isinstance(resolved_task, TaskType) else TaskType.GAME_GENERATION

        failover_result = await execute_with_failover(
            task_type=effective_task,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_schema=json_schema,
            timeout=timeout,
        )
        return failover_result.result, failover_result.to_provider_meta()
