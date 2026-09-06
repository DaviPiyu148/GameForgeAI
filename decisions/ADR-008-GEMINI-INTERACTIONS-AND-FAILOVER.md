# ADR-008 — Gemini Interactions API & Multi-Model Sequential Failover Architecture

**Status:** Accepted

## Context

GameForge AI relies on Google Gemini hosted models to transform natural language prompts and creator intents into validated `GameDesignSpec` and `GameDSL` schemas.

To guarantee high availability, low latency, and resilience against quota exhaustion (429 RPM/RPD) across multiple independent Google accounts and Google Cloud projects, the generative AI subsystem requires a deterministic control plane that manages credentials, model fallbacks, deadlines, and repair loops.

The legacy round-robin key rotation mechanism caused unpredictable key churn and lacked request-level failover guarantees. Furthermore, a single monolithic timeout could cause timeouts across multi-attempt failover trees.

## Decision

GameForge AI adopts the **Gemini Interactions API Architecture** with sequential credential failover, task-based model routing, model fallback chains, dynamic remaining-deadline budgeting, and a dual transport abstraction.

### 1. Control Plane & Transport Separation

The control plane (`ModelRouter`, `GeminiKeyRegistry`, `FailoverExecutor`, `GameGenerationService`, and `validate_game_dsl`) is the **sole authoritative policy and validation layer**.

The transport layer is abstracted behind `AIProviderRouter` with a configuration switch (`AI_TRANSPORT`):
- `AI_TRANSPORT="interactions"`: Instantiates `GeminiInteractionsAdapter` (`google-genai` SDK).
- `AI_TRANSPORT="legacy_http"`: Instantiates `GeminiProvider` (`httpx` OpenAI-compatible REST proxy).

### 2. Sequential Credential Failover

- Credential #1 ($K_1$) is always attempted first for every request while healthy.
- If $K_1$ succeeds, request processing stops immediately.
- Subsequent requests continue to start with $K_1$.
- Failover to $K_2 \rightarrow K_3$ occurs **only** on retryable provider errors (401, credential 403, 429 rate limit, 5xx server flap, network timeout).
- Health tracking is ephemeral and process-local via `GeminiKeyRegistry` with configurable cooldown duration (`KEY_COOLDOWN_SECONDS`, default 300s) and failure threshold (`KEY_FAILURE_THRESHOLD`, default 3).

### 3. Task-Based Model Routing & Fallback Chains

Each operation type is classified into a `TaskType` with an ordered model fallback chain:

