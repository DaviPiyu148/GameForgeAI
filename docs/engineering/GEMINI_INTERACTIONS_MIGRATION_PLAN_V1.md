# GameForge AI — Gemini Interactions API Migration & Multi-Model Failover Architecture Plan V1 (Approved with Amendments)

## Executive Summary

GameForge AI is an AI-native game discovery and 2D browser prototyping platform. It leverages Google Gemini to translate natural-language prompts and interactive builder controls into structured, validatable `GameDesignSpec` and `GameDSL` schemas executed within a deterministic Phaser 3.88 Arcade Physics runtime.

This document serves as the authoritative, approved architectural blueprint for migrating GameForge AI's generative AI transport from the current OpenAI-compatible REST proxy adapter to the official **Google Gemini Interactions API** (`google-genai` SDK), while maintaining GameForge's existing multi-account credential failover, task-based model chains, bounded repair loops, multi-layer validation boundary, and strict runtime safety boundaries.

---

## 1. Final Approved Architecture

```text
                                GAMEFORGE AI
                                     │
                                Task Router
                                     │
                              Failover Executor
                                /           \
                       Credential          Model
                         policy             policy
                      K1 → K2 → K3       3.7 → 3.6 → 3.5
                                \           /
                                 \         /
                               Remaining Deadline
                               /     |     \
                              /      |      \
                             ↓       ↓       ↓
                        Interactions Adapter
                                  │
                           Google Gemini
                                  │
                         Structured Output
                                  │
                          GameForge Validation
                      ┌───────────┼───────────┐
                      ↓           ↓           ↓
                   Normalize    Security    Quality
                      └───────────┼───────────┘
                                  ↓
                               GameDSL
                                  ↓
                             ProjectVersion
```

### Core Architectural Invariants

1. **Policy vs. Transport Separation**: GameForge AI's control plane (`ModelRouter`, `GeminiKeyRegistry`, `FailoverExecutor`, `GameGenerationService`, and `validate_game_dsl`) remains the **sole authoritative policy and validation layer**. The Gemini Interactions API serves strictly as a network transport.
2. **Multi-Account Credential Independence**: Configured API keys represent **different, unlinked Google accounts and Google Cloud projects**. Credential health and quota exhaustion (e.g. 429 RPM/RPD) are strictly isolated per credential slot without global round-robin rotation.
3. **Sequential Failover Discipline**: Requests always start with `Primary Model + Key 1`. Key 2 is invoked **only** on retryable provider errors (401, credential 403, 429 rate limit, 5xx server flap, network timeout). Model fallback to `Model 2` occurs **only** after all eligible credentials for `Model 1` are exhausted or when the failure is classified as `MODEL_UNAVAILABLE` or model-level 403.
4. **Dynamic Remaining-Deadline Budgeting**: The executor enforces one absolute overall deadline ($T_{\text{deadline}} = T_{\text{start}} + 60\text{s}$). Every downstream attempt dynamically receives `min(attempt_cap, remaining_time)`. No layer may consume time beyond the remaining budget.
5. **Hard Global Interaction Budget**: A strict global ceiling of **$\le 5$ total Gemini API calls** per user build request is enforced across primary credential attempts, model fallback, and semantic repair.
6. **Multi-Layer Validation Boundary**: Google Gemini schema compliance is **not** equivalent to GameForge semantic correctness. All AI outputs pass through Pydantic parsing, deterministic normalization, security scanning, requirement coverage checks, gameplay quality grading, and reachability auto-repair.
7. **Safe SSE & Internal Thought Stripping**: Internal model reasoning and thinking tokens are stripped server-side. Compiler build logs emitted over Server-Sent Events (SSE) remain strictly structured, sanitized, and user-facing.
8. **Optional Stateful Remix with Authoritative Local Fallback**: Multi-turn remixing leverages `previous_interaction_id` for latency and token optimization, but seamlessly falls back to the database's authoritative `GameDSL` whenever interaction state is expired, evicted, or fails over across accounts.
9. **Zero Code Changes in Planning Phase**: This document governs architecture and planning only; implementation is gated by phase approval.

---

## 2. Six Required Plan Amendments (Approved Guardrails)

