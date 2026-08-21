import json
import json as _json
import pytest
import httpx

from app.ai.hosted_provider import (
    AIProviderRouter,
    GeminiProvider,
    GroqProvider,
    HostedOpenAIProvider,
    RotatingGeminiProvider,
)
from app.ai.provider import (
    AIConfigurationError,
    AIError,
    AIProvider,
    ModelInvalidResponseError,
    ModelRateLimitedError,
    ModelTimeoutError,
    ModelUnavailableError,
)


# ================================================================
# GeminiProvider Tests
# ================================================================

@pytest.mark.asyncio
async def test_gemini_missing_api_key_raises_configuration_error():
    """Test that calling GeminiProvider without API key raises AIConfigurationError."""
    provider = GeminiProvider(api_key="")
    with pytest.raises(AIConfigurationError) as exc_info:
        await provider.generate_structured("System prompt", "User prompt")
    assert "Gemini API key is not configured" in exc_info.value.message
    assert exc_info.value.code == "AI_CONFIGURATION_ERROR"


@pytest.mark.asyncio
async def test_gemini_valid_structured_response_parsing(monkeypatch):
    """Test clean parsing of valid JSON output from Gemini provider with gemma-4-31b-it model payload."""
    expected_dict = {
        "schema_version": "1.0",
        "metadata": {
            "title": "Cyberpunk Neon Arena",
            "genre": "Action Survival",
            "description": "Survive roaming drones in a neon cyberpunk arena.",
            "archetype": "arena",
        },
        "world": {
            "width": 800,
            "height": 600,
            "gravity": 600,
            "background_color": "#0a0b10",
            "theme": "neon",
        },
        "player": {
            "name": "Player",
            "spawn_x": 100,
            "spawn_y": 300,
            "speed": 300,
            "jump_power": 550,
            "max_health": 100,
            "color": "#00f0ff",
        },
        "entities": [
            {
                "id": "drone_1",
                "type": "enemy",
                "x": 400,
                "y": 200,
                "width": 32,
                "height": 32,
                "color": "#ff0055",
                "behavior": "patrol",
                "speed": 120,
            }
        ],
        "rules": [
            {
                "trigger": {"type": "on_collide_enemy"},
                "action": {"type": "damage_player", "value": 20},
            }
        ],
        "ui": {
            "show_score": True,
            "show_health": True,
            "show_controls": True,
        },
    }
    sent_payload = {}
    sent_headers = {}

    async def mock_post(self, url, json=None, headers=None):
        nonlocal sent_payload, sent_headers
        sent_payload = json
        sent_headers = headers
        assert "generativelanguage.googleapis.com" in str(url)
        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {"message": {"content": _json.dumps(expected_dict)}}
                ]
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = GeminiProvider(
        api_key="test-gemini-key",
        model="gemma-4-31b-it",
    )
    assert provider.model == "gemma-4-31b-it"
    result, meta = await provider.generate_structured_with_meta("System", "User")
    assert result == expected_dict
    assert meta["provider"] == "gemini"
    assert meta["model"] == "gemma-4-31b-it"
    assert meta["provider_display_name"] == "Google Gemini"
    assert meta["model_display_name"] == "Gemma 4 31B"
    assert meta["fallback_used"] is False
    assert sent_payload.get("model") == "gemma-4-31b-it"
    assert sent_headers.get("Authorization") == "Bearer test-gemini-key"


@pytest.mark.asyncio
async def test_gemini_markdown_codeblock_stripping(monkeypatch):
    """Test that ```json ... ``` markdown wrappers are cleanly stripped by GeminiProvider."""
    expected_dict = {"schema_version": "1.0", "test": True}
    markdown_wrapped = f"```json\n{json.dumps(expected_dict)}\n```"

    async def mock_post(self, url, json=None, headers=None):
        return httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": markdown_wrapped}}]},
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = GeminiProvider(api_key="test-gemini-key")
    result = await provider.generate_structured("System", "User")
    assert result == expected_dict


@pytest.mark.asyncio
async def test_gemini_thought_tags_stripping(monkeypatch):
    """Test that <thought>...</thought> tags from Gemma are cleanly stripped by GeminiProvider."""
    expected_dict = {"schema_version": "1.0", "test": "clean"}
    raw_with_thoughts = f"<thought>\nThinking about the game design...\n</thought>\n{json.dumps(expected_dict)}"

    async def mock_post(self, url, json=None, headers=None):
        return httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": raw_with_thoughts}}]},
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = GeminiProvider(api_key="test-gemini-key")
    result = await provider.generate_structured("System", "User")
    assert result == expected_dict


