"""Stub ingestion service — Phase 1 placeholder."""

from knowledge_injector.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class IngestionService:
    """Orchestrates the full knowledge ingestion pipeline.

    This is a Phase 1 stub. Full implementation will be added in subsequent phases.
    """

    def run_once(self) -> None:
        logger.info("ingestion.run_once.started", message="Starting single ingestion run")
        # TODO Phase 2: Git sync + file discovery
        # TODO Phase 3: DB persistence
        # TODO Phase 4: Chunking
        # TODO Phase 5: TEI embeddings
        # TODO Phase 6: Incremental processing
        logger.info("ingestion.run_once.finished", message="Ingestion run complete (stub)")

    def run_loop(self, interval_minutes: int) -> None:
        import time

        logger.info(
            "ingestion.run_loop.started",
            interval_minutes=interval_minutes,
            message=f"Starting ingestion loop with {interval_minutes}m interval",
        )
        while True:
            self.run_once()
            logger.info(
                "ingestion.run_loop.sleeping",
                interval_minutes=interval_minutes,
            )
            time.sleep(interval_minutes * 60)
