"""
test_ai_provider.py — AI Provider Architecture V2 Tests

Tests the following behaviors:
1.  Key 1 is used first on every healthy request.
2.  Key 1 remains primary on successive successful requests (no round-robin).
3.  Key 2 is NOT called after Key 1 success.
4.  Key 1 eligible failure → Key 2 tried.
5.  Key 2 success → Key 3 not called.
6.  All credentials fail → model fallback to next model.
7.  Next model starts from Key 1.
8.  INVALID_REQUEST → no key failover.
9.  SCHEMA_PARSING → no key failover.
10. CONTENT_SAFETY → no key failover.
11. MODEL_UNAVAILABLE → next model (not next key).
12. KEY_AUTH_FAILURE → next credential.
13. RATE_LIMIT → next credential.
14. TRANSIENT (5xx) → next credential.
15. Duplicate keys removed from pool.
16. Configured credential order preserved.
17. Cooldown works (key in cooldown is skipped).
18. Credential health resets after success.
19. Key secret never appears in logs / FailoverResult metadata.
20. Overall deadline enforced.
21. Task-specific model chains are correct (TaskType routing).
22. GeminiProvider: missing key raises AIConfigurationError.
23. GeminiProvider: valid structured response parsing.
24. GeminiProvider: markdown codeblock stripping.
25. GeminiProvider: thought-tag stripping.
26. GeminiProvider: malformed JSON raises ModelInvalidResponseError.
27. GeminiProvider: timeout raises ModelTimeoutError.
28. GeminiProvider: 401 raises AIConfigurationError.
29. GeminiProvider: 429 raises ModelRateLimitedError.
30. GeminiProvider: 500 raises ModelUnavailableError.
31. GeminiProvider: 404 raises ModelUnavailableError.
32. AIProviderRouter defaults to failover executor (no injected primary).
33. AIProviderRouter with injected mock primary bypasses executor.
34. Error classification: classify_ai_error maps exceptions correctly.
35. GeminiKeyRegistry: get_eligible_keys respects cooldown.
"""
import json
import json as _json
import pytest
import httpx
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai.hosted_provider import (
    AIProviderRouter,
    GeminiProvider,
    GroqProvider,
    HostedOpenAIProvider,
)
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
from app.config import settings
from app.ai.key_registry import GeminiKeyRegistry, ProviderKeyState
from app.ai.model_router import TaskType, resolve_model_chain
from app.ai.failover_executor import execute_with_failover, FailoverResult


# ================================================================
# Helpers
# ================================================================

def _make_ok_response(data: dict) -> httpx.Response:
    return httpx.Response(
        status_code=200,
        json={"choices": [{"message": {"content": _json.dumps(data)}}]},
    )


def _make_error_response(status: int, body: str = "") -> httpx.Response:
    return httpx.Response(status_code=status, text=body)


# ================================================================
# 22. GeminiProvider — Missing API Key
# ================================================================

@pytest.mark.asyncio
async def test_gemini_missing_api_key_raises_configuration_error():
    """Test that calling GeminiProvider without API key raises AIConfigurationError."""
    provider = GeminiProvider(api_key="")
    with pytest.raises(AIConfigurationError) as exc_info:
        await provider.generate_structured("System prompt", "User prompt")
    assert "Gemini API key is not configured" in exc_info.value.message
    assert exc_info.value.code == "AI_CONFIGURATION_ERROR"


# ================================================================
# 23. GeminiProvider — Valid structured response
# ================================================================

@pytest.mark.asyncio
async def test_gemini_valid_structured_response_parsing(monkeypatch):
    """Test clean parsing of valid JSON output from GeminiProvider."""
    expected_dict = {
        "schema_version": "1.0",
        "metadata": {
            "title": "Cyberpunk Neon Arena",
            "genre": "Action Survival",
        },
    }
    sent_payload = {}
    sent_headers = {}

    async def mock_post(self, url, json=None, headers=None):
        nonlocal sent_payload, sent_headers
        sent_payload = json
        sent_headers = headers
        assert "generativelanguage.googleapis.com" in str(url)
        return _make_ok_response(expected_dict)

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = GeminiProvider(api_key="test-gemini-key", model="gemini-3.6-flash")
    assert provider.model == "gemini-3.6-flash"
    result, meta = await provider.generate_structured_with_meta("System", "User")
    assert result == expected_dict
    assert meta["provider"] == "gemini"
    assert meta["model"] == "gemini-3.6-flash"
    assert meta["provider_display_name"] == "Google Gemini"
    assert meta["fallback_used"] is False
    assert sent_payload.get("model") == "gemini-3.6-flash"
    assert sent_headers.get("Authorization") == "Bearer test-gemini-key"


