# AI Provider Architecture

## 1. Overview

The AI Provider subsystem provides deterministic, highly available, and resilient Google Gemini API inference for GameForge AI.

It translates user prompts and game-building intents into validated `GameDesignSpec` and `GameDSL` schemas through a structured control plane featuring:
- **Sequential Request-Level Credential Failover**: Uses Credential #1 ($K_1$) while healthy, failing over to backup credentials ($K_2 \rightarrow K_3$) only upon eligible errors.
- **Task-Based Model Routing & Fallback Chains**: Dispatches each AI task type to its optimized primary model with an ordered fallback sequence.
- **Dynamic Remaining-Deadline Budgeting**: Allocates per-attempt timeouts based on the remaining wall-clock budget of an absolute request deadline.
- **Global Interaction Budget Ceiling**: Enforces a hard maximum of $\le 5$ Gemini API calls across generation, model fallback, and semantic repair.
- **Dual Transport Abstraction**: Supports both the official Google Gemini Interactions API (`google-genai` SDK) and an OpenAI-compatible REST proxy adapter via configuration.
- **Strict Multi-Layer Validation Boundary**: Reaffirms that LLM output is never trusted directly as executable code; all outputs must pass Pydantic schema validation, security scanning, quality grading, and reachability auto-repair.

---

## 2. Architecture Pipeline

```text
                      Client Request (Prompt / Intent)
                                    │
                                    ▼
                          GameGenerationService
                                    │ (specifies TaskType)
                                    ▼
                            AIProviderRouter
                                    │
                                    ▼
                            FailoverExecutor
                        (execute_with_failover)
                                    │
        ┌───────────────────────────┴───────────────────────────┐
        ▼                                                       ▼
   ModelRouter                                            Key Registry
(resolve_model_chain)                                 (GeminiKeyRegistry)
        │                                                       │
        │ Model Fallback Chain                                  │ Eligible Credentials (K1, K2, K3)
        └───────────────────────────┬───────────────────────────┘
                                    │
                                    ▼
                         Transport Adapter Layer
            ┌───────────────────────────────────────────────┐
            │ AI_TRANSPORT="interactions" → Interactions    │
            │ AI_TRANSPORT="legacy_http"   → GeminiProvider │
            └───────────────────────┬───────────────────────┘
                                    │
                                    ▼
                         Google Gemini REST API
                                    │
                                    ▼
                         Raw Structured Output
                                    │
                                    ▼
                       Multi-Layer Validation Pipeline
           ┌────────────────────────┼────────────────────────┐
           ↓                        ↓                        ↓
    DSL Normalizer          Security Scanner         Depth Evaluator
  (0 repair calls)          (0 eval / script)      (Quality $\ge$ Threshold)
           └────────────────────────┬────────────────────────┘
                                    │
                                    ▼
                        Bounded Semantic Repair
                    (Max 1 call, dedicated 45s cap)
                                    │
                                    ▼
                      Validated GameDSL Artifact
                                    │
                                    ▼
                     Phaser 3.88 Runtime Compilation
```

---

## 3. Canonical Task Routing Matrix

Each generative operation is mapped to a dedicated `TaskType` with configured primary and fallback models:

