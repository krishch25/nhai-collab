"""Application configuration via environment variables."""

from functools import lru_cache
from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central app configuration loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    env: Literal["dev", "staging", "prod"] = "dev"

    # Database
    database_url: str = "sqlite:///./taxonomy.db"

    # ChromaDB
    chroma_persist_path: str = "./chroma_data"

    # LLM providers and models
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    nvidia_api_key: Optional[str] = None
    ollama_cloud_api_key: Optional[str] = None

    # Default model choices (can be overridden per deployment)
    llm_provider: Literal["openai", "anthropic", "openrouter", "nvidia", "ollama_cloud", "dummy"] = "openai"
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    anthropic_chat_model: str = "claude-3-5-sonnet-latest"
    openrouter_chat_model: str = "openai/gpt-4o-mini"
    nvidia_chat_model: str = "moonshotai/kimi-k2.5"
    ollama_cloud_chat_model: str = "kimi-k2.5"

    # Specific agent models (if None, falls back to default openrouter_chat_model etc.)
    rule_generator_model: Optional[str] = None
    decision_maker_model: Optional[str] = None
    quality_control_model: Optional[str] = None

    def get_database_url(self) -> str:
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()

