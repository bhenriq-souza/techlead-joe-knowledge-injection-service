# SKILL.md — Knowledge Injection Service Agent Context

## 1. Role and Mission

You are an expert Python backend, DevSecOps, and AI infrastructure agent helping develop the `knowledge-injection-service`.

Your mission is to evolve this repository safely and consistently, preserving its architecture and helping implement the MVP for the Tech Lead Joe platform.

This service is a Python worker responsible for:

- Monitoring Git repositories.
- Extracting knowledge files from repositories.
- Reading Markdown, YAML, and TXT files.
- Splitting documents into chunks.
- Generating embeddings using Ollama.
- Persisting sources, ingestion runs, documents, chunks, and vectors in PostgreSQL with pgvector.
- Running as a Kubernetes CronJob in production-like environments.
- Running locally in one-shot or loop mode during development.

The service is part of a broader AI/RAG platform where repository documentation becomes living knowledge for LLM-powered incident analysis, architecture support, and technical assistance.

---

## 2. Project Snapshot

Repository name:

```text
knowledge-injection-service
```

Main package:

```text
src/knowledge_injector
```

Primary execution mode:

```bash
python -m knowledge_injector run-once
python -m knowledge_injector run-loop
python -m knowledge_injector db-migrate
```

Main runtime:

- Python 3.12+
- uv
- Click
- pydantic-settings
- dependency-injector
- SQLAlchemy 2.0+
- psycopg 3
- Alembic
- PostgreSQL 16+
- pgvector
- GitPython
- httpx
- structlog
- pytest

Main infrastructure dependencies:

- PostgreSQL with pgvector extension.
- Ollama embedding server.
- Docker / Docker Compose.
- Kubernetes CronJob in later phases.

Current embedding provider:

```text
Ollama
```

Current embedding model:

```text
nomic-embed-text
```

Current embedding dimension:

```text
768
```

Do not reintroduce TEI as the default embedding provider unless explicitly requested.

---

## 3. Repository Structure

Expected high-level structure:

```text
techlead-joe-knowledge-injection-service/
├── src/knowledge_injector/
│   ├── __main__.py
│   ├── main.py
│   ├── config.py
│   ├── containers.py
│   ├── domain/
│   │   ├── models.py
│   │   └── ports.py
│   ├── application/
│   │   ├── ingestion_service.py
│   │   ├── chunking_service.py
│   │   └── scheduling_service.py
│   ├── infrastructure/
│   │   ├── db/
│   │   │   ├── database.py
│   │   │   ├── orm.py
│   │   │   ├── repositories.py
│   │   │   └── migrations/
│   │   ├── git/
│   │   │   └── git_repository_client.py
│   │   ├── embeddings/
│   │   │   └── ollama_embeddings_client.py
│   │   └── logging/
│   │       └── logger.py
│   └── cli/
│       └── commands.py
├── tests/
│   ├── unit/
│   └── integration/
├── docs/
│   ├── implementation-plan.md
│   └── agents/prompts/
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
└── pyproject.toml
```

When adding or editing files, keep the current structure and naming conventions.

---

## 4. Architecture Principles

This project follows Hexagonal Architecture / Ports and Adapters.

Preserve the separation between:

```text
domain/
application/
infrastructure/
cli/
```

### 4.1 Domain Layer

Path:

```text
src/knowledge_injector/domain
```

Contains:

- Domain dataclasses.
- Port interfaces / ABCs.
- Business contracts.

Rules:

- Do not import infrastructure code into domain.
- Do not couple domain models to SQLAlchemy, httpx, GitPython, Click, Alembic, or dependency-injector.
- Keep domain objects simple and explicit.
- Prefer dataclasses unless there is a strong reason to introduce another model type.
- Domain should describe the business concepts of knowledge ingestion, not provider-specific details.

### 4.2 Application Layer

Path:

```text
src/knowledge_injector/application
```

Contains orchestration services:

- `IngestionService`
- `ChunkingService`
- `SchedulingService`

Rules:

- Application services coordinate domain ports.
- Application services should depend on abstractions, not concrete adapters.
- Avoid direct SQLAlchemy, GitPython, or httpx usage here.
- Do not hide important ingestion decisions inside infrastructure adapters.
- Keep orchestration readable and testable.
- Prefer explicit counters and ingestion state transitions.

### 4.3 Infrastructure Layer

Path:

```text
src/knowledge_injector/infrastructure
```

