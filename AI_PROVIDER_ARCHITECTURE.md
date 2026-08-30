# GameForge AI — AI Provider Architecture V2

## Overview

AI Provider Architecture V2 establishes a deterministic, sequential credential failover system with task-based model routing and model fallback chains for all Google Gemini API interactions in GameForge AI.

This supersedes the legacy round-robin `RotatingGeminiProvider` with a request-level sequential failover mechanism that keeps Credential #1 as the primary while healthy, failing over to backup credentials only on eligible errors.

---

## Key Principles & Invariants

1. **Sequential Request Failover (No Proactive Rotation)**:
   - For every request, Credential #1 is always attempted first.
   - If Credential #1 succeeds, request processing stops immediately.
   - Subsequent requests continue to start with Credential #1 as long as it is healthy.
   - No round-robin, no random key distribution, no proactive rotation.

2. **Credential Health & Ephemeral Cooldown**:
   - Ephemeral in-memory health tracking via `GeminiKeyRegistry`.
   - `KEY_AUTH_FAILURE` (401/403) enters cooldown immediately.
   - `RATE_LIMIT` (429), `TRANSIENT_PROVIDER` (5xx), and `NETWORK_ERROR` enter cooldown after `KEY_FAILURE_THRESHOLD` consecutive failures.
   - Cooldown duration: `KEY_COOLDOWN_SECONDS` (default 300s).
   - Health state is process-local and resets on server restart.

3. **Quota Semantics & Project Isolation**:
   - Multiple credentials should be sourced from independently configured Google API projects to achieve genuine quota isolation.
   - Multiple keys from the same project share project-level quota.

4. **Task-Based Model Routing & Model Fallback**:
   - Each AI operation type has a specialized model chain via `TaskType` and `resolve_model_chain()`.
   - If all eligible credentials fail for the primary model, the executor falls back to the next model in the chain, starting again from Credential #1.
   - `MODEL_UNAVAILABLE` (404/501) triggers model fallback directly without penalizing credential health.

5. **Error Classification & Safe Failover Boundaries**:
   - Only eligible errors trigger credential failover (`KEY_AUTH_FAILURE`, `RATE_LIMIT`, `TRANSIENT_PROVIDER`, `NETWORK_ERROR`, `UNKNOWN`).
   - Ineligible errors (`INVALID_REQUEST`, `CONTENT_SAFETY`, `SCHEMA_PARSING`) raise immediately to the application layer to avoid futile credential churn.

6. **Generation Resilience Invariants**:
   - Schema drift (e.g. `levels[0].width`) is handled deterministically by local normalization in `validator.py` with **0 provider repair calls**.
   - Semantic repair uses `DSL_PATCH` with bounded 1-attempt repair and dedicated `AI_REPAIR_TIMEOUT_SECONDS` (45s).

7. **Zero Secret Leakage**:
   - Raw API keys are never logged, never returned in API responses, never stored in the database, and never exposed to the frontend/browser. Only masked strings (`...4321`) and 1-based indices are used in server logs.

---

## Canonical Task Routing Matrix

| Task Type | Primary Model | Fallback 1 | Fallback 2 | Credential Strategy | Structured Output | Timeout |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GAME_GENERATION` | `gemini-3.7-flash` | `gemini-3.6-flash` | `gemini-3.5-flash` | Sequential | `json_object` | 150s |
| `REMIX` | `gemini-3.6-flash` | `gemini-3.7-flash` | `gemini-3.5-flash` | Sequential | `json_object` | 150s |
| `DSL_PATCH` | `gemini-3.6-flash` | `gemini-3.5-flash-lite` | `gemini-3.1-flash-lite` | Sequential | `json_object` | 45s |
| `BLUEPRINT` | `gemini-3.7-flash` | `gemini-3.6-flash` | `gemini-3.5-flash` | Sequential | `json_object` | 150s |
| `PLAYTEST_ANALYSIS` | `gemini-3.5-flash-lite` | `gemini-3.6-flash` | `gemini-3.1-flash-lite` | Sequential | `json_object` | 150s |
| `DIRECTOR` | `gemini-3.7-flash` | `gemini-3.6-flash` | `gemini-3.5-flash` | Sequential | `json_object` | 150s |

---

## Architecture Flow

```
                      Client Request
                           │
                           ▼
                 GameGenerationService
                           │ (specifies TaskType)
                           ▼
                   AIProviderRouter
                           │
                           ▼
                  Failover Executor
              (execute_with_failover)
                           │
       ┌───────────────────┴───────────────────┐
       ▼                                       ▼
  Model Router                            Key Registry
(resolve_model_chain)                  (GeminiKeyRegistry)
       │                                       │
       │ Model Chain                           │ Eligible Credentials (1, 2, 3...)
       └───────────────────┬───────────────────┘
                           │
                           ▼
                    GeminiProvider
            (single credential + single model)
                           │
                           ▼
                 Google Gemini REST API
             (/v1beta/openai/chat/completions)
```

---

## Configuration Reference

| Environment Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `AI_PROVIDER` | string | `gemini` | Generative provider selection |
| `GEMINI_API_KEY` | string | unset | Comma-separated API credentials |
| `GEMINI_API_KEYS` | string | unset | Secondary/additional credentials |
| `GEMINI_BASE_URL` | string | `https://generativelanguage.googleapis.com/v1beta/openai` | API Base URL |
| `GEMINI_GENERATION_MODELS` | string | `gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash` | Custom generation chain |
| `GEMINI_REMIX_MODELS` | string | `gemini-3.6-flash,gemini-3.7-flash,gemini-3.5-flash` | Custom remix chain |
| `GEMINI_DSL_PATCH_MODELS` | string | `gemini-3.6-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite` | Custom patch/repair chain |
| `GEMINI_BLUEPRINT_MODELS` | string | `gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash` | Custom blueprint chain |
| `GEMINI_ANALYSIS_MODELS` | string | `gemini-3.5-flash-lite,gemini-3.6-flash,gemini-3.1-flash-lite` | Custom analysis chain |
| `KEY_FAILURE_THRESHOLD` | integer | `3` | Consecutive failures before cooldown |
| `KEY_COOLDOWN_SECONDS` | integer | `300` | Cooldown duration in seconds |
| `AI_OVERALL_DEADLINE_SECONDS` | float | `420.0` | Maximum wall-clock time across all attempts |
| `AI_TIMEOUT_SECONDS` | float | `150.0` | Per-attempt HTTP timeout for generation |
| `AI_REPAIR_TIMEOUT_SECONDS` | float | `45.0` | Per-attempt HTTP timeout for DSL repair |