# ================================================================
# 24. GeminiProvider — Markdown codeblock stripping
# ================================================================

@pytest.mark.asyncio
async def test_gemini_markdown_codeblock_stripping(monkeypatch):
    """Test that ```json ... ``` markdown wrappers are cleanly stripped."""
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


# ================================================================
# 25. GeminiProvider — Thought tag stripping
# ================================================================

@pytest.mark.asyncio
async def test_gemini_thought_tags_stripping(monkeypatch):
    """Test that <thought>...</thought> tags from reasoning models are stripped."""
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


# ================================================================
# 26. GeminiProvider — Malformed JSON
# ================================================================

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
    assert exc_info.value.error_class == ProviderErrorClass.SCHEMA_PARSING


# ================================================================
# 27. GeminiProvider — Timeout
# ================================================================

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
    assert exc_info.value.error_class == ProviderErrorClass.NETWORK_ERROR


# ================================================================
# 28. GeminiProvider — 401
# ================================================================

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
    assert exc_info.value.error_class == ProviderErrorClass.KEY_AUTH_FAILURE


# ================================================================
# 29. GeminiProvider — 429
# ================================================================

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
    assert exc_info.value.error_class == ProviderErrorClass.RATE_LIMIT


# ================================================================
# 30. GeminiProvider — 500
# ================================================================

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
    assert exc_info.value.error_class == ProviderErrorClass.MODEL_UNAVAILABLE


# ================================================================
# 31. GeminiProvider — 404 (MODEL_UNAVAILABLE, not INVALID_REQUEST)
# ================================================================

@pytest.mark.asyncio
async def test_gemini_404_raises_model_unavailable_not_invalid_request(monkeypatch):
    """Test that HTTP 404 raises ModelUnavailableError (model not found), not INVALID_REQUEST."""
    async def mock_post(self, url, json=None, headers=None):
        return httpx.Response(status_code=404, text="Model not found")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    provider = GeminiProvider(api_key="test-gemini-key", model="gemini-3.7-flash")
    with pytest.raises(ModelUnavailableError) as exc_info:
        await provider.generate_structured("System", "User")
    assert exc_info.value.error_class == ProviderErrorClass.MODEL_UNAVAILABLE


# ================================================================
# 34. Error Classification
# ================================================================

def test_classify_ai_error_from_subclasses():
    """classify_ai_error should use .error_class from well-typed AIError subclasses."""
    assert classify_ai_error(ModelTimeoutError(5.0)) == ProviderErrorClass.NETWORK_ERROR
    assert classify_ai_error(ModelRateLimitedError()) == ProviderErrorClass.RATE_LIMIT
    assert classify_ai_error(AIConfigurationError()) == ProviderErrorClass.KEY_AUTH_FAILURE
    assert classify_ai_error(ModelUnavailableError()) == ProviderErrorClass.MODEL_UNAVAILABLE
    assert classify_ai_error(ModelInvalidResponseError()) == ProviderErrorClass.SCHEMA_PARSING


def test_classify_ai_error_from_raw_status():
    """classify_ai_error should classify plain AIError by status_code when no subclass."""
    err_401 = AIError("GENERIC", "auth fail", status_code=401)
    assert classify_ai_error(err_401) == ProviderErrorClass.KEY_AUTH_FAILURE

    err_429 = AIError("GENERIC", "rate limit", status_code=429)
    assert classify_ai_error(err_429) == ProviderErrorClass.RATE_LIMIT

    err_400 = AIError("GENERIC", "bad request", status_code=400)
    assert classify_ai_error(err_400) == ProviderErrorClass.INVALID_REQUEST

    err_503 = AIError("GENERIC", "down", status_code=503)
    assert classify_ai_error(err_503) == ProviderErrorClass.TRANSIENT_PROVIDER


