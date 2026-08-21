# 03 — Technology Stack

## Frontend
- React
- TypeScript
- Vite
- Tailwind CSS
- react-router-dom / HashRouter
- React Context

## Backend
- Python 3.12
- FastAPI
- Pydantic v2
- SQLAlchemy 2.0
- SQLite
- Alembic

## Authentication & Security (Phase B7)
- PyJWT (HS256 access tokens)
- pwdlib[argon2] (Argon2 password hashing)
- email-validator (email address validation)
- In-memory sliding window rate limiting

## AI
- Primary Provider: Google Gemini (Gemma 4 31B, API identifier: `gemma-4-31b-it`, OpenAI-compatible REST API)
- Fallback Provider: Groq (Llama 3.1 8B, API identifier: `llama-3.1-8b-instant`, infrastructure availability fallback only)
- Provider abstraction & router (`AIProviderRouter`)
- Structured JSON output with Pydantic validation & bounded repair
- Safe dynamic design logging & provider traceability metadata (zero secret leakage)

## Discovery
- Sentence Transformers (`all-MiniLM-L6-v2`)
- FAISS (`IndexFlatIP`)
- Normalized Steam Insights game catalog
- Deterministic scoring & metadata ranker

## Runtime
- Phaser 3.88.2 with Arcade Physics
- Procedural vector canvas textures (zero external asset requests)
- Mulberry32 deterministic PRNG for reproducible runs
- Deterministic allowlisted rule interpreter (arbitrary JS execution strictly prohibited)

## Transport
- REST for ordinary operations
- SSE for build logs/events

## Deliberately Deferred
Celery, Redis, Kafka, GraphQL, LangChain, LlamaIndex, Kubernetes, microservices, service meshes, and other infrastructure are not approved initially. A real requirement plus an ADR is required before introduction.

## Dependency Rule
Every dependency must solve a concrete problem, reduce complexity, or materially improve the product.
