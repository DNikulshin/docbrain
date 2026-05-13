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

    # На шаге 4 здесь появится database_url; сейчас он не нужен для /health.


settings = Settings()
