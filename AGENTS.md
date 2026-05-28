# AGENTS.md — Tech Lead Joe Knowledge Injection Service

## Mission

This repository implements the Knowledge Injection Service for Tech Lead Joe.

The service ingests allowed documentation changes from GitHub events, chunks documents, generates embeddings, and persists them into PostgreSQL + pgvector for RAG.

## Mandatory context files

Before planning or editing, read:

1. `project_status.md`
2. `docs/implementation-plan.md`
3. `docs/architecture/knowledge-ingestion-event-driven.md`
4. `README.md`
5. relevant files under `src/`

## Current architectural direction

The previous clone/pull local repository flow is SUPERSEDED.

The active direction is:

GitHub PR merge
→ GitHub Actions publishes normalized event to Pub/Sub
→ Worker consumes event
→ Worker queries source catalog
→ Worker computes delta
→ Worker downloads allowed docs via GitHub API
→ Worker updates documents, chunks, embeddings in PostgreSQL

Do not implement new features based on the old GitRepositoryClient path unless explicitly asked.

## Current status

Use `project_status.md` as the source of truth.

Known stubs:
- `ChunkingService`
- `OllamaEmbeddingsClient`
- `IngestionService`
- event-driven ingestion components for steps 3.1 to 3.8

## Architecture rules

- Keep domain pure: dataclasses and ABC ports only.
- Do not introduce framework dependencies into domain.
- Keep SQLAlchemy inside infrastructure adapters.
- Keep orchestration in application services.
- Prefer synchronous implementation unless an ADR changes this.
- Preserve idempotency: repeated ingestion with no changes must create zero new chunks.
- Do not revive the superseded clone/pull flow.

## Validation commands

Use these before finishing any implementation task:

```bash
uv sync
uv run pytest
uv run pytest --cov
uv run ruff check .
uv run mypy .