| Task Type | Primary Model | Fallback 1 | Fallback 2 | Timeout Cap | Thinking Level |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GAME_GENERATION` | `gemini-3.7-flash` | `gemini-3.6-flash` | `gemini-3.5-flash` | 25.0s | `medium` |
| `REMIX` | `gemini-3.7-flash` | `gemini-3.6-flash` | `gemini-3.5-flash` | 25.0s | `medium` |
| `DSL_PATCH` | `gemini-3.5-flash` | `gemini-3.5-flash-lite` | `gemini-3.1-flash-lite` | 15.0s | `low` |
| `BLUEPRINT` | `gemini-3.5-flash-lite` | `gemini-3.1-flash-lite` | — | 20.0s | `low` |
| `PLAYTEST_ANALYSIS` | `gemini-3.5-flash-lite` | `gemini-3.1-flash-lite` | — | 20.0s | `low` |
| `DIRECTOR` | `gemini-3.7-flash` | `gemini-3.6-flash` | `gemini-3.5-flash` | 25.0s | `medium` |

Model chains are declared as configurable policy defaults in `ModelRouter` and can be overridden via environment variables (`GEMINI_GENERATION_MODELS`, `GEMINI_REMIX_MODELS`, etc.).

### 4. Dynamic Remaining-Deadline Budgeting

The executor enforces an absolute overall deadline ($T_{\text{deadline}} = T_{\text{start}} + \text{AI\_OVERALL\_DEADLINE\_SECONDS}$). Each attempt dynamically receives:
$$\text{attempt\_timeout} = \min(\text{per\_attempt\_cap}, \text{overall\_deadline} - \text{elapsed\_time})$$

If $\text{remaining\_time} < 3.0\text{s}$, the executor aborts immediately rather than issuing a doomed network call.

### 5. Global Interaction Hard Cap ($\le 5$ Calls)

A strict global budget ceiling of **$\le 5$ total Gemini API calls** is enforced across primary credential attempts, fallback models, and semantic repair:
- **Primary Generation (Model 1)**: At most 3 credential attempts ($K_1, K_2, K_3$).
- **Model Fallback (Model 2)**: At most 1 fallback model, attempting at most 1 healthy credential ($K_1$).
- **Semantic Repair**: At most 1 repair interaction (`TaskType.DSL_PATCH`).

### 6. Granular 403 Error Classification

The error handler parses response payloads to distinguish:
- **Credential-Specific 403** (`API_KEY_INVALID`, `PERMISSION_DENIED: User not authorized`): Quarantines the credential and advances to the next key on the same model.
- **Model/Policy 403** (`RESOURCE_EXHAUSTED_TIER`, `MODEL_ACCESS_DENIED`, `LOCATION_NOT_SUPPORTED`): Does **not** penalize the credential; advances immediately to the next model in the chain.

### 7. Multi-Layer Validation Boundary

Structured output compliance (`response_format` / `response_schema`) does **not** bypass GameForge validation:
1. Gemini Structured Output parsing
2. Pydantic Type & Schema Coercion (`GameDSL.model_validate` with `extra="forbid"`)
3. Deterministic Normalizer (schema drift correction, scalar coercion, safe strip)
4. Security & Script Scanner (zero `eval`, zero script injection)
5. Requirement Coverage & Gameplay Quality Validator (`GameDepthEvaluator`)
6. Reachability & Spatial Feasibility Auto-Repair (`ReachabilityValidator`)
7. Authoritative Persistent `GameDSL` $\rightarrow$ Phaser 3.88 Runtime Compilation

### 8. Thought Stripping & Telemetry Sanitization

Internal model reasoning tokens (`<thought>` tags and thinking blocks) are stripped server-side. Compiler build logs emitted over Server-Sent Events (SSE) remain strictly sanitized, structured, and user-facing.

### 9. Stateful Remix with Authoritative Local Fallback

Remix operations may pass `previous_interaction_id` for token and latency optimization, but the database's persisted `ProjectVersion.game_dsl` remains the authoritative source of truth. If interaction state expires or fails across unlinked accounts, the system automatically falls back to full database-backed prompt execution.

## Rejected / Deferred Alternatives

- **Proactive / Round-Robin Key Rotation**: Rejected because proactive rotation unnecessarily churns healthy credentials, fragments session state, and prevents detecting when Credential #1 has recovered.
- **Unbounded Retry / Repair Storms**: Rejected in favor of an absolute global ceiling of $\le 5$ total Gemini interactions per build lifecycle.
- **Direct Client-to-Gemini SDK Calls**: Rejected because raw API credentials must never be exposed to the browser.
- **Relying Exclusively on Gemini JSON Schema**: Rejected because schema compliance does not guarantee semantic validity, game balance, or spatial reachability.
- **Local LLM Fallback (Ollama/vLLM)**: Deferred/rejected due to high VRAM hardware requirements incompatible with target deployment environments.

## Consequences

### Positive
- High resilience against quota limits and transient provider outages through sequential failover across independent Google accounts.
- Zero credential churn during healthy operation.
- Deterministic execution times bounded by remaining-deadline budgeting and the $\le 5$ call cap.
- Strict security boundary preserving Pydantic schema validation and script scanning.
- Single-line rollback capability via `AI_TRANSPORT`.

### Negative
- Requires maintaining multiple independent API keys in environment configuration for optimal redundancy.
- Additional abstraction layer in the AI provider pipeline.
