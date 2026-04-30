"""Port interfaces (abstract base classes) defining the contracts for infrastructure adapters."""

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy.orm import Session

from knowledge_injector.domain.models import (
    FileEntry,
    IngestionRun,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSource,
)


class RepositoryClientPort(ABC):
    """Port for interacting with a version-controlled knowledge source."""

    @abstractmethod
    def sync(self) -> str:
        """Sync the local working copy and return the current commit SHA."""

    @abstractmethod
    def list_files(
        self,
        base_path: str,
        include_patterns: list[str],
        exclude_patterns: list[str],
    ) -> list[FileEntry]:
        """List all eligible files matching the given patterns."""


class EmbeddingsClientPort(ABC):
    """Port for generating vector embeddings from text."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""


class KnowledgeSourceRepositoryPort(ABC):
    """Port for persisting KnowledgeSource entities."""

    @abstractmethod
    def upsert(self, source: KnowledgeSource, session: Session) -> KnowledgeSource:
        """Insert or update a knowledge source, returning the persisted entity."""

    @abstractmethod
    def find_by_name(self, name: str, session: Session) -> KnowledgeSource | None:
        """Find a knowledge source by its unique name."""


class IngestionRunRepositoryPort(ABC):
    """Port for persisting IngestionRun entities."""

    @abstractmethod
    def create(self, run: IngestionRun, session: Session) -> IngestionRun:
        """Persist a new ingestion run."""

    @abstractmethod
    def update(self, run: IngestionRun, session: Session) -> IngestionRun:
        """Update an existing ingestion run."""

    @abstractmethod
    def find_by_id(self, run_id: UUID, session: Session) -> IngestionRun | None:
        """Find an ingestion run by ID."""


class KnowledgeDocumentRepositoryPort(ABC):
    """Port for persisting KnowledgeDocument entities."""

    @abstractmethod
    def upsert(self, document: KnowledgeDocument, session: Session) -> KnowledgeDocument:
        """Insert or update a document, returning the persisted entity."""

    @abstractmethod
    def find_by_source_and_path(
        self, source_id: UUID, path: str, session: Session
    ) -> KnowledgeDocument | None:
        """Find a document by its source and path."""

    @abstractmethod
    def find_active_by_source(
        self, source_id: UUID, session: Session
    ) -> list[KnowledgeDocument]:
        """List all active documents for a given source."""

    @abstractmethod
    def mark_deleted(self, document_id: UUID, session: Session) -> None:
        """Soft-delete a document."""


class KnowledgeChunkRepositoryPort(ABC):
    """Port for persisting KnowledgeChunk entities."""

    @abstractmethod
    def replace_for_document(
        self, document_id: UUID, chunks: list[KnowledgeChunk], session: Session
    ) -> list[KnowledgeChunk]:
        """Replace all chunks for a document, returning the newly persisted ones."""

    @abstractmethod
    def delete_for_document(self, document_id: UUID, session: Session) -> int:
        """Delete all chunks for a document, returning the count deleted."""
