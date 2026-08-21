import asyncio
import json
import re
from typing import Any, Dict, List, Optional, Tuple
import httpx

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
    ) -> Dict[str, Any]:
        """
        Request structured JSON completion from the hosted provider endpoint.
        """
        res, _ = await self.generate_structured_with_meta(system_prompt, user_prompt, json_schema)
        return res

    async def generate_structured_with_meta(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
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
            "temperature": 0.3,
        }

        url = f"{self.base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException:
            raise ModelTimeoutError(self.timeout)
        except httpx.NetworkError as net_err:
            raise ModelUnavailableError(
                f"Network error connecting to {self.provider_name} provider: {str(net_err)}"
            )
        except Exception as exc:
            raise AIError("AI_CONNECTION_FAILED", f"Failed to reach {self.provider_name} provider: {str(exc)}")

        if response.status_code == 401 or response.status_code == 403:
            raise AIConfigurationError(
                f"{self.provider_name.capitalize()} rejected the configured credentials.",
                code="AI_PROVIDER_AUTHENTICATION",
            )
        elif response.status_code == 429:
            raise ModelRateLimitedError(f"Rate limit exceeded on {self.provider_name} provider.")
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
            if "gemini" in self.model.lower():
                model_display = "Gemini 3 Flash Preview" if "flash" in self.model.lower() else self.model
            elif "gemma" in self.model.lower():
                model_display = "Gemma 4 31B"
            else:
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
    Primary Generative AI Provider: Google Gemini.
    Uses Google AI Studio / Gemini OpenAI-compatible REST endpoint.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        resolved_key = api_key if api_key is not None else (settings.GEMINI_API_KEY or settings.AI_API_KEY)
        resolved_model = model if model is not None else (settings.GEMINI_MODEL or settings.AI_MODEL or "gemini-3-flash-preview")
        resolved_url = base_url if base_url is not None else (settings.GEMINI_BASE_URL or "https://generativelanguage.googleapis.com/v1beta/openai")

        super().__init__(
            api_key=resolved_key,
            model=resolved_model,
            base_url=resolved_url,
            timeout=timeout or settings.AI_TIMEOUT_SECONDS,
            provider_name="gemini",
        )


