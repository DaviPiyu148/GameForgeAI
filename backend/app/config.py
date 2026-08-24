import os
from typing import List, Union, Optional
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

    # AI Hosted Provider Settings
    AI_PROVIDER: str = "gemini"
    AI_TIMEOUT_SECONDS: float = 150.0
    AI_MAX_RETRIES: int = 2

    # Primary Generative Provider: Google Gemini
    GEMINI_API_KEY: Optional[str] = None
    # Additional Gemini API keys for rotation, comma-separated (e.g. "key_a,key_b,key_c").
    # Combined with GEMINI_API_KEY to form the full rotation pool -- lets a single
    # deployment spread requests across multiple keys/projects to stay under each
    # key's individual rate limit rather than being bottlenecked by one key.
    GEMINI_API_KEYS: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3-flash-preview"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai"

    # Groq Fallback Provider
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    # Generic AI settings (mapped dynamically)
    AI_MODEL: str = "gemini-3-flash-preview"
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
        Ordered, de-duplicated pool of all configured Gemini API keys: `GEMINI_API_KEY`
        (if set) followed by each key in the comma-separated `GEMINI_API_KEYS` list.
        Used by RotatingGeminiProvider to round-robin requests across keys.
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
