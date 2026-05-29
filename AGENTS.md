# AGENTS.md — Tech Lead Joe Knowledge Injection Service

## Mission

This repository implements the Tech Lead Joe Knowledge Injection Service: a Python worker that ingests approved documentation changes, chunks documents, generates embeddings, and persists knowledge into PostgreSQL + pgvector for RAG workloads.

The active product direction is event-driven ingestion:

```text
GitHub PR merge
  -> GitHub Actions publishes a normalized event
  -> Pub/Sub
  -> worker consumes event
  -> source catalog lookup
  -> changed-file delta
  -> GitHub API document download
  -> chunking
  -> embedding generation
  -> PostgreSQL/pgvector persistence
```

## Repository Boundaries

This repository owns Python service code, tests, service-specific documentation, database migrations, and service-local examples.

Do not implement Terraform, cluster bootstrap, ArgoCD desired state, or cross-repository architecture governance here. Those belong in `techlead-joe-infra`, `techlead-joe-gitops`, `homelab-infra`, or `homelab-gitops` as appropriate.

## Mandatory Context Files

Before non-trivial planning or editing, read:

1. `project_status.md`
2. `docs/implementation-plan.md`
3. `docs/architecture/knowledge-ingestion-event-driven.md`
4. `README.md`
5. relevant files under `src/`
6. relevant files under `tests/`

If these files disagree, treat `project_status.md` and `docs/architecture/knowledge-ingestion-event-driven.md` as authoritative for current direction.

## Current Status Source of Truth

Use `project_status.md` as the mandatory source of truth for current status, next steps, blockers, and active architectural direction.

Known current implementation state:

- Alembic migrations, domain models, database setup, and SQLAlchemy repositories are implemented.
- `GitRepositoryClient` clone/pull local flow is superseded as the main product path.
- `ChunkingService`, `OllamaEmbeddingsClient`, and `IngestionService` are still stubs.
- Event-driven ingestion work is planned as steps 3.1 through 3.8 and is not implemented yet.

## Architecture Rules

- Keep the domain layer framework-free: dataclasses, enums, and ABC ports only.
- Keep SQLAlchemy, HTTP clients, GitHub, Pub/Sub, and other provider details inside infrastructure adapters.
- Keep orchestration in application services.
- Keep CLI commands thin: bootstrap dependencies, call services, return process results.
- Prefer synchronous implementation unless an ADR or explicit user instruction changes this.
- Validate behavior through ports, application services, and focused tests rather than through provider internals.
- Preserve idempotency: repeated processing of unchanged input must not create duplicate documents or chunks.
- Do not revive `GitRepositoryClient` clone/pull local ingestion as the main production path.

## Safety Rules

- Never commit or print secrets, tokens, database passwords, GitHub credentials, or private connection strings.
- Do not run destructive database operations against shared environments without explicit approval.
- Do not run Terraform, Kubernetes, ArgoCD, or GCP write commands from this repository unless explicitly requested.
- Do not implement Pub/Sub consumers, GitHub API adapters, or worker orchestration unless the active task explicitly targets that planned step.
- Do not add broad compatibility layers or speculative abstractions without a concrete requirement.

## Validation Commands

Use commands that match the current project configuration:

```bash
uv sync
uv run pytest
uv run pytest --cov=src/knowledge_injector --cov-report=term-missing
uv run ruff check .
```

Do not list `uv run mypy .` as required unless mypy is intentionally added to the project.

## Agent Workflow

1. Read the mandatory context files before non-trivial work.
2. Inspect the relevant `src/` and `tests/` files before editing.
3. Prefer the smallest correct change that preserves the hexagonal boundaries.
4. Add or update tests for behavior changes when practical.
5. Run the relevant validation commands or explain why they were not run.
6. Review the diff before reporting completion.

## Forbidden Actions

- Do not follow legacy clone/pull-centered prompts as the main product path.
- Do not move application code into infra, GitOps, or documentation repositories.
- Do not put infrastructure adapter dependencies in `src/knowledge_injector/domain/`.
- Do not introduce asynchronous runtime behavior unless an ADR or explicit instruction requires it.
- Do not remove or rewrite migrations without explicit approval.
- Do not add `.opencode/` skills, subagents, or `opencode.jsonc` until that implementation phase is intentionally started.

## Documentation Sync

After implementation work, check whether these need updates:

- `project_status.md`
- `README.md`
- `docs/implementation-plan.md`
- `docs/architecture/knowledge-ingestion-event-driven.md`
- relevant files under `specs/` when specs exist

When documentation is stale but outside the current task scope, call it out in the final summary instead of silently leaving conflicting guidance.
