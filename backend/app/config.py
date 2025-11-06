"""Application configuration helpers."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings sourced from environment variables."""

    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = Field(
        default="gpt-5-mini",
        description="Default model used for field extraction",
    )
    extraction_max_chars: int = Field(
        default=6000,
        description="Truncate PDF text to this many characters before sending to the LLM.",
    )
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()


def get_openai_api_key(explicit_key: Optional[str] = None) -> str:
    """Helper to fetch API key, raising if missing."""

    key = explicit_key or get_settings().openai_api_key
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return key