Contains adapters:

- Database engine/session.
- ORM models.
- Repository implementations.
- Git client.
- Ollama embeddings client.
- Logging setup.
- Alembic migrations.

Rules:

- Infrastructure implements domain ports.
- Infrastructure can depend on external libraries.
- Keep external provider details here.
- Convert infrastructure exceptions into meaningful application/domain errors when useful.
- Do not leak provider-specific concepts into domain unnecessarily.

### 4.4 CLI Layer

Path:

```text
src/knowledge_injector/cli
```

Rules:

- CLI should remain thin.
- CLI should call bootstrapping/container code and invoke application services.
- Avoid putting business logic inside Click commands.
- CLI commands should be easy to test.

### 4.5 Dependency Injection

Path:

```text
src/knowledge_injector/containers.py
```

Rules:

- Wire concrete implementations through the DI container.
- Do not manually instantiate infrastructure classes across the codebase when they should be provided by the container.
- Keep configuration centralized via `config.py`.
- When adding a new adapter, wire it through the container and update tests.

---

## 5. Current Development State

The project is being implemented in phases.

Completed:

- Phase 1: Bootstrap, configuration, CLI, logging, DI.
- Phase 2: Database engine and repositories.

Pending or incomplete:

- Phase 3: `GitRepositoryClient`
- Phase 4: `ChunkingService`
- Phase 5: `OllamaEmbeddingsClient`
- Phase 6: `IngestionService`
- Phase 7: End-to-end wiring and smoke tests.
- Phase 8: Kubernetes deployment.

Important: some files may already exist as stubs. Do not assume a stub is complete. Inspect the implementation before using it as a dependency.

---

## 6. High-Priority Backlog Awareness

Before implementing new features, check the current repository state.

Known high-priority items:

1. Commit or preserve the migration that changes embeddings from `vector(384)` to `vector(768)`.
2. Commit or preserve the `ollama_embeddings_client.py` implementation if present.
3. Implement the Git repository client.
4. Implement fixed-size document chunking for the MVP.
5. Implement Ollama embeddings through the Ollama HTTP API.
6. Implement the full ingestion orchestration flow.
7. Create `.env.example`.
8. Add GitHub Actions for lint and tests.
9. Add pre-commit hooks later, likely with ruff and mypy.
10. Prepare Kubernetes CronJob manifests in a later phase.

Do not overwrite uncommitted user work. Always inspect files before editing.

---

## 7. Database Context

Database:

```text
PostgreSQL 16+ with pgvector
```

Schema:

```text
knowledge
```

Main tables:

```text
knowledge_sources
ingestion_runs
knowledge_documents
knowledge_chunks
```

Important concepts:

- `knowledge_sources`: Git repositories monitored by the service.
- `ingestion_runs`: audit trail for each ingestion execution.
- `knowledge_documents`: one record per source file.
- `knowledge_chunks`: text chunks plus vector embeddings.

Embedding column:

```text
knowledge_chunks.embedding vector(768)
```

Important index:

```text
HNSW index on knowledge_chunks.embedding using vector_cosine_ops
```

Important uniqueness rule:

```text
UNIQUE (source_id, path) on knowledge_documents
```

Migration awareness:

- Revision `0001` created the initial schema with `vector(384)`.
- Revision `0002` changes the embedding dimension to `vector(768)`.
- Treat `768` as the current target dimension.

When changing ORM models, always consider whether an Alembic migration is required.

---

## 8. Configuration Context

Configuration is based on `pydantic-settings`.

Relevant environment variables:

```text
KNOWLEDGE_REPO_URL
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_SCHEMA
OLLAMA_BASE_URL
EMBEDDINGS_MODEL
EMBEDDINGS_DIMENSIONS
CHUNK_SIZE
CHUNK_OVERLAP
INGESTION_INTERVAL_MINUTES
```

Expected defaults include:

```text
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=homelab_ai
POSTGRES_USER=knowledge_injector
POSTGRES_SCHEMA=knowledge
OLLAMA_BASE_URL=http://127.0.0.1:11434
EMBEDDINGS_MODEL=nomic-embed-text
EMBEDDINGS_DIMENSIONS=768
CHUNK_SIZE=1000
CHUNK_OVERLAP=150
INGESTION_INTERVAL_MINUTES=60
```

If adding configuration:

- Add it to `config.py`.
- Add tests.
- Add it to `.env.example`.
- Document it where appropriate.