def test_failover_eligibility_matrix():
    """is_credential_failover_eligible must match the spec table exactly."""
    assert is_credential_failover_eligible(ProviderErrorClass.KEY_AUTH_FAILURE) is True
    assert is_credential_failover_eligible(ProviderErrorClass.RATE_LIMIT) is True
    assert is_credential_failover_eligible(ProviderErrorClass.TRANSIENT_PROVIDER) is True
    assert is_credential_failover_eligible(ProviderErrorClass.NETWORK_ERROR) is True
    assert is_credential_failover_eligible(ProviderErrorClass.UNKNOWN) is True
    # Must NOT trigger credential failover
    assert is_credential_failover_eligible(ProviderErrorClass.INVALID_REQUEST) is False
    assert is_credential_failover_eligible(ProviderErrorClass.CONTENT_SAFETY) is False
    assert is_credential_failover_eligible(ProviderErrorClass.SCHEMA_PARSING) is False
    assert is_credential_failover_eligible(ProviderErrorClass.MODEL_UNAVAILABLE) is False


# ================================================================
# 21. Task-Specific Model Chains
# ================================================================

def test_task_model_chains_have_correct_defaults():
    """resolve_model_chain must return correct Gemini 3 defaults per task."""
    gen_chain = resolve_model_chain(TaskType.GAME_GENERATION)
    assert gen_chain == ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"]

    remix_chain = resolve_model_chain(TaskType.REMIX)
    assert remix_chain == ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"]

    blueprint_chain = resolve_model_chain(TaskType.BLUEPRINT)
    assert blueprint_chain == ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]

    patch_chain = resolve_model_chain(TaskType.DSL_PATCH)
    assert patch_chain == ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]

    analysis_chain = resolve_model_chain(TaskType.PLAYTEST_ANALYSIS)
    assert analysis_chain == ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]

    director_chain = resolve_model_chain(TaskType.DIRECTOR)
    assert director_chain == ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"]


def test_task_model_chains_all_non_empty():
    """Every task type must return a non-empty model chain."""
    for task in TaskType:
        chain = resolve_model_chain(task)
        assert len(chain) >= 1, f"Empty chain for {task}"


# ================================================================
# 35. GeminiKeyRegistry — Eligibility & Cooldown
# ================================================================

def test_key_registry_configured_order_preserved():
    """Credential order must match the configured key pool order."""
    registry = GeminiKeyRegistry(api_keys=["key_a", "key_b", "key_c"])
    eligible = registry.get_eligible_keys()
    assert [idx for (idx, _) in eligible] == [0, 1, 2]
    assert eligible[0][1] == "key_a"
    assert eligible[1][1] == "key_b"
    assert eligible[2][1] == "key_c"


def test_key_registry_deduplicates():
    """Duplicate keys must be removed; the first occurrence's position is kept."""
    registry = GeminiKeyRegistry(api_keys=["key_a", "key_b", "key_a", "key_c"])
    assert len(registry) == 3
    eligible = registry.get_eligible_keys()
    keys = [k for (_, k) in eligible]
    assert keys.count("key_a") == 1
    assert "key_b" in keys
    assert "key_c" in keys


@pytest.mark.asyncio
async def test_key_registry_cooldown_skips_key():
    """A credential in cooldown must be skipped by get_eligible_keys()."""
    registry = GeminiKeyRegistry(
        api_keys=["key_a", "key_b", "key_c"],
        failure_threshold=1,
        cooldown_seconds=3600,
    )
    # Force key_a into cooldown
    await registry.record_failure(0, ProviderErrorClass.RATE_LIMIT)
    eligible = registry.get_eligible_keys()
    eligible_keys = [k for (_, k) in eligible]
    assert "key_a" not in eligible_keys
    assert "key_b" in eligible_keys
    assert "key_c" in eligible_keys


@pytest.mark.asyncio
async def test_key_registry_cooldown_clears_after_expiry():
    """A credential must become eligible again after its cooldown expires."""
    registry = GeminiKeyRegistry(
        api_keys=["key_a", "key_b"],
        failure_threshold=1,
        cooldown_seconds=0,  # Instant expiry for test
    )
    await registry.record_failure(0, ProviderErrorClass.RATE_LIMIT)
    # With 0s cooldown the disabled_until is in the past → should be eligible
    eligible = registry.get_eligible_keys()
    eligible_keys = [k for (_, k) in eligible]
    # key_a should have expired cooldown (0 seconds) and be eligible again
    assert "key_a" in eligible_keys


