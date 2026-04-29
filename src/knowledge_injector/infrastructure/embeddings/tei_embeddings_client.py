"""TEI embeddings client — Phase 5 placeholder."""

import httpx

from knowledge_injector.domain.ports import EmbeddingsClientPort
from knowledge_injector.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class TeiEmbeddingsClient(EmbeddingsClientPort):
    """Calls the Text Embeddings Inference (TEI) OpenAI-compatible endpoint.

    This is a Phase 1 stub. Full implementation in Phase 5.
    """

    def __init__(
        self,
        base_url: str,
        embeddings_path: str,
        model: str,
        dimensions: int = 384,
    ) -> None:
        self.embeddings_url = f"{base_url}{embeddings_path}"
        self.model = model
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        # TODO Phase 5: call TEI /v1/embeddings and return vectors
        raise NotImplementedError("TeiEmbeddingsClient.embed() will be implemented in Phase 5")