### Amendment 1: Remaining-Deadline Budgeting (Eliminate Fixed 45s Collision)
- **Problem**: A fixed 45s per-attempt timeout directly conflicts with a 60s overall deadline when attempting multiple credentials or fallbacks ($45\text{s} + 45\text{s} > 60\text{s}$).
- **Resolution**: The executor enforces a single overall deadline ($60.0\text{s}$). Each individual attempt receives:
  $$\text{attempt\_timeout} = \min(\text{per\_attempt\_cap}, \text{overall\_deadline} - \text{elapsed\_time})$$
  - Primary Generation Cap: $25.0\text{s}$
  - Secondary/Fallback Attempt Cap: $20.0\text{s}$
  - Repair Attempt Cap: $15.0\text{s}$
  - Minimum viable attempt threshold: If $\text{remaining\_time} < 3.0\text{s}$, abort immediately rather than issuing a doomed network call.

### Amendment 2: Formally Reconciled Global Interaction Budget ($\le 5$ Calls)
- **Problem**: Unbounded key retries $\times$ model fallbacks $\times$ repair loops could cause retry storms.
- **Resolution**: Impose strict sub-budgets and a global hard cap:
  - **Primary Generation (Model 1)**: At most $3$ credential attempts ($K_1, K_2, K_3$).
  - **Model Fallback (Model 2)**: At most $1$ fallback model, attempting at most $1$ healthy credential ($K_1$).
  - **Semantic Repair**: At most $1$ repair interaction (`TaskType.DSL_PATCH`).
  - **Global Hard Cap**: **Maximum $5$ Gemini interactions total** per build lifecycle. If the budget is exhausted, fail cleanly with a structured error.

```text
Worst-Case Tree:
K1 + M1 (fail) → K2 + M1 (fail) → K3 + M1 (fail) → K1 + M2 (success) → 1 Repair Call = 5 interactions MAX
```

### Amendment 3: Refined 403 Classification (Credential vs. Model/Policy 403)
- **Problem**: Blindly treating all HTTP 403 responses as `KEY_AUTH_FAILURE` could burn through all healthy Google accounts when the issue is model-level permissions, geographic tiering, or project API restrictions.
- **Resolution**: Parse error response payloads to distinguish:
  - **Credential-Specific 403** (e.g. `API_KEY_INVALID`, `PERMISSION_DENIED: User not authorized`): Charge credential $\rightarrow$ quarantine $K_n$ $\rightarrow$ failover to $K_{n+1}$ on same model.
  - **Model/Request Policy 403** (e.g. `RESOURCE_EXHAUSTED_TIER`, `MODEL_ACCESS_DENIED`, `LOCATION_NOT_SUPPORTED`): Do NOT penalize the credential $\rightarrow$ trigger **Model Fallback** immediately or surface terminal error.

### Amendment 4: Configurable Model Policy Validated by Benchmarks
- **Problem**: Treating model chains as permanently frozen hardcoded constants prevents adapting to official Google catalog updates and performance realities.
- **Resolution**:
  - Model chains are declared as **configurable policy defaults** in `ModelRouter` and can be overridden via environment variables (`GEMINI_GENERATION_MODELS`, `GEMINI_REMIX_MODELS`, etc.).
  - Benchmark suite must validate structured output reliability, latency, and GameDSL validity before freezing production defaults.

### Amendment 5: Strict Multi-Layer Validation Boundary
- **Problem**: Relying on Gemini's `response_schema` could create false confidence that GameForge validation is unnecessary.
- **Resolution**: Reaffirm the strict validation hierarchy:
  1. Gemini Structured Output (`response_schema` / `response_format`)
  2. Pydantic Type & Schema Coercion (`GameDSL.model_validate`)
  3. Deterministic Normalizer (clamp bounds, fix implied rules, layout defaults)
  4. Security & Script Scanner (zero `eval`, zero arbitrary callbacks)
  5. Requirement Coverage & Gameplay Quality Validator (`GameDepthEvaluator`, `GameplayQualityValidator`)
  6. Reachability & Spatial Feasibility Auto-Repair (`ReachabilityValidator`)
  7. Authoritative Persistent `GameDSL` $\rightarrow$ Phaser 3.88 Runtime Compilation

