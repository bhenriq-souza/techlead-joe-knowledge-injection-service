---
name: postgres-pgvector-sqlalchemy
description: Use when changing PostgreSQL, pgvector, Alembic migrations, SQLAlchemy ORM models, repository adapters, ingestion_runs, knowledge_documents, knowledge_chunks, or vector persistence.
---

# Postgres Pgvector SQLAlchemy

Use this skill for persistence work involving PostgreSQL, pgvector, Alembic, SQLAlchemy, ORM models, and repository adapters.

## Persistence Boundaries

- Keep SQLAlchemy and pgvector details in infrastructure adapters and migrations.
- Keep domain models free of SQLAlchemy metadata, sessions, engine objects, and database-specific types.
- Keep repositories implementing domain ports with explicit session boundaries.
- Keep repository behavior idempotent: upserts and replacements must not create duplicate sources, documents, chunks, or runs for unchanged inputs.

## Database Objects

- Preserve the intent of `ingestion_runs`, `knowledge_documents`, and `knowledge_chunks`.
- Store embeddings in PostgreSQL/pgvector with 768 dimensions unless the project intentionally changes embedding model dimensions.
- Validate 768-dimensional embeddings before persistence.
- Keep document identity stable around source and path semantics.
- Keep chunk replacement deterministic for a document: remove or replace stale chunks and insert the current ordered chunk set.
- Preserve `content_hash` semantics for idempotent document updates.

## Migration Safety

- Do not rewrite, squash, delete, or reorder existing Alembic migrations unless explicitly approved.
- Prefer additive migrations for schema changes.
- Review ORM models, repository mapping code, and migrations together so they remain consistent.
- Do not run destructive database operations against shared environments without explicit approval.

## Secret Safety

- Never print database DSNs containing credentials.
- Redact passwords, tokens, hosts, or usernames when summarizing connection failures.
- Prefer placeholders such as `postgresql+psycopg://user:password@host:5432/dbname` in docs and examples.

## Validation

- Add repository or migration tests when persistence behavior changes.
- Run `uv run pytest` and `uv run ruff check .` when Python code changes.