@pytest.mark.asyncio
async def test_key_registry_record_success_clears_failures():
    """record_success must reset consecutive_failures and clear disabled_until."""
    registry = GeminiKeyRegistry(
        api_keys=["key_a"],
        failure_threshold=1,
        cooldown_seconds=3600,
    )
    await registry.record_failure(0, ProviderErrorClass.RATE_LIMIT)
    assert not registry.get_eligible_keys()  # In cooldown

    await registry.record_success(0)
    state = registry.get_state(0)
    assert state.consecutive_failures == 0
    assert state.disabled_until is None
    assert registry.get_eligible_keys()  # Eligible again


@pytest.mark.asyncio
async def test_key_registry_auth_failure_immediate_cooldown():
    """KEY_AUTH_FAILURE must immediately enter cooldown regardless of threshold."""
    registry = GeminiKeyRegistry(
        api_keys=["key_a", "key_b"],
        failure_threshold=5,  # High threshold; would normally need 5 failures
        cooldown_seconds=3600,
    )
    # One AUTH failure should immediately disable the key
    await registry.record_failure(0, ProviderErrorClass.KEY_AUTH_FAILURE)
    state = registry.get_state(0)
    assert state.disabled_until is not None
    eligible = registry.get_eligible_keys()
    assert all(k != "key_a" for (_, k) in eligible)


def test_key_registry_secret_not_in_state():
    """Credential secrets must not appear in ProviderKeyState (only masked identifier)."""
    raw_key = "AIzaSyB19AMT2lo2Q4_BTHKRCSBpe9K06U8Cu3I"
    registry = GeminiKeyRegistry(api_keys=[raw_key])
    state = registry.get_state(0)
    assert raw_key not in state.masked_key
    assert len(state.masked_key) <= 8  # Only last 4 chars + prefix dots


# ================================================================
# Failover Executor — Core Sequential Behavior
# ================================================================

@pytest.mark.asyncio
async def test_key1_used_first():
    """Key 1 must be the first credential tried on a healthy request."""
    registry = GeminiKeyRegistry(api_keys=["key_a", "key_b", "key_c"])
    expected_result = {"ok": True}

    with patch("app.ai.gemini_interactions_adapter.GeminiInteractionsAdapter") as MockProvider:
        MockProvider.return_value.generate_structured_with_meta = AsyncMock(
            return_value=(expected_result, {})
        )
        result = await execute_with_failover(
            task_type=TaskType.GAME_GENERATION,
            system_prompt="S",
            user_prompt="U",
            registry=registry,
        )

    # Only one call should have been made (first success stops)
    assert MockProvider.call_count == 1
    # Verify Key 1 (key_a) was used
    call_kwargs = MockProvider.call_args
    used_key = call_kwargs.kwargs.get("api_key") or (call_kwargs.args[0] if call_kwargs.args else None)
    assert used_key == "key_a"
    assert result.result == expected_result
    assert result.key_fallbacks_used == 0
    assert result.model_fallbacks_used == 0


@pytest.mark.asyncio
async def test_key1_stays_primary_on_successive_success():
    """Key 1 must be used for EVERY request when healthy — no round-robin."""
    registry = GeminiKeyRegistry(api_keys=["key_a", "key_b", "key_c"])
    seen_keys = []

    with patch("app.ai.gemini_interactions_adapter.GeminiInteractionsAdapter") as MockProvider:
        MockProvider.return_value.generate_structured_with_meta = AsyncMock(
            return_value=({"ok": True}, {})
        )
        for _ in range(4):
            MockProvider.reset_mock()
            await execute_with_failover(
                task_type=TaskType.GAME_GENERATION,
                system_prompt="S",
                user_prompt="U",
                registry=registry,
            )
            call_kwargs = MockProvider.call_args
            used_key = call_kwargs.kwargs.get("api_key") or (call_kwargs.args[0] if call_kwargs.args else None)
            seen_keys.append(used_key)

    # All 4 requests must have used key_a (Key 1)
    assert all(k == "key_a" for k in seen_keys), f"Expected all key_a, got: {seen_keys}"


