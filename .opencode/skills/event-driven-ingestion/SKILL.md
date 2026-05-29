---
name: event-driven-ingestion
description: Use ONLY when working on event-driven knowledge ingestion, SourceIngestionEvent contracts, GitHub Actions to Pub/Sub flow, Pub/Sub consumers, GitHub content clients, source catalog rules, branch/environment validation, or incremental sync.
---

# Event-Driven Ingestion

Use this skill only for work on the active event-driven knowledge ingestion path.

## Active Production Path

The authoritative ingestion flow is:

```text
GitHub PR merge
  -> GitHub Actions publishes a normalized event
  -> Pub/Sub
  -> worker consumes event
  -> source catalog lookup
  -> branch/environment validation
  -> changed-file delta
  -> GitHub API document download
  -> chunking
  -> embeddings
  -> PostgreSQL/pgvector persistence
```

Do not implement or promote `GitRepositoryClient` clone/pull local ingestion as the production path. It is superseded by the event-driven design and may only remain as a future local-development or fallback adapter if explicitly requested.

## Scope Rules

- Treat `project_status.md` and `docs/architecture/knowledge-ingestion-event-driven.md` as authoritative when docs disagree.
- Keep the worker source-catalog-driven. The event is not trusted blindly for what to index.
- Enforce branch-to-environment validation before processing changed files.
- Process only allowed and changed files. Do not clone or index the whole repository.
- Handle `added`, `modified`, `removed`, and `renamed` file changes explicitly.
- Keep initial sync and periodic reconciliation limited to allowed catalog sources, not whole-repository indexing.

## Step 3.1 Guardrails

Step 3.1 is domain/contracts work only:

- Create or revise normalized event models such as `SourceIngestionEvent`.
- Model branch-to-environment mapping rules.
- Revise `KnowledgeSource` for provider, environment, branch, allowed paths, and blocked paths.
- Define `RepositoryContentClientPort` for GitHub API content access without local sync.
- Define `IngestionEventConsumerPort` for event consumption.
- Do not implement Pub/Sub adapters in Step 3.1.
- Do not implement GitHub API adapters in Step 3.1.
- Do not implement worker orchestration in Step 3.1.

## Validation

- Add or update tests for event validation, catalog lookup behavior, branch/environment filtering, allowed/blocked path filtering, and idempotency when those behaviors change.
- Run `uv run pytest` and `uv run ruff check .` when Python code changes.
