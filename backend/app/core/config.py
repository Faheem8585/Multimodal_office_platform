"""Twelve-factor configuration via environment variables.

Settings are environment-aware (dev/staging/prod). No secrets are hardcoded;
in production they should be injected by a secrets manager (Vault / AWS SM)
into the process environment. `.env` is for local development only.
"""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    environment: Environment = Environment.DEV
    debug: bool = False
    project_name: str = "Office Platform"
    api_v1_prefix: str = "/api/v1"

    # --- Security ---
    # In prod this MUST be supplied via the environment / secrets manager.
    jwt_secret: str = Field(default="dev-only-insecure-change-me", min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 900  # 15 min
    refresh_token_ttl_seconds: int = 60 * 60 * 24 * 14  # 14 days
    cors_origins: list[str] = ["http://localhost:5173"]

    # --- Database ---
    database_url: PostgresDsn = Field(  # type: ignore[assignment]
        default="postgresql+asyncpg://office:office@localhost:5432/office"
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # --- Redis (cache + celery broker + rate limit) ---
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")  # type: ignore[assignment]

    # --- Object storage (S3-compatible, MinIO locally) ---
    s3_endpoint_url: str | None = None  # None => use AWS default
    s3_bucket: str = "office-documents"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"
    storage_local_fallback_dir: str = "/tmp/office-storage"

    # --- AI / RAG ---
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384
    # Provider: "anthropic" (cloud, paid), "ollama" (local, free), or "echo"
    # (extractive fallback, free). Unavailable providers fall back to echo.
    llm_provider: str = "anthropic"
    anthropic_api_key: str | None = None
    llm_model: str = "claude-opus-4-8"
    # Local LLM via Ollama (used when llm_provider="ollama").
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"

    # --- Observability ---
    sentry_dsn: str | None = None
    otel_exporter_endpoint: str | None = None
    log_level: str = "INFO"

    # --- Rate limiting ---
    rate_limit_default: str = "200/minute"

    @field_validator("jwt_secret")
    @classmethod
    def _no_default_in_prod(cls, v: str, info) -> str:  # type: ignore[no-untyped-def]
        # Cross-field validation against environment happens in model_post_init.
        return v

    def model_post_init(self, __context) -> None:  # type: ignore[no-untyped-def]
        if self.environment == Environment.PROD:
            if self.jwt_secret == "dev-only-insecure-change-me":
                raise ValueError("JWT_SECRET must be set in production")
            if len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be >= 32 chars in production (HS256)")
            if self.debug:
                raise ValueError("DEBUG must be False in production")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
