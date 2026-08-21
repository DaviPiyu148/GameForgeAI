"""AI Provider abstraction package."""
from app.ai.provider import (
    AIConfigurationError,
    AIError,
    AIProvider,
    ModelInvalidResponseError,
    ModelRateLimitedError,
    ModelTimeoutError,
    ModelUnavailableError,
)
from app.ai.hosted_provider import HostedOpenAIProvider
from app.ai.prompts import (
    SYSTEM_PROMPT,
    build_generation_prompt,
    build_repair_prompt,
)

__all__ = [
    "AIProvider",
    "HostedOpenAIProvider",
    "AIError",
    "AIConfigurationError",
    "ModelInvalidResponseError",
    "ModelRateLimitedError",
    "ModelTimeoutError",
    "ModelUnavailableError",
    "SYSTEM_PROMPT",
    "build_generation_prompt",
    "build_repair_prompt",
]
