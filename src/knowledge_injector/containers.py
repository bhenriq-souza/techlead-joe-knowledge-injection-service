"""Dependency Injection container built with dependency-injector."""

from dependency_injector import containers, providers

from knowledge_injector.application.chunking_service import ChunkingService
from knowledge_injector.application.ingestion_service import IngestionService
from knowledge_injector.application.scheduling_service import SchedulingService
from knowledge_injector.config import AppSettings
from knowledge_injector.infrastructure.db.database import Database
from knowledge_injector.infrastructure.embeddings.ollama_embeddings_client import (
    OllamaEmbeddingsClient,
)
from knowledge_injector.infrastructure.git.git_repository_client import (
    GitRepositoryClient,
)


class Container(containers.DeclarativeContainer):
    """Application-level DI container.

    All dependencies are wired here. To swap an adapter (e.g., replace Ollama with
    another embeddings provider), change only the relevant provider below.
    """

    wiring_config = containers.WiringConfiguration(
        modules=[
            "knowledge_injector.cli.commands",
        ]
    )

    settings: providers.Object[AppSettings] = providers.Object(AppSettings.from_env())

    # ── Infrastructure ──────────────────────────────────────────────────────

    db: providers.Singleton[Database] = providers.Singleton(
        Database,
        dsn=settings.provided.database.dsn,
        schema=settings.provided.database.schema_,
    )

    git_client: providers.Factory[GitRepositoryClient] = providers.Factory(
        GitRepositoryClient,
        repo_url=settings.provided.knowledge_source.repo_url,
        branch=settings.provided.knowledge_source.repo_branch,
        workdir=settings.provided.ingestion.workdir,
        auth_mode=settings.provided.knowledge_source.repo_auth_mode,
    )

    embeddings_client: providers.Factory[OllamaEmbeddingsClient] = providers.Factory(
        OllamaEmbeddingsClient,
        base_url=settings.provided.ollama.base_url,
        embeddings_path=settings.provided.ollama.embeddings_path,
        model=settings.provided.embeddings.model,
        dimensions=settings.provided.embeddings.dimensions,
    )

    # ── Application services ─────────────────────────────────────────────────

    chunking_service: providers.Factory[ChunkingService] = providers.Factory(
        ChunkingService,
        chunk_size=settings.provided.chunking.size,
        chunk_overlap=settings.provided.chunking.overlap,
    )

    scheduling_service: providers.Factory[SchedulingService] = providers.Factory(
        SchedulingService,
        interval_minutes=settings.provided.ingestion.interval_minutes,
    )

    ingestion_service: providers.Factory[IngestionService] = providers.Factory(
        IngestionService,
    )