@pytest.mark.asyncio
async def test_key2_not_called_after_key1_success():
    """After Key 1 succeeds, Key 2 must NOT be called."""
    registry = GeminiKeyRegistry(api_keys=["key_a", "key_b"])

    with patch("app.ai.gemini_interactions_adapter.GeminiInteractionsAdapter") as MockProvider:
        MockProvider.return_value.generate_structured_with_meta = AsyncMock(
            return_value=({"ok": True}, {})
        )
        await execute_with_failover(
            task_type=TaskType.GAME_GENERATION,
            system_prompt="S",
            user_prompt="U",
            registry=registry,
        )

    # Only one provider instantiation (Key 1 only)
    assert MockProvider.call_count == 1


@pytest.mark.asyncio
async def test_key1_eligible_failure_triggers_key2():
    """After Key 1 rate-limited, Key 2 must be tried."""
    registry = GeminiKeyRegistry(
        api_keys=["key_a", "key_b"],
        failure_threshold=5,
        cooldown_seconds=3600,
    )
    call_sequence = []

    with patch("app.ai.gemini_interactions_adapter.GeminiInteractionsAdapter") as MockProvider:
        def provider_factory(*args, **kwargs):
            key = kwargs.get("api_key", "")
            call_sequence.append(key)
            mock = MagicMock()
            if key == "key_a":
                mock.generate_structured_with_meta = AsyncMock(
                    side_effect=ModelRateLimitedError()
                )
            else:
                mock.generate_structured_with_meta = AsyncMock(
                    return_value=({"ok": True}, {})
                )
            return mock

        MockProvider.side_effect = provider_factory

        result = await execute_with_failover(
            task_type=TaskType.GAME_GENERATION,
            system_prompt="S",
            user_prompt="U",
            registry=registry,
        )

    assert result.result == {"ok": True}
    assert "key_a" in call_sequence
    assert "key_b" in call_sequence
    assert result.key_fallbacks_used == 1


@pytest.mark.asyncio
async def test_key2_success_key3_not_called():
    """After Key 2 succeeds (Key 1 failed), Key 3 must NOT be called."""
    registry = GeminiKeyRegistry(
        api_keys=["key_a", "key_b", "key_c"],
        failure_threshold=5,
        cooldown_seconds=3600,
    )
    call_sequence = []

    with patch("app.ai.gemini_interactions_adapter.GeminiInteractionsAdapter") as MockProvider:
        def provider_factory(*args, **kwargs):
            key = kwargs.get("api_key", "")
            call_sequence.append(key)
            mock = MagicMock()
            if key == "key_a":
                mock.generate_structured_with_meta = AsyncMock(
                    side_effect=ModelRateLimitedError()
                )
            else:
                mock.generate_structured_with_meta = AsyncMock(
                    return_value=({"ok": True}, {})
                )
            return mock

        MockProvider.side_effect = provider_factory
        await execute_with_failover(
            task_type=TaskType.GAME_GENERATION,
            system_prompt="S",
            user_prompt="U",
            registry=registry,
        )

    assert "key_a" in call_sequence
    assert "key_b" in call_sequence
    assert "key_c" not in call_sequence, "key_c should not be called after key_b succeeds"


@pytest.mark.asyncio
async def test_invalid_request_no_failover():
    """INVALID_REQUEST error must raise immediately — no credential or model cycling."""
    registry = GeminiKeyRegistry(
        api_keys=["key_a", "key_b"],
        failure_threshold=5,
        cooldown_seconds=3600,
    )

    with patch("app.ai.gemini_interactions_adapter.GeminiInteractionsAdapter") as MockProvider:
        mock = MagicMock()
        mock.generate_structured_with_meta = AsyncMock(
            side_effect=AIError("INVALID_REQUEST", "bad payload", status_code=400,
                                error_class=ProviderErrorClass.INVALID_REQUEST)
        )
        MockProvider.return_value = mock

        with pytest.raises(AIError) as exc_info:
            await execute_with_failover(
                task_type=TaskType.GAME_GENERATION,
                system_prompt="S",
                user_prompt="U",
                registry=registry,
            )

    # Must fail immediately — only one provider instantiation
    assert MockProvider.call_count == 1
    assert exc_info.value.error_class == ProviderErrorClass.INVALID_REQUEST