| Task Type | Primary Model | Fallback 1 | Fallback 2 | Credential Strategy | Attempt Cap | Thinking Level |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GAME_GENERATION` | `gemini-3.7-flash` | `gemini-3.6-flash` | `gemini-3.5-flash` | Sequential | 25.0s | `medium` |
| `REMIX` | `gemini-3.7-flash` | `gemini-3.6-flash` | `gemini-3.5-flash` | Sequential | 25.0s | `medium` |
| `DSL_PATCH` | `gemini-3.5-flash` | `gemini-3.5-flash-lite` | `gemini-3.1-flash-lite` | Sequential | 15.0s | `low` |
| `BLUEPRINT` | `gemini-3.5-flash-lite` | `gemini-3.1-flash-lite` | — | Sequential | 20.0s | `low` |
| `PLAYTEST_ANALYSIS`| `gemini-3.5-flash-lite` | `gemini-3.1-flash-lite` | — | Sequential | 20.0s | `low` |
| `DIRECTOR` | `gemini-3.7-flash` | `gemini-3.6-flash` | `gemini-3.5-flash` | Sequential | 25.0s | `medium` |

Model chains are declared as configurable defaults in `ModelRouter` and can be customized via environment variables (`GEMINI_GENERATION_MODELS`, `GEMINI_REMIX_MODELS`, etc.).

---

## 4. Credential Management & Health Lifecycle

### 4.1 Sequential Failover Invariants
1. **Request Origin**: Every incoming request begins by attempting Credential #1 ($K_1$) on the primary model.
2. **Zero Proactive Churn**: If $K_1$ succeeds, request execution completes immediately. There is no round-robin or random rotation.
3. **Multi-Account Quota Isolation**: Configured API keys represent independent Google accounts/projects to ensure that rate limits (429) on one project do not affect backup keys.

### 4.2 Ephemeral In-Memory Health Tracking (`GeminiKeyRegistry`)
- **Key Authentication Failure (`KEY_AUTH_FAILURE`)**: Enters quarantine cooldown immediately upon a 401 or credential-level 403 error.
- **Transient Provider / Rate Limit Failures**: Enters quarantine cooldown after exceeding `KEY_FAILURE_THRESHOLD` consecutive failures (default: 3).
- **Cooldown Duration**: Quarantined keys remain inactive for `KEY_COOLDOWN_SECONDS` (default: 300s).
- **Process Scope**: Health state is strictly in-memory and resets upon application restart.

---

## 5. Comprehensive Error Classification & Routing

The error classifier (`classify_ai_error`) inspects HTTP status codes and response payloads to determine failover behavior:

| HTTP Status / Condition | Error Classification | Key Failover? | Model Fallback? | Action Taken |
| :--- | :--- | :---: | :---: | :--- |
| **401 Unauthorized** | `KEY_AUTH_FAILURE` | **YES** | NO | Key into quarantine $\rightarrow$ advance to next key on same model. |
| **403 Credential Error** (Invalid key, user unauthorized) | `KEY_AUTH_FAILURE` | **YES** | NO | Key into quarantine $\rightarrow$ advance to next key on same model. |
| **403 Model / Policy Error** (Region blocked, model restricted) | `MODEL_UNAVAILABLE` | **NO** | **YES** | Do NOT penalize key $\rightarrow$ advance immediately to next model in chain. |
| **429 Rate Limit / Quota Exhaustion** | `RATE_LIMIT` | **YES** | NO (until keys exhausted) | Increment key failure count $\rightarrow$ try next key; if all keys exhausted $\rightarrow$ fallback model. |
| **500 / 502 / 503 / 504 Server Flap** | `TRANSIENT_PROVIDER` | **YES** | NO (until keys exhausted) | Increment key failure count $\rightarrow$ try next key; if all exhausted $\rightarrow$ fallback model. |
| **404 / 501 Model Unsupported** | `MODEL_UNAVAILABLE` | **NO** | **YES** | Advance immediately to next model in chain without penalizing key. |
| **400 Bad Request Payload** | `INVALID_REQUEST` | **NO** | **NO** | Terminal error $\rightarrow$ raise immediately to caller. |
| **Content Safety Rejection** | `CONTENT_SAFETY` | **NO** | **NO** | Terminal error $\rightarrow$ raise immediately to caller. |
| **Malformed JSON Output** | `SCHEMA_PARSING` | **NO** | **NO** | Pass raw text to deterministic normalizer & bounded repair loop. |
| **Network Timeout / Disconnect** | `NETWORK_ERROR` | **YES** | NO | Try next key if remaining deadline $\ge 3.0\text{s}$. |

---

## 6. Deadline Budgeting & Call Ceiling

### 6.1 Dynamic Remaining-Deadline Formula
The executor calculates attempt timeouts dynamically:
$$\text{attempt\_timeout} = \min(\text{per\_attempt\_cap}, \text{overall\_deadline} - \text{elapsed\_time})$$

- If $\text{remaining\_time} < 3.0\text{s}$, the attempt aborts immediately to avoid doomed network overhead.
- Total wall-clock execution time across all attempts is bounded by `AI_OVERALL_DEADLINE_SECONDS` (default: 420.0s).

### 6.2 Global Interaction Budget ($\le 5$ Calls)
To prevent retry storms, the build lifecycle enforces a global limit of $\le 5$ total Gemini API calls:
- **Primary Model ($M_1$)**: Up to 3 credential attempts ($K_1, K_2, K_3$).
- **Fallback Model ($M_2$)**: Up to 1 fallback model attempt with 1 healthy credential ($K_1$).
- **Semantic Repair (`DSL_PATCH`)**: At most 1 bounded repair interaction.

---

## 7. Resilience & Normalization Pipeline

To eliminate unnecessary repair calls, GameForge AI implements a two-stage resilience pipeline:

1. **Stage 1: Deterministic Normalization (`dsl_normalizer.py`)** (0 Provider Calls)
   - Resolves harmless schema drift (e.g. `levels[i].width` $\rightarrow$ `levels[i].world.width`).
   - Coerces scalar formats (numeric strings $\rightarrow$ floats/ints, hex color formatting).
   - Maps behavioral synonyms and strips safe metadata fields.
   - Cleans markdown fences (````json ... ````) and XML thought wrappers.
   - Fast-fails on security violations (`UNSAFE_DSL_PAYLOAD`) with zero repair overhead.

2. **Stage 2: Bounded Semantic Repair (`game_generation_service.py`)** (Max 1 Provider Call)
   - Invoked only when genuine semantic validation errors occur.
   - Uses dedicated `AI_REPAIR_TIMEOUT_SECONDS` (45.0s).
   - Passes exact validation issues to the model to generate a targeted patch.

---

## 8. Configuration Reference

All settings are configured via environment variables in `backend/.env`:

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `AI_PROVIDER` | string | `gemini` | Generative provider selection |
| `AI_TRANSPORT` | string | `interactions` | Transport layer: `interactions` (`google-genai`) or `legacy_http` (`httpx` proxy) |
| `GEMINI_API_KEY` | string | unset | Primary API credential (or comma-separated list) |
| `GEMINI_API_KEYS` | string | unset | Secondary / backup credentials |
| `GEMINI_BASE_URL` | string | `https://generativelanguage.googleapis.com/v1beta/openai` | Base URL for legacy HTTP transport |
| `GEMINI_GENERATION_MODELS` | string | `gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash` | Comma-separated generation model chain |
| `GEMINI_REMIX_MODELS` | string | `gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash` | Comma-separated remix model chain |
| `GEMINI_DSL_PATCH_MODELS` | string | `gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite` | Comma-separated repair model chain |
| `GEMINI_BLUEPRINT_MODELS` | string | `gemini-3.5-flash-lite,gemini-3.1-flash-lite` | Comma-separated blueprint model chain |
| `GEMINI_ANALYSIS_MODELS` | string | `gemini-3.5-flash-lite,gemini-3.1-flash-lite` | Comma-separated telemetry critique chain |
| `KEY_FAILURE_THRESHOLD` | integer | `3` | Consecutive failures before key enters quarantine |
| `KEY_COOLDOWN_SECONDS` | integer | `300` | Duration of key quarantine in seconds |
| `AI_OVERALL_DEADLINE_SECONDS` | float | `420.0` | Maximum wall-clock time for multi-attempt execution |
| `AI_TIMEOUT_SECONDS` | float | `150.0` | Per-attempt HTTP timeout for primary generation |
| `AI_REPAIR_TIMEOUT_SECONDS` | float | `45.0` | Per-attempt HTTP timeout for semantic repair |
| `AI_REPAIR_MAX_ATTEMPTS` | integer | `1` | Maximum semantic repair interactions allowed |

---

## 9. Security & Safety Invariants

1. **Zero Secret Leakage**: Raw API keys are never returned in HTTP responses, never written to persistent databases, and never sent to the browser. Server logs use masked representations (`...4321`) and 1-based index numbers.
2. **Thought Stripping**: Internal model reasoning tokens (`<thought>`) are stripped in the transport adapter and are never emitted over SSE build streams.
3. **No Dynamic Execution**: Model outputs are parsed exclusively as data structures. The runtime interpreter executes only allowlisted Arcade physics behaviors.