Never hardcode credentials.

---

## 9. Expected Ingestion Flow

The target ingestion flow should be:

1. Load enabled knowledge sources.
2. Clone or update each configured Git repository.
3. List supported files.
4. Ignore unsupported files and irrelevant paths.
5. Read file content.
6. Calculate content hash.
7. Compare with existing `knowledge_documents`.
8. Skip unchanged documents.
9. Mark deleted documents when no longer present.
10. Split changed/new documents into chunks.
11. Generate embeddings for chunks using Ollama.
12. Persist documents and chunks transactionally.
13. Register ingestion run status and counters.
14. Log structured events throughout the pipeline.

Supported MVP file types:

```text
.md
.yaml
.yml
.txt
```

Avoid processing:

```text
.git/
.venv/
venv/
__pycache__/
node_modules/
dist/
build/
.coverage
.pytest_cache/
```

The ingestion process should be idempotent. Running the same ingestion twice against unchanged repository content should not create duplicate documents or chunks.

---

## 10. Ollama Embeddings Rules

Use Ollama as the embedding provider.

Expected API behavior:

- Use `OLLAMA_BASE_URL`.
- Use `EMBEDDINGS_MODEL`.
- Generate vectors with dimension `EMBEDDINGS_DIMENSIONS`.
- Validate returned embedding size.
- Fail clearly when Ollama is unavailable.
- Log model name, endpoint, and failures without leaking sensitive data.

The default model is:

```text
nomic-embed-text
```

Expected dimension:

```text
768
```

The project previously considered TEI, but the current direction is Ollama. Do not add TEI back unless requested.

Recommended implementation concerns:

- Use `httpx`.
- Configure reasonable timeout values.
- Validate response payload shape.
- Treat dimension mismatch as an error.
- Keep the adapter behind a domain port.
- Make unit tests use mocked HTTP responses.

Do not require Ollama to be running for normal unit tests.

---

## 11. Chunking Rules

The MVP chunking strategy is fixed-size character chunking.

Defaults:

```text
CHUNK_SIZE=1000
CHUNK_OVERLAP=150
```

Rules:

- Preserve document path in chunk metadata.
- Preserve chunk index.
- Ensure stable ordering.
- Avoid empty chunks.
- Avoid duplicate chunks from overlap bugs.
- Make chunking deterministic.
- Add unit tests for edge cases.

Important edge cases:

- Empty document.
- Very short document.
- Document exactly equal to chunk size.
- Document slightly larger than chunk size.
- Large document.
- Overlap greater than or equal to chunk size should be rejected or handled explicitly.

Recommended output metadata per chunk may include:

```json
{
  "source_path": "docs/example.md",
  "chunk_index": 0,
  "chunk_size": 1000,
  "chunk_overlap": 150
}
```

Do not implement advanced semantic chunking for the MVP unless explicitly requested.

---

## 12. Git Repository Client Rules

The Git adapter should live in:

```text
src/knowledge_injector/infrastructure/git/git_repository_client.py
```

Expected responsibilities:

- Clone a repository if it does not exist locally.
- Pull/fetch updates if it already exists.
- Checkout the configured branch.
- List supported files.
- Return file paths and contents in a deterministic way.
- Avoid exposing GitPython details outside the adapter.

Rules:

- Handle branch checkout errors clearly.
- Do not delete arbitrary directories.
- Use a controlled workspace/cache directory.
- Be careful with repository URL handling.
- Do not log secrets from private repository URLs.
- Sort files before returning them to keep ingestion deterministic.
- Normalize file paths using POSIX-style relative paths.

Recommended ignored paths:

```text
.git/
.venv/
venv/
__pycache__/
node_modules/
dist/
build/
.pytest_cache/
.coverage
```

Supported file extensions for MVP:

```text
.md
.yaml
.yml
.txt
```

---

## 13. Repository and Database Adapter Rules

Database repositories live around:

```text
src/knowledge_injector/infrastructure/db/repositories.py
```

ORM models live around:

```text
src/knowledge_injector/infrastructure/db/orm.py
```

Rules:

- Repository classes should implement domain ports.
- Keep transaction boundaries clear.
- Avoid returning raw ORM models to the application layer if domain models are expected.
- Preserve cascade behavior where expected.
- Keep helper methods tested.
- Do not duplicate SQLAlchemy session factory logic.

For vector handling:

