"""Ollama embeddings client — Phase 5 placeholder."""

import httpx

from knowledge_injector.domain.ports import EmbeddingsClientPort
from knowledge_injector.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class OllamaEmbeddingsClient(EmbeddingsClientPort):
    """Calls the Ollama /api/embed endpoint to generate text embeddings.

    This is a Phase 1 stub. Full implementation in Phase 5.
    """

    def __init__(
        self,
        base_url: str,
        embeddings_path: str,
        model: str,
        dimensions: int = 768,
    ) -> None:
        self.embeddings_url = f"{base_url}{embeddings_path}"
        self.model = model
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        # TODO Phase 5: POST to Ollama /api/embed and return vectors
        raise NotImplementedError("OllamaEmbeddingsClient.embed() will be implemented in Phase 5")