### Amendment 6: Pinned & Constrained SDK Dependency
- **Problem**: An unbounded `>=2.3.0` dependency could allow breaking upstream SDK updates to silently destabilize production.
- **Resolution**: Constrain dependency to tested compatible range in `backend/requirements.txt`:
  `google-genai>=2.3.0,<3.0.0` (with exact version pinned in `uv.lock` / test environment upon installation).

---

## 3. Official Google Gemini Model Catalog (2026 Assessment)

| Model Identifier | Official Status | Context / Output | Recommended Role | Evaluation & Policy |
| :--- | :---: | :---: | :--- | :--- |
| **`gemini-3.7-flash`** | **STABLE / GA** | 1M / 64k | **Primary Game Generator & Complex Remix** | **Recommended Primary**. Exceptional structured output compliance, agentic planning, thinking controls. |
| **`gemini-3.5-flash-lite`** | **STABLE / GA** | 1M / 64k | **Fast Playtest Critique & Light Patching** | **Recommended Analysis Model**. Sub-second latency, ultra-low cost, reliable JSON formatting for telemetry summaries. |
| **`gemini-3.6-flash`** | **STABLE / GA** | 1M / 64k | **Secondary Generator Fallback** | Highly reliable secondary fallback in the generation chain. |
| **`gemini-3.1-pro-preview`** | **PREVIEW** | 1M / 64k | **Director / Deep Architecture Fallback** | Strong reasoning, higher latency. Suitable for complex campaign generation fallback. |
| **`gemini-3.1-flash-lite`** | **STABLE / GA** | 1M / 64k | **High-Throughput General Fallback** | Final fallback model when quota is constrained. |
| *`gemini-3-flash-preview`* | **DEPRECATED** | — | **Migrate / Remove from Defaults** | Deprecated by Google with no shutdown date announced. Removed from defaults. |
| *`gemini-2.0-* / 1.5-*`* | **DEPRECATED** | — | **FORBIDDEN** | Legacy architectures; explicitly prohibited. |

---

## 4. Task-Based Model Chains & Thinking Budget Policy

### 4.1 Canonical Task Model Chains (Configurable Defaults)

```python
_DEFAULT_CHAINS: dict[TaskType, list[str]] = {
    TaskType.GAME_GENERATION: [
        "gemini-3.7-flash",       # Primary: high-capability generation
        "gemini-3.6-flash",       # Fallback 1: stable generation
        "gemini-3.5-flash",       # Fallback 2: lighter generation
    ],
    TaskType.REMIX: [
        "gemini-3.7-flash",       # Primary: complex mutation
        "gemini-3.6-flash",       # Fallback 1
        "gemini-3.5-flash",       # Fallback 2
    ],
    TaskType.BLUEPRINT: [
        "gemini-3.5-flash-lite",  # Fast blueprint / concept expansion
        "gemini-3.1-flash-lite",  # Light blueprint fallback
    ],
    TaskType.DSL_PATCH: [
        "gemini-3.5-flash",       # Fast semantic repair
        "gemini-3.5-flash-lite",  # Light repair fallback 1
        "gemini-3.1-flash-lite",  # Light repair fallback 2
    ],
    TaskType.PLAYTEST_ANALYSIS: [
        "gemini-3.5-flash-lite",  # Ultra-fast critique
        "gemini-3.1-flash-lite",  # Light critique fallback
    ],
    TaskType.DIRECTOR: [
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
    ],
}
```

### 4.2 Thinking Levels Policy (Gemini 3.7 Flash)
- **`GAME_GENERATION`**: `thinking_level="medium"` (balanced reasoning for progression, mechanics, and enemy variety).
- **`REMIX`**: `thinking_level="medium"` (evaluates diff against prior specification).
- **`DSL_PATCH`**: `thinking_level="low"` (focused semantic correction of specific validation errors).
- **`PLAYTEST_ANALYSIS`**: `thinking_level="low"` / minimal (fast extraction of ratings from deterministic telemetry).
- *Strict Rule*: Model thinking tokens are strictly stripped in the transport adapter and are **never** logged or emitted over SSE.

---

## 5. Comprehensive Error Classification & Routing Matrix