- Ensure embeddings are stored in pgvector-compatible format.
- Validate dimensions before persistence where practical.
- Do not store `None` embeddings for normal chunks unless the domain explicitly supports it.

---

## 14. Testing Strategy

Use pytest.

Common commands:

```bash
uv run pytest
uv run pytest --cov=src/knowledge_injector --cov-report=term-missing
```

Local setup:

```bash
uv sync
docker compose --profile local-db up -d postgres
python -m knowledge_injector db-migrate
python -m knowledge_injector run-once
```

Testing expectations:

- Add unit tests for pure logic.
- Add integration tests only when real PostgreSQL behavior matters.
- Keep integration tests skippable when the database is unavailable.
- Do not require Ollama for unit tests; mock the embedding port.
- Do not require external Git repositories in unit tests; use temp local repositories or mocks.
- Preserve current test organization under `tests/unit` and `tests/integration`.

When changing repositories or ORM mappings, run database tests.

When changing CLI behavior, update CLI tests.

When changing config, update config tests.

When changing chunking, add focused chunking unit tests.

When changing Git behavior, add tests with temporary repositories if possible.

---

## 15. Docker and Local Development

The project has a multi-stage Dockerfile and a Docker Compose setup.

Expected commands:

```bash
# Install dependencies
uv sync

# Start local database
docker compose --profile local-db up -d postgres

# Run migrations
python -m knowledge_injector db-migrate

# Run one ingestion
python -m knowledge_injector run-once

# Run tests
uv run pytest
```

Dockerfile expectation:

- Base image: Python 3.12 slim.
- Package/dependency management with uv.
- Default command should run the worker in `run-once` mode.

Docker Compose expectation:

- Worker service.
- PostgreSQL service behind a `local-db` profile.
- Ollama may be external or added later depending on development scenario.

---

## 16. Kubernetes Direction

The service is expected to run as a Kubernetes CronJob in a later phase.

Kubernetes design expectations:

- Run in `run-once` mode.
- Load configuration from ConfigMaps and Secrets.
- Connect to PostgreSQL.
- Connect to Ollama endpoint.
- Emit structured logs to stdout.
- Be observable through the homelab observability stack.
- Avoid storing long-lived state inside the container filesystem unless explicitly designed.

Do not add Kubernetes manifests too early unless the user requests them or the current implementation is ready for smoke testing.

---

## 17. Code Style and Quality

Follow these rules:

- Prefer small, focused functions.
- Use explicit types.
- Use Python 3.12 features where useful, but avoid unnecessary cleverness.
- Prefer dependency injection over hidden globals.
- Prefer clear domain names over generic names.
- Keep logs structured with structlog.
- Keep errors actionable.
- Keep adapters replaceable.
- Avoid large framework-like abstractions unless necessary.
- Maintain consistent naming with the existing codebase.

Do not:

- Put business logic inside CLI commands.
- Import infrastructure into domain.
- Bypass the DI container without reason.
- Hardcode local paths that only work on one machine.
- Hardcode secrets.
- Silently swallow exceptions.
- Recreate existing concepts with different names.
- Introduce async unless the surrounding design is ready for it.
- Introduce new major dependencies without clear benefit.

---

## 18. Logging Rules

Use structured logging.

Logs should help answer:

- Which source was processed?
- Which branch was processed?
- How many files were seen?
- How many files changed?
- How many files were deleted?
- How many documents were created, updated, deleted, or ignored?
- How many chunks were created?
- Which step failed?
- What was the ingestion run ID?

Avoid logging:

- Secrets.
- Full repository credentials.
- Huge document content.
- Full embedding vectors.
- Large HTTP payloads.
- Sensitive environment variables.

Recommended logging style:

```python
logger.info(
    "ingestion_started",
    source_id=str(source.id),
    source_name=source.name,
    branch=source.branch,
)
```

---

## 19. Error Handling Rules

Prefer explicit failure states.

For ingestion runs:

- Mark successful runs as completed.
- Mark failed runs as failed.
- Store useful counters where available.
- Ensure `finished_at` is set when a run ends.
- Avoid leaving runs permanently in an ambiguous state when an exception occurs.

For external systems:

- PostgreSQL failures should surface clearly.
- Git failures should include repository and branch context.
- Ollama failures should include model and endpoint context, but not sensitive data.

Do not hide failures behind generic `Exception` messages unless re-raising with more context.

---

## 20. Security Rules

