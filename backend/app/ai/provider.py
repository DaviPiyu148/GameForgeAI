from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional


class ProviderErrorClass(str, Enum):
    """
    Canonical classification of AI provider errors.

    This drives failover eligibility decisions:
    - KEY_AUTH_FAILURE, RATE_LIMIT, TRANSIENT_PROVIDER, NETWORK_ERROR, MODEL_UNAVAILABLE:
      credential/model failover may help — try next credential or next model.
    - INVALID_REQUEST, CONTENT_SAFETY, SCHEMA_PARSING:
      failover will NOT help — fail immediately to the application layer.
    - UNKNOWN: conservative — try next credential once.
    """
    KEY_AUTH_FAILURE = "KEY_AUTH_FAILURE"      # 401/403 — credential rejected
    RATE_LIMIT = "RATE_LIMIT"                  # 429 — quota / rate limit
    TRANSIENT_PROVIDER = "TRANSIENT_PROVIDER"  # 5xx — server-side infra flap
    NETWORK_ERROR = "NETWORK_ERROR"            # timeout / connection failure
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"    # model not found / offline for this model
    INVALID_REQUEST = "INVALID_REQUEST"        # 400 caused by our payload — fix the request
    CONTENT_SAFETY = "CONTENT_SAFETY"          # safety block — prompt content issue
    SCHEMA_PARSING = "SCHEMA_PARSING"          # provider succeeded but output unparseable
    UNKNOWN = "UNKNOWN"                        # unclassified — conservative failover


# ── Failover eligibility policies ────────────────────────────────────────────

def is_credential_failover_eligible(error_class: ProviderErrorClass) -> bool:
    """
    Returns True if trying the next configured credential might succeed.

    Ineligible errors (INVALID_REQUEST, CONTENT_SAFETY, SCHEMA_PARSING) indicate
    the problem is in GameForge's payload or the prompt — cycling credentials won't help.
    MODEL_UNAVAILABLE is typically a model-level issue, not a credential issue.
    """
    return error_class in (
        ProviderErrorClass.KEY_AUTH_FAILURE,
        ProviderErrorClass.RATE_LIMIT,
        ProviderErrorClass.TRANSIENT_PROVIDER,
        ProviderErrorClass.NETWORK_ERROR,
        ProviderErrorClass.UNKNOWN,
    )


def is_model_fallback_eligible(error_class: ProviderErrorClass) -> bool:
    """
    Returns True if trying the next model in the task chain might succeed.

    A MODEL_UNAVAILABLE error on model A should try model B — not cycle credentials.
    Credential exhaustion also triggers model fallback.
    """
    return error_class in (
        ProviderErrorClass.MODEL_UNAVAILABLE,
        ProviderErrorClass.RATE_LIMIT,
        ProviderErrorClass.TRANSIENT_PROVIDER,
        ProviderErrorClass.UNKNOWN,
    )


class AIError(Exception):
    """Base exception for AI provider operations."""
    def __init__(self, code: str, message: str, status_code: int = 502,
                 error_class: Optional[ProviderErrorClass] = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.error_class = error_class or ProviderErrorClass.UNKNOWN
        super().__init__(f"[{code}] {message}")


class ModelUnavailableError(AIError):
    """Raised when the hosted model endpoint is unreachable or down."""
    def __init__(self, message: str = "Hosted model service is currently unavailable.",
                 code: str = "MODEL_UNAVAILABLE"):
        super().__init__(code, message, status_code=503,
                         error_class=ProviderErrorClass.MODEL_UNAVAILABLE)


class ModelTimeoutError(AIError):
    """Raised when hosted model inference exceeds the configured timeout."""
    def __init__(self, timeout_seconds: float, code: str = "MODEL_TIMEOUT",
                 message: Optional[str] = None):
        super().__init__(
            code,
            message or f"Hosted model request timed out after {timeout_seconds} seconds.",
            status_code=504,
            error_class=ProviderErrorClass.NETWORK_ERROR,
        )


class ModelRateLimitedError(AIError):
    """Raised when the hosted provider API quota or rate limit is exceeded."""
    def __init__(self, message: str = "Hosted model API rate limit exceeded.",
                 code: str = "MODEL_RATE_LIMITED"):
        super().__init__(code, message, status_code=429,
                         error_class=ProviderErrorClass.RATE_LIMIT)


class ModelInvalidResponseError(AIError):
    """Raised when the hosted model returns malformed JSON or empty content."""
    def __init__(self, message: str = "Hosted model returned an invalid or unparseable response.",
                 code: str = "MODEL_INVALID_RESPONSE"):
        super().__init__(code, message, status_code=502,
                         error_class=ProviderErrorClass.SCHEMA_PARSING)


class AIConfigurationError(AIError):
    """Raised when the AI provider credentials or settings are invalid."""
    def __init__(self, message: str = "AI provider is improperly configured (e.g. missing API key).",
                 code: str = "AI_CONFIGURATION_ERROR"):
        super().__init__(code, message, status_code=500,
                         error_class=ProviderErrorClass.KEY_AUTH_FAILURE)


def classify_ai_error(exc: Exception) -> ProviderErrorClass:
    """
    Classify an exception into a canonical ProviderErrorClass.

    Prefers explicit .error_class on typed AIError subclasses (when it is not UNKNOWN),
    then falls back to HTTP status code inspection for plain AIError instances,
    then classifies httpx network errors by exception type name.
    Does NOT parse fragile human-readable strings when a structured code/status is available.
    """
    if isinstance(exc, AIError):
        # Use the subclass's error_class only if it is a specific, non-default classification
        if exc.error_class is not None and exc.error_class != ProviderErrorClass.UNKNOWN:
            return exc.error_class

        # Fall through to status_code inspection for plain AIError(code, msg, status_code=...)
        sc = exc.status_code
        if sc in (401, 403):
            return ProviderErrorClass.KEY_AUTH_FAILURE
        if sc == 429:
            return ProviderErrorClass.RATE_LIMIT
        if sc == 400:
            return ProviderErrorClass.INVALID_REQUEST
        if sc in (404, 501):
            return ProviderErrorClass.MODEL_UNAVAILABLE
        if sc >= 500:
            return ProviderErrorClass.TRANSIENT_PROVIDER
        return ProviderErrorClass.UNKNOWN

    # httpx network-level errors (import-time check avoids hard dependency here)
    exc_type = type(exc).__name__
    if exc_type in ("TimeoutException", "ConnectTimeout", "ReadTimeout", "WriteTimeout",
                    "PoolTimeout", "NetworkError", "ConnectError", "RemoteProtocolError"):
        return ProviderErrorClass.NETWORK_ERROR

    return ProviderErrorClass.UNKNOWN


class AIProvider(ABC):
    """Abstract interface for hosted AI model providers."""

    @abstractmethod
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Request structured JSON from the hosted LLM provider.

        Must return a parsed Python dictionary or raise an AIError derivative.
        """
        pass
