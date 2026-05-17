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


settings = Settings()
