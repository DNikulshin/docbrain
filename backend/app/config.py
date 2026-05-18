from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "docbrain-backend"
    app_version: str = "0.1.0"
    environment: str = Field(default="development")

    database_url: str = Field(
        ...,
        description="Async SQLAlchemy URL, например postgresql+asyncpg://user:pass@host:5432/db",
    )

    log_level: str = "INFO"
    log_format: Literal["console", "json"] = "console"

    embedding_provider: Literal["stub", "openrouter"] = "stub"
    embedding_dim: int = 1536
    chunk_size: int = 800
    chunk_overlap: int = 100
    max_upload_bytes: int = 10 * 1024 * 1024

    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    openrouter_timeout: float = 30.0
    openrouter_retries: int = 2
    embedding_batch_size: int = 96

    minio_endpoint: str | None = None
    minio_public_endpoint: str | None = None
    minio_access_key: str | None = None
    minio_secret_key: str | None = None
    minio_bucket: str = "docbrain-files"
    minio_presign_ttl_sec: int = 3600


settings = Settings()