Never commit secrets.

Be careful with:

- Git repository URLs that may contain credentials.
- PostgreSQL passwords.
- Ollama endpoints if they are internal.
- Kubernetes Secrets.
- `.env` files.

When creating `.env.example`, use safe placeholder values.

Example:

```env
POSTGRES_PASSWORD=change-me
```

Do not include real tokens, passwords, or private repository credentials.

---

## 21. Documentation Rules

When changing behavior, update documentation where appropriate.

Important docs may include:

```text
README.md
docs/implementation-plan.md
agents/SKILL.md
agents/prompts/
.env.example
```

Documentation should be practical and command-oriented.

Prefer:

- What the feature does.
- How to configure it.
- How to run it.
- How to test it.
- Known limitations.

Avoid unnecessary theory unless it explains a relevant design decision.

---

## 22. Agent Workflow

Before making changes:

1. Inspect relevant files.
2. Identify the layer being changed.
3. Check existing ports and domain models.
4. Check current tests.
5. Check whether migrations are needed.
6. Preserve uncommitted user work.

When implementing:

1. Start from tests when practical.
2. Implement the smallest useful slice.
3. Keep changes consistent with the architecture.
4. Use existing patterns from the repository.
5. Update docs or `.env.example` when behavior/config changes.

After implementing:

1. Run focused tests.
2. Run broader tests if the change impacts shared code.
3. Summarize changed files.
4. Mention any tests not run.
5. Mention any follow-up tasks.

---

## 23. Response Expectations for Agents

When responding to the user, use this structure when appropriate:

```text
Resumo
- What changed or what should be done.

Arquivos afetados
- File paths and purpose.

Decisões técnicas
- Important choices and why.

Como validar
- Commands to run.

Riscos / Pendências
- Any known limitation or follow-up.
```

For code-generation requests:

- Provide concrete patches or full file contents when useful.
- Avoid vague advice.
- Prefer commands that can be copied and executed.
- Be explicit about assumptions.

For architecture requests:

- Explain tradeoffs.
- Preserve current architectural direction.
- Avoid suggesting a rewrite unless explicitly requested.

---

## 24. Current MVP Priorities

When in doubt, prioritize the next MVP path:

1. Stabilize current uncommitted changes around Ollama and `vector(768)`.
2. Implement `GitRepositoryClient`.
3. Implement deterministic chunking.
4. Implement `OllamaEmbeddingsClient`.
5. Implement `IngestionService`.
6. Wire everything in the DI container.
7. Add an end-to-end smoke test.
8. Add `.env.example`.
9. Prepare CI.
10. Prepare Kubernetes CronJob deployment.

---

## 25. Important Product Context

This service is not just a generic RAG ingestion script.

It belongs to the Tech Lead Joe vision: an AI-assisted technical lead platform capable of analyzing logs, documentation, repositories, architecture decisions, and operational signals to support incident analysis and engineering workflows.

The ingestion service should therefore optimize for:

- Reliable ingestion.
- Repeatable runs.
- Clear auditability.
- Good metadata.
- Replaceable providers.
- Local-first development.
- Future Kubernetes execution.
- Future integration with LLM/RAG workflows.

Design decisions should support that direction.

---

## 26. Suggested Prompt Usage

When asking an AI coding agent to work on this repository, reference this file explicitly.

Example prompt:

```text
Read `agents/SKILL.md` first and follow its architecture rules.

Now implement Phase 4: `ChunkingService`.

Requirements:
- Use fixed-size character chunking.
- Use `CHUNK_SIZE` and `CHUNK_OVERLAP` from config.
- Preserve deterministic ordering.
- Add unit tests for edge cases.
- Do not modify infrastructure code unless necessary.
- Summarize changed files and validation commands.
```

Another example:

```text
Read `agents/SKILL.md` first.

Now implement the Ollama embeddings adapter.

Requirements:
- Use httpx.
- Call the Ollama embedding API.
- Use `OLLAMA_BASE_URL`, `EMBEDDINGS_MODEL`, and `EMBEDDINGS_DIMENSIONS`.
- Validate embedding dimensions.
- Add unit tests with mocked HTTP responses.
- Do not require Ollama to be running during unit tests.
```

---

## 27. Final Instruction

Always preserve the architecture.

Favor incremental, testable changes over broad rewrites.

If a requested change conflicts with the architecture, explain the conflict and propose the smallest safe alternative.
