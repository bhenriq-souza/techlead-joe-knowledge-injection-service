"""CLI commands for knowledge-injector."""

import sys

import click
from dependency_injector.wiring import Provide, inject

from knowledge_injector.application.ingestion_service import IngestionService
from knowledge_injector.config import AppSettings
from knowledge_injector.containers import Container
from knowledge_injector.infrastructure.logging.logger import (
    configure_logging,
    get_logger,
)

logger = get_logger(__name__)


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Knowledge Injector — populates the vector knowledge base from Git sources."""
    ctx.ensure_object(dict)


@cli.command("run-once")
@inject
def run_once(
    ingestion_service: IngestionService = Provide[Container.ingestion_service],
) -> None:
    """Execute a single ingestion run and exit.

    Designed to be triggered by a Kubernetes CronJob.
    """
    settings: AppSettings = Container.settings()
    logger.info(
        "cli.run_once.invoked",
        app_env=settings.app_env,
        source_name=settings.knowledge_source.source_name,
        repo_url=settings.knowledge_source.repo_url,
        branch=settings.knowledge_source.repo_branch,
        db=settings.database.dsn_safe,
        embeddings_model=settings.embeddings.model,
        message="run-once invoked — starting ingestion pipeline",
    )
    try:
        ingestion_service.run_once()
    except Exception as exc:  # noqa: BLE001
        logger.error("cli.run_once.error", error=str(exc), exc_info=True)
        sys.exit(1)


@cli.command("run-loop")
@click.option(
    "--interval",
    default=None,
    type=int,
    help="Override INGESTION_INTERVAL_MINUTES for this session.",
)
@inject
def run_loop(
    interval: int | None,
    ingestion_service: IngestionService = Provide[Container.ingestion_service],
) -> None:
    """Run ingestion in a continuous loop (development / non-Kubernetes mode).

    The preferred production scheduler is Kubernetes CronJob using run-once.
    """
    settings: AppSettings = Container.settings()
    effective_interval = interval or settings.ingestion.interval_minutes
    logger.info(
        "cli.run_loop.invoked",
        interval_minutes=effective_interval,
        message="run-loop invoked — entering continuous ingestion loop",
    )
    try:
        ingestion_service.run_loop(interval_minutes=effective_interval)
    except KeyboardInterrupt:
        logger.info(
            "cli.run_loop.interrupted", message="Interrupted by user, shutting down"
        )
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        logger.error("cli.run_loop.error", error=str(exc), exc_info=True)
        sys.exit(1)


@cli.command("db-migrate")
@click.option("--revision", default="head", show_default=True, help="Target revision.")
def db_migrate(revision: str) -> None:
    """Run Alembic migrations up to REVISION (default: head).

    Equivalent to: alembic upgrade head
    """
    from alembic import command as alembic_command
    from alembic.config import Config as AlembicConfig
    from pathlib import Path

    ini_path = Path(__file__).resolve().parents[3] / "alembic.ini"
    alembic_cfg = AlembicConfig(str(ini_path))
    logger.info("cli.db_migrate.started", revision=revision)
    alembic_command.upgrade(alembic_cfg, revision)
    logger.info("cli.db_migrate.finished", revision=revision)


def create_cli(container: Container) -> click.Group:
    """Wire the container and return the CLI group."""
    container.wire(modules=["knowledge_injector.cli.commands"])
    return cli
