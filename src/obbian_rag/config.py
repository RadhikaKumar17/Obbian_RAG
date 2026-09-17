from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="RAG_", extra="ignore")
    environment: Literal["development", "production", "test"] = "development"
    provider: Literal["offline", "groq"] = "offline"
    api_key: SecretStr = SecretStr("")
    groq_api_key: SecretStr = SecretStr("")
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    generation_model: str = "llama-3.3-70b-versatile"
    dimensions: int = Field(default=384, ge=64, le=3072)
    data_dir: Path = Path("data")
    index_dir: Path = Path("storage")
    model_cache_dir: Path = Path("storage/models")
    top_k: int = Field(default=4, ge=1, le=8)
    min_similarity: float = Field(default=0.25, ge=0, le=1)
    timeout_seconds: float = Field(default=20, ge=1, le=60)
    requests_per_minute: int = Field(default=30, ge=1, le=600)
    max_concurrency: int = Field(default=4, ge=1, le=16)
    bootstrap: bool = True

    @model_validator(mode="after")
    def validate_secrets(self):
        if self.environment == "production" and len(self.api_key.get_secret_value()) < 32:
            raise ValueError("Production requires a random RAG_API_KEY of at least 32 characters.")
        if self.environment == "production" and self.provider != "groq":
            raise ValueError("Offline mode is for tests and local demonstrations, not production.")
        if self.provider == "groq" and not self.groq_api_key.get_secret_value():
            raise ValueError("RAG_GROQ_API_KEY is required for the Groq provider.")
        if self.provider == "groq" and (
            self.embedding_model != "BAAI/bge-small-en-v1.5" or self.dimensions != 384
        ):
            raise ValueError("This release uses BAAI/bge-small-en-v1.5 with 384 dimensions.")
        return self

    @property
    def profile(self):
        return f"{self.provider}:{self.embedding_model if self.provider == 'openai' else 'hash-v1'}:{self.dimensions}"
