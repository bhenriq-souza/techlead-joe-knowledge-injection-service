"""Database engine and session factory."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from knowledge_injector.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class Database:
    def __init__(self, dsn: str, schema: str = "knowledge") -> None:
        self.dsn = dsn
        self.schema = schema
        self._engine = create_engine(dsn, future=True, pool_pre_ping=True)
        self._session_factory: sessionmaker[Session] = sessionmaker(
            bind=self._engine,
            class_=Session,
            expire_on_commit=False,
            autoflush=False,
        )

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def health_check(self) -> bool:
        try:
            with self.session() as s:
                s.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            logger.warning("database.health_check.failed", error=str(exc))
            return False
