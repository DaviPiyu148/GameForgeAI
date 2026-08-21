# ADR-006 — Hosted LLM Provider Abstraction

**Status:** Accepted

## Context
Initial design documentation referenced local model runtimes (such as Ollama). However, hackathon execution environments and developer hardware lack the dedicated GPU/VRAM resources necessary for performant local inference.

## Decision
GameForge AI uses a **Hosted LLM API** for all model inference behind an internal provider abstraction (`AIProvider`).

- The backend communicates exclusively with the hosted LLM provider.
- The frontend **NEVER** communicates directly with any LLM provider and receives zero provider credentials.
- The backend isolates provider-specific API protocols inside an `AIProvider` boundary.

### Architecture Pipeline
```text
FastAPI (BuildService)
  ↓
AIProvider Abstraction
  ↓
Hosted LLM Provider (REST / JSON mode)
  ↓
Structured JSON Response
  ↓
Pydantic Schema Validation (Game DSL)
  ↓
Bounded Repair Loop (if invalid)
  ↓
Validated Game DSL Artifact
  ↓
Build Pipeline / Project Persistence
```

## Rationale
1. **Hardware Independence**: Eliminates local GPU, VRAM, CUDA, and model server dependencies.
2. **Security**: Provider API keys remain strictly backend-only and are never exposed to clients.
3. **Quality & Structure**: Leverages high-performance hosted models capable of reliable structured JSON output.
4. **Provider Agility**: Swapping models or providers (e.g. Gemini, OpenAI, Groq, Anthropic) requires modifying only the provider adapter, with zero changes to business logic or generation pipelines.
5. **Robust Error Handling**: Provider-specific rate limits, timeouts, and network issues are mapped to internal application error taxonomies.

## Requirements & Constraints
- Provider and model must be configurable via environment variables (`AI_PROVIDER`, `AI_MODEL`, `AI_API_KEY`, `AI_BASE_URL`, `AI_TIMEOUT_SECONDS`, `AI_MAX_RETRIES`).
- Strict timeout enforcement and bounded retry/repair loops (maximum 2 retries).
- No vendor-specific code or SDK leaks into domain services or repositories.
- Zero local LLM fallbacks (local inference is unsupported).
