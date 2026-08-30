"""AI Provider abstraction package."""
from app.ai.provider import (
    AIConfigurationError,
    AIError,
    AIProvider,
    ModelInvalidResponseError,
    ModelRateLimitedError,
    ModelTimeoutError,
    ModelUnavailableError,
    ProviderErrorClass,
    classify_ai_error,
    is_credential_failover_eligible,
    is_model_fallback_eligible,
)
from app.ai.hosted_provider import (
    AIProviderRouter,
    GeminiProvider,
    GroqProvider,
    HostedOpenAIProvider,
)
from app.ai.model_router import TaskType, resolve_model_chain
from app.ai.prompts import (
    SYSTEM_PROMPT,
    build_generation_prompt,
    build_repair_prompt,
)

__all__ = [
    # Core provider interface
    "AIProvider",
    "AIProviderRouter",
    # Concrete providers
    "GeminiProvider",
    "GroqProvider",
    "HostedOpenAIProvider",
    # Error types
    "AIError",
    "AIConfigurationError",
    "ModelInvalidResponseError",
    "ModelRateLimitedError",
    "ModelTimeoutError",
    "ModelUnavailableError",
    # Error classification (V2)
    "ProviderErrorClass",
    "classify_ai_error",
    "is_credential_failover_eligible",
    "is_model_fallback_eligible",
    # Task routing (V2)
    "TaskType",
    "resolve_model_chain",
    # Prompts
    "SYSTEM_PROMPT",
    "build_generation_prompt",
    "build_repair_prompt",
]
