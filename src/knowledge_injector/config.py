"""Application configuration loaded from environment variables."""

import os

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_csv(value: str | list[str], default: list[str]) -> list[str]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        return [p.strip() for p in value.split(",") if p.strip()]
    return default


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    db: str = Field(default="homelab_ai")
    user: str = Field(default="knowledge_injector")
    password: str = Field(default="change-me")
    schema_: str = Field(default="knowledge", alias="POSTGRES_SCHEMA")

    @property
    def dsn(self) -> str:
        return (
            f"postgresql+psycopg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.db}"
        )

    @property
    def dsn_safe(self) -> str:
        """DSN without credentials for logging."""
        return f"postgresql://{self.host}:{self.port}/{self.db}"


class KnowledgeSourceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KNOWLEDGE_",
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    source_name: str = Field(default="default-source", alias="KNOWLEDGE_SOURCE_NAME")
    repo_url: str = Field(default="", alias="KNOWLEDGE_REPO_URL")
    repo_branch: str = Field(default="main", alias="KNOWLEDGE_REPO_BRANCH")
    repo_base_path: str = Field(default="", alias="KNOWLEDGE_REPO_BASE_PATH")
    repo_auth_mode: str = Field(default="none", alias="KNOWLEDGE_REPO_AUTH_MODE")


class IngestionSettings(BaseSettings):
    """Ingestion configuration.

    Note: ``include_patterns`` and ``exclude_patterns`` accept comma-separated
    strings in environment variables, e.g.::

        INGESTION_INCLUDE_PATTERNS=**/*.md,**/*.txt,**/*.yaml
    """

    model_config = SettingsConfigDict(
        env_prefix="INGESTION_",
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    interval_minutes: int = Field(default=60)
    workdir: str = Field(default="/tmp/knowledge-injector")

    # Raw strings — parsed into lists via computed_field below.
    # Using str avoids pydantic-settings trying to JSON-decode comma-separated values.

    include_patterns_raw: str = Field(
        default="**/*.md,**/*.txt,**/*.yaml,**/*.yml",
        alias="INGESTION_INCLUDE_PATTERNS",
    )
    exclude_patterns_raw: str = Field(
        default=".git/**,node_modules/**,.venv/**",
        alias="INGESTION_EXCLUDE_PATTERNS",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def include_patterns(self) -> list[str]:
        return _parse_csv(
            self.include_patterns_raw,
            default=["**/*.md", "**/*.txt", "**/*.yaml", "**/*.yml"],
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def exclude_patterns(self) -> list[str]:
        return _parse_csv(
            self.exclude_patterns_raw,
            default=[".git/**", "node_modules/**", ".venv/**"],
        )


class EmbeddingsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EMBEDDINGS_",
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    provider: str = Field(default="ollama")
    model: str = Field(default="nomic-embed-text")
    dimensions: int = Field(default=768)


class OllamaSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OLLAMA_", extra="ignore", env_file=".env", env_file_encoding="utf-8"
    )

    base_url: str = Field(default="http://127.0.0.1:11434")
    embeddings_path: str = Field(default="/api/embed")

    @property
    def embeddings_url(self) -> str:
        return f"{self.base_url}{self.embeddings_path}"


class ChunkingSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CHUNK_", extra="ignore", env_file=".env", env_file_encoding="utf-8"
    )

    size: int = Field(default=1000)
    overlap: int = Field(default=150)


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore", env_file=".env", env_file_encoding="utf-8"
    )

    app_env: str = Field(default="dev")
    log_level: str = Field(default="INFO")

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    knowledge_source: KnowledgeSourceSettings = Field(
        default_factory=KnowledgeSourceSettings
    )
    ingestion: IngestionSettings = Field(default_factory=IngestionSettings)
    embeddings: EmbeddingsSettings = Field(default_factory=EmbeddingsSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)

    @classmethod
    def from_env(cls) -> "AppSettings":
        return cls(
            database=DatabaseSettings(),
            knowledge_source=KnowledgeSourceSettings(),
            ingestion=IngestionSettings(),
            embeddings=EmbeddingsSettings(),
            ollama=OllamaSettings(),
            chunking=ChunkingSettings(),
        )