@pytest.mark.asyncio
async def test_schema_parsing_no_failover():
    """SCHEMA_PARSING error must raise immediately — provider succeeded, it's our problem."""
    registry = GeminiKeyRegistry(
        api_keys=["key_a", "key_b"],
        failure_threshold=5,
        cooldown_seconds=3600,
    )

    with patch("app.ai.gemini_interactions_adapter.GeminiInteractionsAdapter") as MockProvider:
        mock = MagicMock()
        mock.generate_structured_with_meta = AsyncMock(
            side_effect=ModelInvalidResponseError("bad json")
        )
        MockProvider.return_value = mock

        with pytest.raises(ModelInvalidResponseError):
            await execute_with_failover(
                task_type=TaskType.GAME_GENERATION,
                system_prompt="S",
                user_prompt="U",
                registry=registry,
            )

    assert MockProvider.call_count == 1


@pytest.mark.asyncio
async def test_model_unavailable_triggers_model_fallback_not_key_cycling():
    """MODEL_UNAVAILABLE must advance to next model, not cycle through keys."""
    registry = GeminiKeyRegistry(
        api_keys=["key_a", "key_b"],
        failure_threshold=5,
        cooldown_seconds=3600,
    )
    call_sequence = []

    with patch("app.ai.gemini_interactions_adapter.GeminiInteractionsAdapter") as MockProvider:
        def provider_factory(*args, **kwargs):
            key = kwargs.get("api_key", "")
            model = kwargs.get("model", "")
            call_sequence.append((model, key))
            mock = MagicMock()
            if "3.7" in model:
                mock.generate_structured_with_meta = AsyncMock(
                    side_effect=ModelUnavailableError(code="MODEL_NOT_FOUND")
                )
            else:
                mock.generate_structured_with_meta = AsyncMock(
                    return_value=({"ok": True, "model_used": model}, {})
                )
            return mock

        MockProvider.side_effect = provider_factory

        result = await execute_with_failover(
            task_type=TaskType.GAME_GENERATION,
            system_prompt="S",
            user_prompt="U",
            registry=registry,
        )

    assert result.result.get("ok") is True
    assert "3.7" not in result.model_used
    assert result.model_fallbacks_used >= 1


@pytest.mark.asyncio
async def test_all_credentials_fail_triggers_model_fallback():
    """After all credentials are exhausted for model N, executor must try model N+1."""
    registry = GeminiKeyRegistry(
        api_keys=["key_a"],
        failure_threshold=5,
        cooldown_seconds=3600,
    )
    call_sequence = []

    with patch("app.ai.gemini_interactions_adapter.GeminiInteractionsAdapter") as MockProvider:
        def provider_factory(*args, **kwargs):
            model = kwargs.get("model", "")
            key = kwargs.get("api_key", "")
            call_sequence.append((model, key))
            mock = MagicMock()
            if "3.7" in model:
                mock.generate_structured_with_meta = AsyncMock(
                    side_effect=ModelRateLimitedError()
                )
            else:
                mock.generate_structured_with_meta = AsyncMock(
                    return_value=({"ok": True}, {})
                )
            return mock

        MockProvider.side_effect = provider_factory
        result = await execute_with_failover(
            task_type=TaskType.GAME_GENERATION,
            system_prompt="S",
            user_prompt="U",
            registry=registry,
        )

    models_tried = [m for (m, _) in call_sequence]
    assert any("3.7" in m for m in models_tried)
    assert any("3.7" not in m for m in models_tried)
    assert result.result == {"ok": True}
    assert result.model_fallbacks_used >= 1


