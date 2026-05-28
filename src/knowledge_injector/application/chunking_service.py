"""Stub chunking service — Phase 4 placeholder."""

from knowledge_injector.domain.models import FileEntry, KnowledgeChunk
from knowledge_injector.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class ChunkingService:
    """Splits documents into overlapping chunks for embedding.

    This is a Phase 1 stub. Full Markdown-aware implementation in Phase 4.
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 150) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, file_entry: FileEntry, document_id=None) -> list[KnowledgeChunk]:
        # TODO Phase 4: implement Markdown header splitting + size fallback
        raise NotImplementedError(
            "ChunkingService.chunk() will be implemented in Phase 4"
        )
