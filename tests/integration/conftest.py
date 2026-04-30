"""Fixtures for integration tests that need a live Postgres."""

from collections.abc import Iterator

import pytest
from sqlalchemy import text

from knowledge_injector.containers import Container
from knowledge_injector.infrastructure.db.database import Database


@pytest.fixture(scope="session")
def db() -> Iterator[Database]:
    database = Container().db()
    if not database.health_check():
        pytest.skip("Postgres not reachable; skipping integration tests")
    yield database


@pytest.fixture
def cleanup_source_names(db: Database) -> Iterator[list[str]]:
    """Tracks knowledge_sources created during a test and removes them afterwards.

    CASCADE on FK constraints removes runs, documents, chunks transitively.
    """
    names: list[str] = []
    yield names
    if not names:
        return
    with db.session() as s:
        s.execute(
            text("DELETE FROM knowledge.knowledge_sources WHERE name = ANY(:names)"),
            {"names": names},
        )