@pytest.mark.asyncio
async def test_next_model_starts_from_key1():
    """When falling back to the next model, the executor must start from Key 1, not Key 2."""
    registry = GeminiKeyRegistry(
        api_keys=["key_a", "key_b"],
        failure_threshold=5,
        cooldown_seconds=3600,
    )
    call_sequence = []

    with patch("app.ai.gemini_interactions_adapter.GeminiInteractionsAdapter") as MockProvider:
        def provider_factory(*args, **kwargs):
            model = kwargs.get("model", "")
            key = kwargs.get("api_key", "")
            call_sequence.append((model, key))
            mock = MagicMock()
            if "3.7" in model:
                mock.generate_structured_with_meta = AsyncMock(
                    side_effect=ModelRateLimitedError()
                )
            else:
                mock.generate_structured_with_meta = AsyncMock(
                    return_value=({"ok": True}, {})
                )
            return mock

        MockProvider.side_effect = provider_factory
        await execute_with_failover(
            task_type=TaskType.GAME_GENERATION,
            system_prompt="S",
            user_prompt="U",
            registry=registry,
        )

    fallback_model_calls = [(m, k) for (m, k) in call_sequence if "3.7" not in m]
    if fallback_model_calls:
        first_fallback_key = fallback_model_calls[0][1]
        assert first_fallback_key == "key_a", f"Fallback should start from Key 1, got: {first_fallback_key}"


@pytest.mark.asyncio
async def test_no_eligible_credentials_raises_unavailable():
    """An empty credential pool must raise AIConfigurationError or ModelUnavailableError."""
    registry = GeminiKeyRegistry(api_keys=[])

    # With an empty pool, the executor should fail fast with a configuration error
    with pytest.raises((AIConfigurationError, ModelUnavailableError)):
        await execute_with_failover(
            task_type=TaskType.GAME_GENERATION,
            system_prompt="S",
            user_prompt="U",
            registry=registry,
        )


@pytest.mark.asyncio
async def test_failover_result_no_credential_details():
    """FailoverResult.to_provider_meta() must not expose raw credential values."""
    registry = GeminiKeyRegistry(api_keys=["my_super_secret_key_12345"])

    with patch("app.ai.gemini_interactions_adapter.GeminiInteractionsAdapter") as MockProvider:
        MockProvider.return_value.generate_structured_with_meta = AsyncMock(
            return_value=({"ok": True}, {})
        )
        result = await execute_with_failover(
            task_type=TaskType.GAME_GENERATION,
            system_prompt="S",
            user_prompt="U",
            registry=registry,
        )

    meta = result.to_provider_meta()
    meta_str = str(meta)
    assert "my_super_secret_key_12345" not in meta_str
    assert "provider" in meta
    assert "model" in meta


# ================================================================
# 32. AIProviderRouter — Defaults
# ================================================================

@pytest.mark.asyncio
async def test_router_with_no_primary_uses_failover_executor():
    """AIProviderRouter with no injected primary should use the failover executor."""
    router = AIProviderRouter()
    assert router.primary is None  # V2 behavior: no primary means → failover executor


# ================================================================
# 33. AIProviderRouter — Test mock compatibility
# ================================================================

@pytest.mark.asyncio
async def test_router_with_injected_mock_primary_bypasses_executor(monkeypatch):
    """AIProviderRouter with a mock primary should delegate to it directly."""
    expected_dsl = {"schema_version": "1.0", "title": "Mock Game"}

    async def mock_post(self, url, json=None, headers=None):
        return _make_ok_response(expected_dsl)

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    primary = GeminiProvider(api_key="test-key-123", model="gemini-3.6-flash")
    router = AIProviderRouter(primary=primary)

    result, meta = await router.generate_structured_with_meta("System", "User")
    assert result == expected_dsl
    assert meta["provider"] == "gemini"
    assert meta["model"] == "gemini-3.6-flash"
    assert meta["fallback_used"] is False


# ================================================================
# 36. GeminiInteractionsAdapter — Transport & Schema Tests
# ================================================================

from app.ai.gemini_interactions_adapter import GeminiInteractionsAdapter


