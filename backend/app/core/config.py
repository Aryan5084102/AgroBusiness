"""Application configuration with strict environment-variable validation.

Settings are loaded once and cached. Missing or malformed required variables
fail fast at startup rather than surfacing as runtime errors later.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, PostgresDsn, RedisDsn, TypeAdapter, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Validate DSN shape at load time while keeping the stored type as ``str`` for
# ergonomic use with SQLAlchemy / redis clients.
_postgres_adapter = TypeAdapter(PostgresDsn)
_redis_adapter = TypeAdapter(RedisDsn)

Environment = Literal["development", "test", "staging", "production"]


class Settings(BaseSettings):
    """Validated application settings sourced from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Meta -------------------------------------------------------------
    environment: Environment = "development"
    debug: bool = False
    app_name: str = "AgriFlow ERP"
    api_v1_prefix: str = "/api/v1"

    # --- Datastores -------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://agriflow:agriflow@localhost:5432/agriflow",
    )
    redis_url: str = Field(default="redis://localhost:6379/0")

    # --- Security ---------------------------------------------------------
    secret_key: str = Field(default="dev-insecure-change-me", min_length=8)
    access_token_ttl_seconds: int = 900  # 15 minutes
    refresh_token_ttl_seconds: int = 60 * 60 * 24 * 14  # 14 days

    # --- CORS -------------------------------------------------------------
    # NoDecode: keep pydantic-settings from JSON-decoding the env value so a
    # plain comma-separated string works (handled by ``_split_cors`` below).
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # --- Object storage ---------------------------------------------------
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "agriflow"
    s3_secret_key: str = "agriflow-secret"
    s3_bucket: str = "agriflow"
    s3_region: str = "us-east-1"

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, value: str) -> str:
        _postgres_adapter.validate_python(value)
        return value

    @field_validator("redis_url")
    @classmethod
    def _validate_redis_url(cls, value: str) -> str:
        _redis_adapter.validate_python(value)
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, value: object) -> object:
        """Accept a comma-separated string or a JSON/list for CORS origins."""
        if isinstance(value, str) and not value.startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def enforce_production_safety(self) -> None:
        """Reject insecure defaults when running in production."""
        if self.is_production and self.secret_key == "dev-insecure-change-me":
            raise RuntimeError("SECRET_KEY must be set to a strong value in production.")


@lru_cache
def get_settings() -> Settings:
    """Return a cached, validated Settings instance."""
    settings = Settings()
    settings.enforce_production_safety()
    return settings
