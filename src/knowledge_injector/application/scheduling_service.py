"""Stub scheduling service — future CronJob / run-loop helper."""

from knowledge_injector.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class SchedulingService:
    """Handles scheduling logic for the run-loop mode.

    In production the Kubernetes CronJob is the scheduler.
    This service is used only for the optional run-loop dev mode.
    """

    def __init__(self, interval_minutes: int = 60) -> None:
        self.interval_minutes = interval_minutes
