import os
from typing import Dict, List, Union, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings using pydantic-settings."""
    APP_NAME: str = "GameForge API"
    APP_ENV: str = "development"
    DATABASE_URL: str = "sqlite:///./gameforge.db"
    DB_ECHO_SQL: bool = False
    # Both loopback forms are allowed by default: start.bat/vite.config.ts bind
    # and open the frontend at 127.0.0.1:5173, while docs/README reference
    # localhost:5173 -- the two are different browser origins, and a mismatch
    # here means an otherwise-healthy backend rejects the browser's requests
    # with "Disallowed CORS origin" the moment anything talks to it directly
    # (i.e. outside Vite's same-origin dev proxy).
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Hugging Face Settings (Optional - higher rate limits & authenticated hub downloads)
    HF_TOKEN: Optional[str] = None

    # ── AI Hosted Provider Settings ────────────────────────────────────────
    AI_PROVIDER: str = "gemini"
    AI_TRANSPORT: str = "interactions"  # "interactions" (google-genai) or "legacy_http" (httpx OpenAI proxy)
    AI_TIMEOUT_SECONDS: float = 60.0
    AI_REPAIR_TIMEOUT_SECONDS: float = 25.0
    AI_REPAIR_MAX_ATTEMPTS: int = 1
    AI_MAX_RETRIES: int = 2

    # Overall deadline across ALL failover attempts (key + model fallback combined).
    # Enforces dynamic remaining-deadline budgeting: attempt_timeout = min(cap, remaining_deadline).
    AI_OVERALL_DEADLINE_SECONDS: float = 60.0

    # ── Primary Generative Provider: Google Gemini ─────────────────────────
    # GEMINI_API_KEY / GEMINI_API_KEYS support comma-separated credentials
    # representing INDEPENDENTLY configured Google API credentials/projects.
    # Each credential belongs to a separate Google API project for
    # independent quota. Multiple credentials from the same project share
    # project-level quota and do NOT provide independent quota isolation.
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_API_KEYS: Optional[str] = None

    # Default production Gemini model and thinking budget
    GEMINI_MODEL: str = "gemini-3.7-flash"
    GEMINI_THINKING_LEVEL: str = "medium"  # "low", "medium", "high"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai"

    # ── Task-Specific Model Chains (Gemini 3 stable family) ───────────────
    # These are DEFAULT chains.  Override via environment variables.
    # All models in a chain must support response_format=json_object (structured output).
    # Format: comma-separated ordered model IDs, primary first.
    # If not set, model_router.py uses hardcoded Gemini 3 defaults.
    GEMINI_GENERATION_MODELS: Optional[str] = None  # e.g. "gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash"
    GEMINI_REMIX_MODELS: Optional[str] = None       # e.g. "gemini-3.6-flash,gemini-3.7-flash,gemini-3.5-flash"
    GEMINI_DSL_PATCH_MODELS: Optional[str] = None   # e.g. "gemini-3.6-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite"
    GEMINI_BLUEPRINT_MODELS: Optional[str] = None   # e.g. "gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash"
    GEMINI_ANALYSIS_MODELS: Optional[str] = None    # e.g. "gemini-3.5-flash-lite,gemini-3.6-flash,gemini-3.1-flash-lite"
    GEMINI_DIRECTOR_MODELS: Optional[str] = None    # e.g. "gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash"

    # ── Credential Failover / Health Settings ─────────────────────────────
    # KEY_FAILURE_THRESHOLD: consecutive failures before a credential enters cooldown.
    # KEY_AUTH_FAILURE always enters cooldown immediately (regardless of threshold).
    KEY_FAILURE_THRESHOLD: int = 3
    # KEY_COOLDOWN_SECONDS: how long a credential stays in cooldown before becoming
    # eligible again.  Health state is process-local; restart clears all cooldowns.
    KEY_COOLDOWN_SECONDS: int = 300  # 5 minutes

    # ── Groq Fallback Provider (Optional) ─────────────────────────────────
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    # Generic AI settings (mapped dynamically — legacy compatibility)
    AI_MODEL: str = "gemini-3.7-flash"
    AI_API_KEY: Union[str, None] = None
    AI_BASE_URL: Union[str, None] = None

    # Authentication Settings (Phase B7)
    # AUTH_JWT_SECRET is required — the application refuses to start without it.
    # No hardcoded fallback is permitted here: an insecure default would let the
    # backend silently sign/verify auth tokens with a fixed, source-visible secret.
    # Use a strong random secret in production (e.g. `openssl rand -hex 32`).
    # For local development, set this in your .env file.
    # For tests, backend/tests/conftest.py sets a dedicated test-only secret via
    # os.environ before any app module (and therefore this Settings class) is imported.
    # Never commit a real secret to version control.
    AUTH_JWT_SECRET: str = Field(
        ...,
        min_length=16,
        description="Required JWT HS256 signing secret. Must come from the environment "
        "or .env file — there is no insecure default.",
    )
    AUTH_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # IGDB Enrichment Settings (Optional Phase D7)
    IGDB_CLIENT_ID: Optional[str] = None
    IGDB_CLIENT_SECRET: Optional[str] = None
    IGDB_CACHE_TTL_DAYS: int = 7

    # ── Personalization V1 — Feature Flag (Phase 6 / 6.1) ──────────────────────
    # PERSONALIZATION_MODE controls how the personalized re-ranker is applied:
    #   OFF       — no personalization computation
    #   SHADOW    — compute personalized ranking in background; return BASE result
    #   TREATMENT — apply personalized ranking for users in the treatment cohort
    # Phase 7 active setting: TREATMENT (5% controlled treatment cohort).
    PERSONALIZATION_MODE: str = "TREATMENT"

    # Lambda for the additive re-ranking formula:
    #   personalized_score = base_score + (PERSONALIZATION_LAMBDA * personalization_score)
    # Must remain configuration-controlled; not exposed to runtime user input.
    PERSONALIZATION_LAMBDA: float = 0.05

    # Percentage of authenticated users assigned to the TREATMENT cohort (0–100).
    # Deterministic assignment is based on hash(user_id) % 100.
    # Phase 8: 10% controlled treatment expansion.
    PERSONALIZATION_TREATMENT_PCT: int = 10

    # Phase 6.3 Mode-Specific Lambdas for shadow experiment:
    # DISCOVER: 0.05, HIDDEN_GEMS: 0.05, BEST_MATCH: 0.02, POPULAR: 0.00
    PERSONALIZATION_MODE_LAMBDAS: Dict[str, float] = {
        "DISCOVER": 0.05,
        "HIDDEN_GEMS": 0.05,
        "BEST_MATCH": 0.02,
        "POPULAR": 0.00,
    }

    # Maximum acceptable personalization overhead in milliseconds.
    # Requests exceeding this fall back to base ranking (safety budget).
    PERSONALIZATION_LATENCY_BUDGET_MS: float = 50.0

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(
        env_file=(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    def gemini_api_key_pool(self) -> List[str]:
        """
        Ordered, de-duplicated pool of all configured Gemini API credentials.

        Reads GEMINI_API_KEY (which may itself be comma-separated) and
        GEMINI_API_KEYS.  Deduplication preserves the first occurrence's position.

        Each credential should ideally represent an independently configured
        Google API project for quota isolation.  Multiple credentials from the
        same project share project-level quota and do NOT provide independent
        quota isolation, even if they are different key strings.
        """
        candidates: List[str] = []
        if self.GEMINI_API_KEY:
            candidates.extend(self.GEMINI_API_KEY.split(","))
        if self.GEMINI_API_KEYS:
            candidates.extend(self.GEMINI_API_KEYS.split(","))

        pool: List[str] = []
        seen = set()
        for raw in candidates:
            key = (raw or "").strip()
            if key and key not in seen:
                seen.add(key)
                pool.append(key)
        return pool


settings = Settings()
