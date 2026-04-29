"""Unit tests for Database (engine + session factory)."""

from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from knowledge_injector.infrastructure.db.database import Database


@pytest.fixture
def sqlite_dsn(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def db(sqlite_dsn: str) -> Database:
    database = Database(dsn=sqlite_dsn, schema="knowledge")
    with database.session() as s:
        s.execute(text("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)"))
    return database


class TestDatabaseInit:
    def test_stores_dsn_and_schema(self, sqlite_dsn: str):
        db = Database(dsn=sqlite_dsn, schema="custom")
        assert db.dsn == sqlite_dsn
        assert db.schema == "custom"

    def test_default_schema_is_knowledge(self, sqlite_dsn: str):
        db = Database(dsn=sqlite_dsn)
        assert db.schema == "knowledge"

    def test_creates_engine_and_session_factory(self, sqlite_dsn: str):
        db = Database(dsn=sqlite_dsn)
        assert db._engine is not None
        assert db._session_factory is not None


class TestSessionContextManager:
    def test_yields_sqlalchemy_session(self, db: Database):
        with db.session() as s:
            assert isinstance(s, Session)

    def test_commits_on_success(self, db: Database):
        with db.session() as s:
            s.execute(text("INSERT INTO items (name) VALUES ('alice')"))
        with db.session() as s:
            count = s.execute(text("SELECT COUNT(*) FROM items")).scalar_one()
        assert count == 1

    def test_rolls_back_on_exception(self, db: Database):
        with pytest.raises(RuntimeError, match="boom"):
            with db.session() as s:
                s.execute(text("INSERT INTO items (name) VALUES ('bob')"))
                raise RuntimeError("boom")
        with db.session() as s:
            count = s.execute(text("SELECT COUNT(*) FROM items")).scalar_one()
        assert count == 0

    def test_re_raises_original_exception(self, db: Database):
        class CustomError(Exception):
            pass

        with pytest.raises(CustomError):
            with db.session():
                raise CustomError("propagate me")

    def test_closes_session_after_success(self, db: Database):
        with db.session() as s:
            captured = s
        assert not captured.in_transaction()

    def test_closes_session_after_exception(self, db: Database):
        captured: Session | None = None
        with pytest.raises(RuntimeError):
            with db.session() as s:
                captured = s
                raise RuntimeError("err")
        assert captured is not None
        assert not captured.in_transaction()


class TestHealthCheck:
    def test_returns_true_when_reachable(self, db: Database):
        assert db.health_check() is True

    def test_returns_false_when_session_raises(self, db: Database):
        with patch.object(db, "_session_factory", side_effect=Exception("no db")):
            assert db.health_check() is False

    def test_does_not_raise_on_failure(self, db: Database):
        with patch.object(db, "_session_factory", side_effect=Exception("kaboom")):
            db.health_check()