| Error Condition / Status | Classified Error Class | Key Failover? | Model Fallback? | Detailed Routing Action |
| :--- | :--- | :---: | :---: | :--- |
| **401 Unauthorized** | `KEY_AUTH_FAILURE` | **YES** | NO | Key into 60s quarantine $\rightarrow$ advance to next key on same model. |
| **403 Credential Error** (Invalid key, user unauthorized) | `KEY_AUTH_FAILURE` | **YES** | NO | Key into 60s quarantine $\rightarrow$ advance to next key on same model. |
| **403 Model / Policy Error** (Region blocked, model restricted) | `MODEL_UNAVAILABLE` | **NO** | **YES** | Do NOT penalize key $\rightarrow$ advance immediately to next model in chain. |
| **429 Rate Limit / Quota** | `RATE_LIMIT` | **YES** | NO (until keys exhausted) | Key into failure count $\rightarrow$ advance to next key; if all keys rate-limited $\rightarrow$ fallback model. |
| **500 / 503 / 504 Server Flap** | `TRANSIENT_PROVIDER` | **YES** | NO (until keys exhausted) | Increment key failure count $\rightarrow$ try next key; if all exhausted $\rightarrow$ fallback model. |
| **404 / 501 Model Unsupported** | `MODEL_UNAVAILABLE` | **NO** | **YES** | Advance immediately to next model (Key 1 NOT penalized). |
| **400 Bad Request Payload** | `INVALID_REQUEST` | **NO** | **NO** | Terminal failure $\rightarrow$ raise immediately to application. |
| **Content Safety Rejection** | `CONTENT_SAFETY` | **NO** | **NO** | Terminal failure $\rightarrow$ raise immediately to application. |
| **Malformed JSON Response** | `SCHEMA_PARSING` | **NO** | **NO** | Pass candidate to GameForge deterministic normalizer & bounded repair loop. |
| **Client Timeout / Disconnect** | `NETWORK_ERROR` | **YES** | NO | Advance to next key if remaining deadline $\ge 3.0\text{s}$. |

---

## 6. Stateful Remix Architecture with Authoritative Local Fallback

```text
USER REMIX REQUEST ("Make enemies faster and add a boss")
                       │
                       ▼
        Check for cached interaction_id?
              ├── YES ──► Try client.interactions.create(
              │              previous_interaction_id=id,
              │              input=remix_prompt
              │           )
              │           ├── SUCCESS ──► Validate DSL -> Done (Cache new interaction_id)
              │           └── FAIL (404/expired/auth) ──┐
              │                                         │
              └── NO / FALLBACK ◄───────────────────────┘
                       │
                       ▼
       Execute Full DB-Backed Prompt:
       build_remix_prompt(dsl_from_db, spec_from_db, intents)
                       │
                       ▼
         Stateless Interaction Call
```

### Persistence Invariants
- The database `ProjectVersion.game_dsl` and `GameDesignSpec` remain the **sole source of truth**.
- Google Interaction IDs are treated purely as **ephemeral acceleration tokens** stored in in-memory session cache or optional version metadata.
- If an interaction fails, expires, or if failover occurs across different Google accounts, the service immediately falls back to the full database-backed prompt without user-visible disruption.

---

## 7. Transport Abstraction & Single-Line Rollback Strategy

To guarantee risk-free rollout, the application maintains the `AI_TRANSPORT` configuration switch:

```python
# app/config.py
AI_TRANSPORT: str = "interactions"  # Options: "interactions", "legacy_http"
```

- When `AI_TRANSPORT="interactions"`, `FailoverExecutor` instantiates `GeminiInteractionsAdapter` (`google-genai`).
- When `AI_TRANSPORT="legacy_http"`, `FailoverExecutor` falls back directly to `GeminiProvider` (`httpx` OpenAI proxy).
- The `AIProviderRouter` facade ensures callers (`GameGenerationService`, tests, fixtures) require **zero** interface modifications.

---