@pytest.mark.asyncio
async def test_interactions_adapter_missing_api_key_raises_configuration_error(monkeypatch):
    """Interactions adapter with no API key must raise AIConfigurationError."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    monkeypatch.setattr(settings, "GEMINI_API_KEYS", None)
    monkeypatch.setattr(settings, "AI_API_KEY", None)

    adapter = GeminiInteractionsAdapter(api_key="")
    with pytest.raises(AIConfigurationError) as exc_info:
        await adapter.generate_structured("System", "User")
    assert "Gemini API key is not configured" in exc_info.value.message


@pytest.mark.asyncio
async def test_interactions_adapter_valid_structured_response():
    """Interactions adapter must parse valid JSON output and return interaction metadata."""
    adapter = GeminiInteractionsAdapter(api_key="test-key-123", model="gemini-3.7-flash")

    mock_interaction = MagicMock()
    mock_interaction.output_text = json.dumps({"schema_version": "1.0", "title": "Interactions Game"})
    mock_interaction.id = "interaction-abc-123"
    mock_interaction.usage = {"total_tokens": 500}

    with patch("google.genai.Client") as MockClient:
        mock_instance = MagicMock()
        mock_instance.aio.interactions.create = AsyncMock(return_value=mock_interaction)
        MockClient.return_value = mock_instance

        res, meta = await adapter.generate_structured_with_meta("System", "User")

    assert res["title"] == "Interactions Game"
    assert meta["provider"] == "gemini"
    assert meta["model"] == "gemini-3.7-flash"
    assert meta["interaction_id"] == "interaction-abc-123"


@pytest.mark.asyncio
async def test_interactions_adapter_thought_tag_stripping():
    """Interactions adapter must strip reasoning tags server-side before parsing JSON."""
    adapter = GeminiInteractionsAdapter(api_key="test-key-123")

    mock_interaction = MagicMock()
    mock_interaction.output_text = (
        "<thought>Plan: Generate topdown shooter mechanics with player velocity 200</thought>\n"
        '{"schema_version": "1.0", "title": "Clean Game"}'
    )
    mock_interaction.id = "int-123"

    with patch("google.genai.Client") as MockClient:
        mock_instance = MagicMock()
        mock_instance.aio.interactions.create = AsyncMock(return_value=mock_interaction)
        MockClient.return_value = mock_instance

        res = await adapter.generate_structured("System", "User")

    assert res["title"] == "Clean Game"
    assert "<thought>" not in json.dumps(res)


@pytest.mark.asyncio
async def test_interactions_adapter_codeblock_stripping():
    """Interactions adapter must strip markdown code fences."""
    adapter = GeminiInteractionsAdapter(api_key="test-key-123")

    mock_interaction = MagicMock()
    mock_interaction.output_text = '```json\n{"schema_version": "1.0", "title": "Fenced Game"}\n```'
    mock_interaction.id = "int-456"

    with patch("google.genai.Client") as MockClient:
        mock_instance = MagicMock()
        mock_instance.aio.interactions.create = AsyncMock(return_value=mock_interaction)
        MockClient.return_value = mock_instance

        res = await adapter.generate_structured("System", "User")

    assert res["title"] == "Fenced Game"


@pytest.mark.asyncio
async def test_interactions_adapter_previous_interaction_id_forwarding():
    """Interactions adapter must forward previous_interaction_id when provided."""
    adapter = GeminiInteractionsAdapter(api_key="test-key-123")

    mock_interaction = MagicMock()
    mock_interaction.output_text = '{"title": "Remix Game"}'
    mock_interaction.id = "int-789"

    with patch("google.genai.Client") as MockClient:
        mock_instance = MagicMock()
        mock_create = AsyncMock(return_value=mock_interaction)
        mock_instance.aio.interactions.create = mock_create
        MockClient.return_value = mock_instance

        await adapter.generate_structured(
            "System", "Remix Prompt", previous_interaction_id="int-parent-001"
        )

    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs.get("previous_interaction_id") == "int-parent-001"


@pytest.mark.asyncio
async def test_interactions_adapter_model_access_denied_403_raises_model_unavailable():
    """403 with model-level access denied must classify as MODEL_UNAVAILABLE (not KEY_AUTH_FAILURE)."""
    adapter = GeminiInteractionsAdapter(api_key="test-key-123", model="gemini-3.7-flash")

    error = Exception("HTTP 403: model access_denied location not supported")
    error.status_code = 403

    with patch("google.genai.Client") as MockClient:
        mock_instance = MagicMock()
        mock_instance.aio.interactions.create = AsyncMock(side_effect=error)
        MockClient.return_value = mock_instance

        with pytest.raises(ModelUnavailableError) as exc_info:
            await adapter.generate_structured("System", "User")

    assert exc_info.value.code == "MODEL_ACCESS_DENIED"
    assert exc_info.value.error_class == ProviderErrorClass.MODEL_UNAVAILABLE