@pytest.mark.asyncio
async def test_gemini_malformed_json_raises_invalid_response(monkeypatch):
    """Test that malformed JSON raises ModelInvalidResponseError."""
    async def mock_post(self, url, json=None, headers=None):
        return httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": "{ broken json syntax ..."}}]},
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = GeminiProvider(api_key="test-gemini-key")
    with pytest.raises(ModelInvalidResponseError) as exc_info:
        await provider.generate_structured("System", "User")
    assert exc_info.value.code == "MODEL_INVALID_RESPONSE"


@pytest.mark.asyncio
async def test_gemini_timeout_raises_model_timeout_error(monkeypatch):
    """Test that request timeout raises ModelTimeoutError."""
    async def mock_post(self, url, json=None, headers=None):
        raise httpx.TimeoutException("Connection timed out")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = GeminiProvider(api_key="test-gemini-key", timeout=5.0)
    with pytest.raises(ModelTimeoutError) as exc_info:
        await provider.generate_structured("System", "User")
    assert exc_info.value.code == "MODEL_TIMEOUT"


@pytest.mark.asyncio
async def test_gemini_authentication_failure_raises_configuration_error(monkeypatch):
    """Test that HTTP 401 raises AIConfigurationError with AI_PROVIDER_AUTHENTICATION code."""
    async def mock_post(self, url, json=None, headers=None):
        return httpx.Response(status_code=401, text="Unauthorized: Invalid API Key")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = GeminiProvider(api_key="bad-key")
    with pytest.raises(AIConfigurationError) as exc_info:
        await provider.generate_structured("System", "User")
    assert exc_info.value.code == "AI_PROVIDER_AUTHENTICATION"
    assert "Gemini rejected the configured credentials" in exc_info.value.message


@pytest.mark.asyncio
async def test_gemini_rate_limit_raises_rate_limited_error(monkeypatch):
    """Test that HTTP 429 raises ModelRateLimitedError."""
    async def mock_post(self, url, json=None, headers=None):
        return httpx.Response(status_code=429, text="Rate limit exceeded")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = GeminiProvider(api_key="test-gemini-key")
    with pytest.raises(ModelRateLimitedError) as exc_info:
        await provider.generate_structured("System", "User")
    assert exc_info.value.code == "MODEL_RATE_LIMITED"


@pytest.mark.asyncio
async def test_gemini_server_error_raises_model_unavailable_error(monkeypatch):
    """Test that HTTP 500/503 raises ModelUnavailableError."""
    async def mock_post(self, url, json=None, headers=None):
        return httpx.Response(status_code=503, text="Service Unavailable")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = GeminiProvider(api_key="test-gemini-key")
    with pytest.raises(ModelUnavailableError) as exc_info:
        await provider.generate_structured("System", "User")
    assert exc_info.value.code == "MODEL_UNAVAILABLE"


# ================================================================
# Router Tests
# ================================================================

@pytest.mark.asyncio
async def test_router_with_gemini_primary(monkeypatch):
    """Test that AIProviderRouter defaults to GeminiProvider and executes correctly."""
    expected_dsl = {"schema_version": "1.0", "title": "Gemini Game"}

    async def mock_gemini_post(self, url, json=None, headers=None):
        return httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": _json.dumps(expected_dsl)}}]},
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_gemini_post)

    primary = GeminiProvider(api_key="test-key-123", model="gemma-4-31b-it")
    router = AIProviderRouter(primary=primary)

    result, meta = await router.generate_structured_with_meta("System", "User")
    assert result == expected_dsl
    assert meta["provider"] == "gemini"
    assert meta["model"] == "gemma-4-31b-it"
    assert meta["fallback_used"] is False


# ================================================================
# RotatingGeminiProvider Tests
# ================================================================

@pytest.mark.asyncio
async def test_rotating_provider_no_keys_raises_configuration_error():
    """An empty key pool raises AIConfigurationError, same as a bare GeminiProvider."""
    provider = RotatingGeminiProvider(api_keys=[])
    with pytest.raises(AIConfigurationError):
        await provider.generate_structured("System", "User")


@pytest.mark.asyncio
async def test_rotating_provider_round_robins_across_successful_calls(monkeypatch):
    """Successive successful calls should advance through the key pool in order,
    spreading load rather than reusing the same key every time."""
    expected_dict = {"schema_version": "1.0", "test": True}
    seen_keys = []

    async def mock_post(self, url, json=None, headers=None):
        seen_keys.append(headers.get("Authorization"))
        return httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": _json.dumps(expected_dict)}}]},
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = RotatingGeminiProvider(api_keys=["key_a", "key_b", "key_c"])
    for _ in range(4):
        result, meta = await provider.generate_structured_with_meta("System", "User")
        assert result == expected_dict
        assert meta["key_pool_size"] == 3

    # 4 calls across a 3-key pool: key_a, key_b, key_c, key_a (round-robin wrap)
    assert seen_keys == ["Bearer key_a", "Bearer key_b", "Bearer key_c", "Bearer key_a"]


@pytest.mark.asyncio
async def test_rotating_provider_skips_rate_limited_key(monkeypatch):
    """If the first key in rotation is rate-limited, the next key in the pool is
    tried within the same request instead of surfacing a hard failure."""
    expected_dict = {"schema_version": "1.0", "test": "recovered"}

    async def mock_post(self, url, json=None, headers=None):
        if headers.get("Authorization") == "Bearer key_a":
            return httpx.Response(status_code=429, text="Rate limit exceeded")
        return httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": _json.dumps(expected_dict)}}]},
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = RotatingGeminiProvider(api_keys=["key_a", "key_b"])
    result, meta = await provider.generate_structured_with_meta("System", "User")
    assert result == expected_dict
    assert meta["provider"] == "gemini"


@pytest.mark.asyncio
async def test_rotating_provider_all_keys_rate_limited_raises(monkeypatch):
    """When every key in the pool is rate-limited, the provider fails fast with
    ModelRateLimitedError rather than retrying indefinitely."""
    async def mock_post(self, url, json=None, headers=None):
        return httpx.Response(status_code=429, text="Rate limit exceeded")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = RotatingGeminiProvider(api_keys=["key_a", "key_b"])
    with pytest.raises(ModelRateLimitedError):
        await provider.generate_structured_with_meta("System", "User")


@pytest.mark.asyncio
async def test_router_defaults_to_rotating_gemini_provider():
    """AIProviderRouter with no explicit primary should default to a RotatingGeminiProvider."""
    router = AIProviderRouter()
    assert isinstance(router.primary, RotatingGeminiProvider)