## 8. Implementation Roadmap (Phases 1–4)

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: DEPENDENCY & INTERACTIONS ADAPTER SETUP                            │
│  - Add constrained `google-genai>=2.3.0,<3.0.0` to requirements.txt         │
│  - Create `app/ai/gemini_interactions_adapter.py` implementing AIProvider   │
│  - Implement Pydantic schema generation, thinking levels & thought stripping│
│  - Unit tests with mock Interaction responses                               │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: FAILOVER EXECUTOR & DEADLINE BUDGETING                             │
│  - Implement dynamic remaining-deadline budgeting in `FailoverExecutor`     │
│  - Enforce global $\le 5$ interaction hard cap                              │
│  - Implement refined 403 error classification (credential vs model)         │
│  - Update task model router defaults to Gemini 3 GA models                  │
│  - Multi-account failover integration tests                                 │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: STATEFUL REMIX & SERVICE INTEGRATION                               │
│  - Wire optional `previous_interaction_id` into `apply_remix`               │
│  - Implement automatic database GameDSL fallback on interaction expiry      │
│  - Keep DSL repair strictly stateless                                       │
│  - Benchmark first-pass validation rate and latency                         │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: STABILIZATION, VERIFICATION & LEGACY CLEANUP                       │
│  - Full test suite verification (all 424 backend tests passing)             │
│  - Deprecate `gemini-3-flash-preview` configuration references              │
│  - Update documentation and create Git checkpoint                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. File Impact Matrix

| File Path | Nature of Change | Purpose |
| :--- | :---: | :--- |
| `backend/requirements.txt` | Modify | Add constrained `google-genai>=2.3.0,<3.0.0`. |
| `backend/app/config.py` | Modify | Add `AI_TRANSPORT`, update model defaults, configure thinking budgets. |
| `backend/app/ai/gemini_interactions_adapter.py` | Create | Official Interactions API transport adapter with structured schema support. |
| `backend/app/ai/failover_executor.py` | Modify | Enforce dynamic remaining deadline, global $\le 5$ budget, and refined 403 classification. |
| `backend/app/ai/model_router.py` | Modify | Update default model chains to Gemini 3 GA catalog. |
| `backend/app/ai/provider.py` | Modify | Refine `classify_ai_error` for granular 403 payload inspection. |
| `backend/app/services/game_generation_service.py` | Modify | Pass `interaction_id` in Remix metadata for optional stateful acceleration. |
| `backend/tests/test_ai_provider.py` | Modify | Add comprehensive tests for deadline budgeting, 403 classification, and Interactions adapter. |

---

## 10. Adversarial Plan Review & Verification Checklist

| Adversarial Challenge | Assessment | Mitigating Design Rule |
| :--- | :---: | :--- |
| **1. Does 45s attempt timeout collide with 60s deadline?** | **NO (Resolved)** | Replaced with dynamic remaining-deadline budgeting: $\text{timeout} = \min(\text{cap}, \text{remaining})$. |
| **2. Can retries multiply beyond acceptable bounds?** | **NO (Resolved)** | Explicitly enforced global hard ceiling of $\le 5$ total Gemini API calls per build. |
| **3. Can a model 403 exhaust all independent Google accounts?** | **NO (Resolved)** | 403 classification parses payload to distinguish credential vs. model-level access errors. |
| **4. Are model chains hardcoded without flexibility?** | **NO (Resolved)** | Chains are declared as configurable policy defaults with benchmark validation and env overrides. |
| **5. Can Gemini schema compliance bypass GameForge rules?** | **NO (Resolved)** | Multi-layer validation boundary (Pydantic $\rightarrow$ Normalizer $\rightarrow$ Security $\rightarrow$ Quality $\rightarrow$ Reachability) remains 100% intact. |
| **6. Can unpinned SDK versions destabilize the build?** | **NO (Resolved)** | SDK dependency is constrained to `google-genai>=2.3.0,<3.0.0` and pinned during installation. |
| **7. Does stateful remix create external data dependency?** | **NO (Resolved)** | Database `GameDSL` is authoritative; interaction IDs are ephemeral acceleration caches with automatic local fallback. |

---

## Plan Verdict

**VERDICT: APPROVED WITH REQUIRED PLAN AMENDMENTS**

The plan incorporates all six required amendments, satisfies all GameForge AI constitution rules, preserves 100% of GameForge's existing validation and policy boundaries, enforces strict multi-account credential independence, and provides a clear, bounded, incremental path to leveraging the Google Gemini Interactions API.
