"""
Platform Configuration Module.
Loads environment variables safely using Pydantic Settings.
"""

from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PlatformSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    elixir_env: str = Field(default="development", alias="ELIXIR_ENV")
    elixir_debug: bool = Field(default=True, alias="ELIXIR_DEBUG")
    elixir_secret_key: str = Field(
        default="change-me-in-production-use-strong-entropy-minimum-32-chars",
        alias="ELIXIR_SECRET_KEY",
    )
    allowed_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="ELIXIR_ALLOWED_ORIGINS",
    )

    # Database URLs
    database_url: str = Field(
        default="postgresql+asyncpg://elixir:elixir_secure_pass@localhost:5432/elixir_eim",
        alias="DATABASE_URL",
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg://elixir:elixir_secure_pass@localhost:5432/elixir_eim",
        alias="DATABASE_URL_SYNC",
    )
    database_pool_size: int = Field(default=20, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=10, alias="DATABASE_MAX_OVERFLOW")

    # Redis
    redis_url: str = Field(
        default="redis://:redis_secure_pass@localhost:6379/0",
        alias="REDIS_URL",
    )

    # Object Storage (S3 / MinIO)
    s3_endpoint_url: str = Field(default="http://localhost:9000", alias="S3_ENDPOINT_URL")
    s3_access_key_id: str = Field(default="minioadmin", alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str = Field(default="minioadmin_secure", alias="S3_SECRET_ACCESS_KEY")
    s3_bucket_name: str = Field(default="elixir-eim-content", alias="S3_BUCKET_NAME")
    s3_quarantine_bucket: str = Field(
        default="elixir-eim-quarantine", alias="S3_QUARANTINE_BUCKET"
    )
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")

    # Policy Engine (OPA)
    opa_url: str = Field(default="http://localhost:8181/v1/data/elixir/authz", alias="OPA_URL")

    # Identity & OIDC
    oidc_issuer_url: str = Field(
        default="http://localhost:8080/realms/elixir", alias="OIDC_ISSUER_URL"
    )
    oidc_client_id: str = Field(default="elixir-eim-api", alias="OIDC_CLIENT_ID")
    oidc_client_secret: str = Field(
        default="keycloak-client-secret-placeholder", alias="OIDC_CLIENT_SECRET"
    )
    oidc_algorithms: str = Field(default="RS256", alias="OIDC_ALGORITHMS")

    # Observability
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


# Global platform settings instance
settings = PlatformSettings()
