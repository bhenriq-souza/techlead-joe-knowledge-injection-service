# knowledge-injector

> Part of the **Tech Lead Joe** ecosystem.

A Python service that reads versioned Git repositories, generates embeddings via [TEI](https://github.com/huggingface/text-embeddings-inference), and persists the resulting vector knowledge base in PostgreSQL/pgvector for downstream RAG workloads.

```
Git docs ──► knowledge-injector ──► TEI embeddings ──► PostgreSQL/pgvector ──► RAG service
```

---

## Responsibilities

- Clone / pull a Git repository configured via environment variables.
- Identify eligible documents (Markdown, YAML, plain text, etc.).
- Detect new, changed, and deleted files using content hashing.
- Chunk documents respecting Markdown structure.
- Generate embeddings using the TEI OpenAI-compatible endpoint.
- Persist sources, documents, chunks, and embeddings in PostgreSQL.
- Record every ingestion run for auditability.
- Skip unchanged content — no redundant re-embedding.

**Out of scope:** chat, RAG queries, LLM enrichment, Jira/Slack integration.

---

## Requirements

| Tool | Version |
|------|---------|
| Python | 3.12+ |
| uv | latest |
| Docker | 24+ |
| PostgreSQL | 16+ with pgvector |
| TEI | any OpenAI-compatible release |

---

## Quick start

```bash
# 1. Copy and fill in your environment variables
cp .env.example .env
$EDITOR .env

# 2. Install dependencies
uv sync

# 3. Run a single ingestion pass
uv run python -m knowledge_injector run-once

# 4. (Optional) Run in continuous loop — dev/non-Kubernetes mode
uv run python -m knowledge_injector run-loop --interval 30
```

---

## Environment variables

See [.env.example](.env.example) for the full list with descriptions.

Key variables:

| Variable | Description |
|---|---|
| `KNOWLEDGE_REPO_URL` | Git repository to ingest |
| `KNOWLEDGE_REPO_BRANCH` | Branch to track |
| `POSTGRES_HOST` / `POSTGRES_DB` | Target database |
| `TEI_BASE_URL` | Text Embeddings Inference endpoint |
| `EMBEDDINGS_MODEL` | Model name (default: `BAAI/bge-small-en-v1.5`) |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Chunking parameters (chars) |

---

## Docker

### Build

```bash
docker build -t knowledge-injector:latest .
```

### Run (with local pgvector)

```bash
# Start the optional local postgres/pgvector
docker compose --profile local-db up -d postgres

# Run a single ingestion pass
docker compose run --rm knowledge-injector
```

---

## Project structure

```
src/knowledge_injector/
├── __main__.py            # python -m knowledge_injector entry point
├── main.py                # Bootstrap: DI container + logging + CLI
├── config.py              # Pydantic-settings configuration
├── containers.py          # dependency-injector DI container
├── domain/
│   ├── models.py          # Core domain entities (dataclasses)
│   └── ports.py           # Abstract port interfaces
├── application/
│   ├── ingestion_service.py   # Orchestrates the full pipeline
│   ├── chunking_service.py    # Splits documents into chunks
│   └── scheduling_service.py  # run-loop scheduling helper
├── infrastructure/
│   ├── git/               # GitRepositoryClient (GitPython)
│   ├── embeddings/        # TeiEmbeddingsClient (httpx)
│   ├── db/                # SQLAlchemy + Alembic migrations
│   └── logging/           # structlog configuration
└── cli/
    └── commands.py        # Click CLI — run-once / run-loop
```

---

## Development phases

| Phase | Description | Status |
|-------|-------------|--------|
| **1** | Bootstrap: uv, DI, CLI skeleton | ✅ Done |
| **2** | Git source + file discovery | 🔜 Next |
| **3** | PostgreSQL + Alembic migrations | 🔜 |
| **4** | Markdown-aware chunking | 🔜 |
| **5** | TEI embeddings integration | 🔜 |
| **6** | Incremental processing (skip unchanged) | 🔜 |
| **7** | Kubernetes CronJob manifests | 🔜 |

---

## Kubernetes (CronJob)

The application is designed to execute a single run and exit:

```bash
python -m knowledge_injector run-once
```

Example CronJob configuration (Phase 7):

```yaml
apiVersion: batch/v1
kind: CronJob
spec:
  schedule: "0 * * * *"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 5
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: knowledge-injector
              image: knowledge-injector:latest
              command: ["python", "-m", "knowledge_injector", "run-once"]
```

---

## Validated AI Lab environment

This service is designed to run against the **AI Lab** stack (Docker Compose + NVIDIA Container Toolkit on the local Ubuntu workstation).
Setup guide: `techlead-joe-infra/docs/prompts/setup-ai-lab-docker-ollama-tei.md`.

AI Lab hardware: AMD Ryzen 9 7900X / RTX 5070 12 GB GDDR7 / 64 GB DDR5 (`192.168.15.103`, same LAN as homelab).

- TEI serving `BAAI/bge-small-en-v1.5` (384-dim) at `http://192.168.15.103:8080`
- PostgreSQL 16 with pgvector in Docker (on homelab cluster — `192.168.15.97`)
- NVIDIA container toolkit (GPU for other services; TEI runs on CPU here)
