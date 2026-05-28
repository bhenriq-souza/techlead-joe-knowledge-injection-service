"""Alembic environment — reads DSN from env vars via AppSettings."""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool, text

from alembic import context

# Make sure the src/ package is importable when alembic runs from project root
sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "src"))

from knowledge_injector.config import AppSettings  # noqa: E402
from knowledge_injector.infrastructure.db.orm import Base  # noqa: E402

# ── Alembic config object ────────────────────────────────────────────────────
alembic_cfg = context.config

if alembic_cfg.config_file_name is not None:
    fileConfig(alembic_cfg.config_file_name)

# Inject the DSN from env vars so alembic.ini doesn't need a hardcoded URL
settings = AppSettings.from_env()
alembic_cfg.set_main_option("sqlalchemy.url", settings.database.dsn)

target_metadata = Base.metadata
SCHEMA = settings.database.schema_


# ── helpers ──────────────────────────────────────────────────────────────────


def _include_object(obj, name, type_, reflected, compare_to):
    """Only manage objects inside the knowledge schema."""
    if type_ == "table":
        return obj.schema == SCHEMA
    return True


def _configure_context(connection, **kwargs):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=SCHEMA,
        include_schemas=True,
        include_object=_include_object,
        compare_type=True,
        **kwargs,
    )


def _ensure_schema_and_extensions(connection) -> None:
    connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


# ── offline mode ─────────────────────────────────────────────────────────────


def run_migrations_offline() -> None:
    url = alembic_cfg.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=SCHEMA,
        include_schemas=True,
        include_object=_include_object,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── online mode ──────────────────────────────────────────────────────────────


def run_migrations_online() -> None:
    connectable = engine_from_config(
        alembic_cfg.get_section(alembic_cfg.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        _configure_context(connection)
        with context.begin_transaction():
            _ensure_schema_and_extensions(connection)
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
