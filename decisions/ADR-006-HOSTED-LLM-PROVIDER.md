# ADR-006 — Hosted LLM Provider Abstraction

**Status:** Accepted

## Context

GameForge AI requires model inference for parts of the build/generation pipeline.

Local inference is intentionally unsupported because the intended execution environments do not reliably provide the GPU/VRAM resources required for performant local inference.

Provider-specific API protocols, credentials, rate limits, and failure modes should not leak into domain logic.

## Decision

All model inference uses a **Hosted LLM API** behind an internal `AIProvider` abstraction.

The backend communicates with the provider.

The frontend never communicates directly with an LLM provider and receives zero provider credentials.

Provider-specific SDK/protocol details remain inside the provider adapter.

## Architecture Pipeline

```text
FastAPI / BuildService
        ↓
AIProvider abstraction
        ↓
Hosted LLM Provider
        ↓
Structured response
        ↓
Pydantic / Game DSL validation
        ↓
Bounded repair loop
        ↓
Validated Game DSL artifact
        ↓
Build pipeline / project persistence
```

## Provider Contract

The internal `AIProvider` boundary should normalize:

- Request construction
- Model selection
- Structured-output handling
- Authentication
- Timeouts
- Retryable vs non-retryable failures
- Rate-limit handling
- Provider error mapping
- Observability metadata

Domain services must not import or depend on vendor-specific SDK behavior.

## Configuration

Provider/model configuration is supplied through environment/configuration management, including the currently defined settings:

- `AI_PROVIDER`
- `AI_MODEL`
- `AI_API_KEY`
- `AI_BASE_URL`
- `AI_TIMEOUT_SECONDS`
- `AI_MAX_RETRIES`

Configuration must be validated at startup where required.

## Reliability

External calls require:

- Strict timeouts
- Bounded retries
- Exponential backoff/jitter where appropriate
- Clear retryability classification
- Request cancellation handling
- Safe error mapping

The generation/repair process is bounded. The current design permits at most 2 retries for provider/repair handling as defined by the implementation contract.

Do not create infinite retry or repair loops.

## Structured Output

Prefer structured JSON responses.

Provider output must still pass Game DSL/schema validation.

A provider returning syntactically valid JSON does not make the content semantically valid.

## Security

Never:

- Expose `AI_API_KEY` to the browser.
- Log provider secrets.
- Store provider credentials in source control.
- Trust provider/LLM output as executable code.
- Allow provider-specific bypasses around DSL validation.

## Observability

Provider calls should expose safe operational telemetry such as:

- Latency
- Success/failure counts
- Timeout counts
- Retry counts
- Rate-limit events
- Model/provider identifiers where safe

Do not log prompts/responses indiscriminately if they may contain sensitive user data or secrets.

## Provider Agility

Changing providers/models should normally require changes inside the provider adapter/configuration layer rather than domain services or generation/business logic.

## Rejected / Deferred

- Local LLM inference as a fallback
- Provider SDK calls from domain services
- Frontend-to-provider API calls
- Unlimited retry/repair loops
- Provider-specific business logic spread throughout the application

## Consequences

### Positive

- Hardware independence.
- Provider interchangeability.
- Backend-only credential handling.
- Centralized timeout/error/retry policy.
- Clear boundary between generation infrastructure and business logic.

### Negative

- Requires external network access.
- Subject to provider availability, quotas, pricing, and latency.
- Hosted inference must be handled carefully during outages.