class RotatingGeminiProvider(AIProvider):
    """
    Gemini provider that rotates round-robin across a pool of configured API keys.

    Two rate-limit defenses in one:
    1. Load spreading: each call advances to the next key in the pool, so steady
       traffic is distributed across keys instead of hammering a single one.
    2. Reactive rotation: if the key picked for this call comes back rate-limited
       (HTTP 429) or rejected (401/403 -- e.g. a revoked key), the next key in the
       pool is tried immediately within the same request, bounded to one attempt
       per configured key so an exhausted pool still fails fast.

    Degrades to plain single-key GeminiProvider behavior when only one key (or
    zero) is configured -- existing single-key deployments are unaffected.
    """

    provider_name = "gemini"

    def __init__(
        self,
        api_keys: Optional[List[str]] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self._keys: List[str] = [k for k in (api_keys if api_keys is not None else settings.gemini_api_key_pool()) if k]
        self.model = model or (settings.GEMINI_MODEL or settings.AI_MODEL or "gemini-3-flash-preview")
        self.base_url = (base_url or settings.GEMINI_BASE_URL or "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/")
        self.timeout = timeout or settings.AI_TIMEOUT_SECONDS
        self._index = 0
        self._lock = asyncio.Lock()

        # Backward-compatible single-key surface for callers that inspect `.api_key`
        # directly (e.g. AIProviderRouter's "is a fallback provider configured?" check).
        self.api_key = self._keys[0] if self._keys else None

    async def _next_key(self) -> str:
        async with self._lock:
            key = self._keys[self._index % len(self._keys)]
            self._index += 1
        return key

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        result, _ = await self.generate_structured_with_meta(system_prompt, user_prompt, json_schema)
        return result

    async def generate_structured_with_meta(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if not self._keys:
            raise AIConfigurationError("Gemini API key is not configured on the server.")

        last_error: Optional[AIError] = None
        for _ in range(len(self._keys)):
            key = await self._next_key()
            provider = GeminiProvider(api_key=key, model=self.model, base_url=self.base_url, timeout=self.timeout)
            try:
                res, meta = await provider.generate_structured_with_meta(system_prompt, user_prompt, json_schema)
                if len(self._keys) > 1:
                    meta["key_pool_size"] = len(self._keys)
                return res, meta
            except (ModelRateLimitedError, AIConfigurationError) as err:
                # This specific key is rate-limited or was rejected -- rotate to the
                # next key in the pool rather than surfacing a hard failure immediately.
                last_error = err
                continue

        raise last_error or ModelRateLimitedError("All configured Gemini API keys are rate-limited.")


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
    Provider Router:
    - Primary: Google Gemini (Gemini 3 Flash Preview: `gemini-3-flash-preview`), rotating across every
      configured `GEMINI_API_KEY`/`GEMINI_API_KEYS` if more than one key is set.
    - Optional Fallback: Groq (if explicitly injected, otherwise none)
    """

    def __init__(
        self,
        primary: Optional[AIProvider] = None,
        fallback: Optional[AIProvider] = None,
    ):
        self.primary = primary or RotatingGeminiProvider()
        self.fallback = fallback

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Request structured completion with automatic fallback on infrastructure failures.
        """
        result, _ = await self.generate_structured_with_meta(system_prompt, user_prompt, json_schema)
        return result

    async def generate_structured_with_meta(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Execute completion with infrastructure fallback routing and provider traceability metadata.
        """
        # 1. Attempt Primary Provider (Gemini)
        try:
            if hasattr(self.primary, "generate_structured_with_meta"):
                return await self.primary.generate_structured_with_meta(
                    system_prompt, user_prompt, json_schema
                )
            else:
                res = await self.primary.generate_structured(system_prompt, user_prompt, json_schema)
                return res, {
                    "provider": getattr(self.primary, "provider_name", "primary"),
                    "model": getattr(self.primary, "model", "default"),
                    "fallback_used": False,
                    "fallback_reason": None,
                }

        except (ModelUnavailableError, ModelTimeoutError, ModelRateLimitedError) as infra_err:
            # 2. Check if Fallback Provider (Groq) is configured
            fallback_key = getattr(self.fallback, "api_key", None)
            if fallback_key:
                try:
                    if hasattr(self.fallback, "generate_structured_with_meta"):
                        res, meta = await self.fallback.generate_structured_with_meta(
                            system_prompt, user_prompt, json_schema
                        )
                        meta["fallback_used"] = True
                        meta["fallback_reason"] = infra_err.code
                        return res, meta
                    else:
                        res = await self.fallback.generate_structured(system_prompt, user_prompt, json_schema)
                        return res, {
                            "provider": getattr(self.fallback, "provider_name", "groq"),
                            "model": getattr(self.fallback, "model", "llama-3.1-8b-instant"),
                            "fallback_used": True,
                            "fallback_reason": infra_err.code,
                        }
                except Exception as fb_err:
                    raise ModelUnavailableError(
                        f"Primary provider failed ({infra_err.message}) and fallback provider also failed: {str(fb_err)}"
                    )
            else:
                # Fallback unconfigured: re-raise the primary provider error cleanly
                raise infra_err

        except AIConfigurationError as cfg_err:
            # If Primary has no API key configured, check if fallback has key configured
            fallback_key = getattr(self.fallback, "api_key", None)
            if fallback_key:
                if hasattr(self.fallback, "generate_structured_with_meta"):
                    res, meta = await self.fallback.generate_structured_with_meta(
                        system_prompt, user_prompt, json_schema
                    )
                    meta["fallback_used"] = True
                    meta["fallback_reason"] = "PRIMARY_NOT_CONFIGURED"
                    return res, meta
                else:
                    res = await self.fallback.generate_structured(system_prompt, user_prompt, json_schema)
                    return res, {
                        "provider": getattr(self.fallback, "provider_name", "groq"),
                        "model": getattr(self.fallback, "model", "llama-3.1-8b-instant"),
                        "fallback_used": True,
                        "fallback_reason": "PRIMARY_NOT_CONFIGURED",
                    }
            raise cfg_err
