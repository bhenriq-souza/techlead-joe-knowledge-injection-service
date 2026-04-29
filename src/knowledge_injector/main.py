"""Application entry point."""

from knowledge_injector.containers import Container
from knowledge_injector.infrastructure.logging.logger import configure_logging


def main() -> None:
    """Bootstrap the DI container, configure logging, then hand off to the CLI."""
    # Settings are loaded first so we can configure logging before anything else.
    container = Container()
    settings = container.settings()

    configure_logging(settings.log_level)

    from knowledge_injector.cli.commands import create_cli

    app = create_cli(container)
    app(standalone_mode=True)
