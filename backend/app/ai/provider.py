from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class AIError(Exception):
    """Base exception for AI provider operations."""
    def __init__(self, code: str, message: str, status_code: int = 502):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(f"[{code}] {message}")


class ModelUnavailableError(AIError):
    """Raised when the hosted model endpoint is unreachable or down."""
    def __init__(self, message: str = "Hosted model service is currently unavailable.", code: str = "MODEL_UNAVAILABLE"):
        super().__init__(code, message, status_code=503)


class ModelTimeoutError(AIError):
    """Raised when hosted model inference exceeds the configured timeout."""
    def __init__(self, timeout_seconds: float, code: str = "MODEL_TIMEOUT", message: Optional[str] = None):
        super().__init__(
            code,
            message or f"Hosted model request timed out after {timeout_seconds} seconds.",
            status_code=504,
        )


class ModelRateLimitedError(AIError):
    """Raised when the hosted provider API quota or rate limit is exceeded."""
    def __init__(self, message: str = "Hosted model API rate limit exceeded.", code: str = "MODEL_RATE_LIMITED"):
        super().__init__(code, message, status_code=429)


class ModelInvalidResponseError(AIError):
    """Raised when the hosted model returns malformed JSON or empty content."""
    def __init__(self, message: str = "Hosted model returned an invalid or unparseable response.", code: str = "MODEL_INVALID_RESPONSE"):
        super().__init__(code, message, status_code=502)


class AIConfigurationError(AIError):
    """Raised when the AI provider credentials or settings are invalid."""
    def __init__(self, message: str = "AI provider is improperly configured (e.g. missing API key).", code: str = "AI_CONFIGURATION_ERROR"):
        super().__init__(code, message, status_code=500)


class AIProvider(ABC):
    """Abstract interface for hosted AI model providers."""

    @abstractmethod
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Request structured JSON from the hosted LLM provider.
        
        Must return a parsed Python dictionary or raise an AIError derivative.
        """
        pass
