# Implementation Plan — knowledge-injector MVP end-to-end

> Objetivo: sair do estado atual (schema criado, todo o resto stub) para um `run-once` que clona o repositório `homelab-infra`, descobre arquivos, gera chunks, gera embeddings via Ollama e persiste tudo no Postgres, com a `ingestion_runs` registrando o resultado.

---

## 1. Estado atual (baseline)

| Componente | Estado | Observação |
|---|---|---|
| Migração Alembic `0001` | ✅ Aplicada | Schema `knowledge` + 4 tabelas + índice HNSW em `vector(384)` |
| Migração Alembic `0002` | ✅ Aplicada | Altera coluna `embedding` de `vector(384)` para `vector(768)` (nomic-embed-text via Ollama) |
| `domain/models.py`, `domain/ports.py` | ✅ Pronto | Dataclasses + ABCs já refletem o schema |
| `infrastructure/db/orm.py` | ✅ Pronto | ORM models alinhados com a migração |
| `config.py` (Pydantic Settings) | ✅ Pronto | Carrega `.env` automaticamente |
| `cli/commands.py` | ✅ Pronto | `run-once`, `run-loop`, `db-migrate` |
| `containers.py` (DI) | ⚠️ Parcial | Falta wirar repositórios e session factory no `IngestionService` |
| `infrastructure/db/database.py` | ✅ Completo | Engine + session factory + health_check implementados |
| `infrastructure/db/repositories.py` | ✅ Completo | 4 repositórios implementados com upsert, queries e embedding via SQL textual |
| `infrastructure/git/git_repository_client.py` | 🚧 Stub | `NotImplementedError` |
| `application/chunking_service.py` | 🚧 Stub | `NotImplementedError` |
| `infrastructure/embeddings/ollama_embeddings_client.py` | 🚧 Stub | `NotImplementedError` |
| `application/ingestion_service.py` | 🚧 Stub | Apenas log |

**Ambientes validados:**
- Postgres `192.168.15.97:5432` / DB `homelab_ai` / role `appuser` / schema `knowledge`, pgvector 0.8.2.
- Ollama `http://192.168.15.103:11434`, modelo `nomic-embed-text`, 768 dimensões, endpoint `/api/embed` confirmado.

---

## 2. Princípios para o MVP

1. **Fim-a-fim primeiro, qualidade depois.** Toda peça vai começar simples (chunking por tamanho fixo, embed síncrono, persistência ORM convencional) e evoluir em iterações futuras.
2. **Síncrono.** Usar SQLAlchemy 2.0 em modo síncrono (`psycopg`) e `httpx.Client` síncrono. Apesar do `pyproject.toml` listar `asyncpg` e `sqlalchemy[asyncio]`, o CLI é um job de bateria simples — async não traz ganho aqui e adiciona complexidade. Mantemos a porta aberta para migrar depois.
3. **Idempotente.** Rodar duas vezes seguidas sem mudança no repo deve resultar em zero `chunks_updated` e zero `chunks_deleted`.
4. **Transações por documento.** Cada documento (chunks + embedding + upsert) é uma unidade transacional. Falha em um arquivo não derruba o run inteiro — registra erro e continua, marca run como `partial` se houver falha parcial.
5. **Sem feature flags / camadas extras.** Implementar o caminho feliz; tratar erro só onde o pipeline pode falhar de forma esperada (rede, parsing, IO).

---

## 3. Arquitetura de runtime do `run-once`

```
IngestionService.run_once()
├── 1. KnowledgeSourceRepo.upsert(source)            ← garante linha em knowledge_sources
├── 2. IngestionRunRepo.create(run, status=RUNNING)  ← cria linha "em execução"
├── 3. RepositoryClient.sync()                        ← clone/pull, retorna commit SHA
├── 4. RepositoryClient.list_files(...)               ← FileEntry[] (path, content, hash)
├── 5. para cada FileEntry:
│     ├── KnowledgeDocumentRepo.find_by_source_and_path(...)
│     ├── se hash idêntico → pular (incremental)
│     ├── senão: ChunkingService.chunk(file)
│     ├── EmbeddingsClient.embed([chunk.content for ...])
│     ├── KnowledgeDocumentRepo.upsert(doc)
│     ├── KnowledgeChunkRepo.replace_for_document(doc.id, chunks_with_embeddings)
│     └── (commit por documento)
├── 6. Documents ausentes do listing → mark_deleted (soft) + delete_for_document
└── 7. IngestionRunRepo.update(run, status=SUCCEEDED|PARTIAL|FAILED, contadores, sha)
```

---

## 4. Plano de implementação (ordem de execução)

A ordem é deliberada: cada passo só depende do anterior. Cada passo termina com **algo executável e verificável** — não é tudo-ou-nada.

### ~~Passo 1 — `Database`: engine + session factory~~ ✅ Implementado

**Arquivo:** [src/knowledge_injector/infrastructure/db/database.py](../src/knowledge_injector/infrastructure/db/database.py)

- Criar `create_engine(dsn, future=True)` síncrono.
- Expor `session_factory: sessionmaker[Session]` com `expire_on_commit=False`.
- Helper context manager `with db.session() as s: yield s` que faz commit/rollback automático.
- `health_check()`: `SELECT 1`.

**Validação:** chamar `db.health_check()` num REPL retorna `True`.

---

### ~~Passo 2 — Repositories (SQLAlchemy adapters dos ports)~~ ✅ Implementado

**Arquivo:** [src/knowledge_injector/infrastructure/db/repositories.py](../src/knowledge_injector/infrastructure/db/repositories.py)

Implementar 4 classes implementando os ports já definidos:

- `KnowledgeSourceRepository` — `upsert(by name)`, `find_by_name`.
- `IngestionRunRepository` — `create`, `update`, `find_by_id`.
- `KnowledgeDocumentRepository` — `upsert(by source_id+path)`, `find_by_source_and_path`, `find_active_by_source`, `mark_deleted`.
- `KnowledgeChunkRepository` — `replace_for_document` (delete + bulk insert), `delete_for_document`.

**Detalhes técnicos:**
- Usar `INSERT ... ON CONFLICT DO UPDATE` (Postgres dialect) para `upsert`.
- Mapeamento ORM ↔ dataclass via funções privadas `_to_domain` / `_from_domain`.
- Para `KnowledgeChunk.embedding`, gravar via SQL textual usando o tipo `vector` do `pgvector` (coluna `embedding` não está mapeada no ORM — comentário explícito no código). Usar `from pgvector.sqlalchemy import Vector` ou `text("INSERT INTO ... (embedding) VALUES (cast(:emb AS vector))")` com lista Python serializada como `'[0.1,0.2,...]'`.
- Cada repositório recebe uma `Session` por chamada (não guarda estado).

**Validação:** teste manual escrevendo um `KnowledgeSource` fake e lendo de volta.

---

### ~~Passo 3 — `GitRepositoryClient` (clone/pull local)~~ → SUPERSEDED

> **Decisão arquitetural (2026-05-15):** O Passo 3 original foi substituído pela abordagem de ingestão event-driven.
>
> O `GitRepositoryClient` baseado em clone/pull local pode ser mantido futuramente como adapter auxiliar (fallback / local-dev), mas **não é o caminho principal de ingestão do produto**.
>
> Consulte: [agents/prompts/passo-03-git-repository-client.md](../agents/prompts/passo-03-git-repository-client.md) (prompt original, mantido como referência)  
> Consulte: [docs/architecture/knowledge-ingestion-event-driven.md](architecture/knowledge-ingestion-event-driven.md) (decisão completa)

---

### Passo 3 — Event-driven Document Source Ingestion

**Decisão:** O serviço não deve ser tratado como um "Git repository indexer". Ele deve ser um serviço de ingestão controlada de fontes documentais aprovadas.

**Novo fluxo principal:**

```text
GitHub PR mergeado
  → GitHub/GitHub Actions publica evento normalizado no Pub/Sub
  → Knowledge Ingestion Worker consome evento
  → Worker consulta catálogo (fonte de verdade)
  → Worker resolve ambiente pela branch de destino
  → Worker calcula delta (arquivos alterados no merge)
  → Worker baixa apenas documentos permitidos via GitHub API
  → Worker atualiza documentos, chunks e embeddings
```

**Princípios:**

- O catálogo é a fonte de verdade: projeto, serviço, repositório, ambiente, branch monitorada, `allowed_paths`, `blocked_paths`, tipo documental e nível de confiança.
- O worker **não confia cegamente no evento**: consulta o catálogo antes de baixar qualquer conteúdo.
- O worker baixa apenas documentos **alterados e permitidos** (delta, não clone completo).
- Arquivos `removed` e `renamed` também atualizam o banco.
- O initial sync ocorre quando o repositório é associado ao catálogo (processa todos os paths permitidos, não o repo inteiro).
- O incremental sync ocorre quando um PR é mergeado na branch configurada para o ambiente.
- Reconciliação periódica garante consistência mesmo sem eventos.
- Clone/pull local deixa de ser caminho principal.

**Branch por ambiente (exemplo):**

| Branch | Ambiente |
|--------|----------|
| `develop` | `dev` |
| `homolo` | `hml` |
| `main` | `prd` |

**Prompt principal:** [agents/prompts/passo-03-event-driven-document-source-ingestion.md](../agents/prompts/passo-03-event-driven-document-source-ingestion.md)

---

## Backlog — Event-driven Knowledge Ingestion

Organizado em fases incrementais. Cada fase termina com algo verificável.

### Passo 3.1 — Revisão de domínio e contratos

- Criar modelo de evento normalizado (`SourceIngestionEvent` ou similar).
- Criar modelo para mapeamento branch → ambiente.
- Revisar `KnowledgeSource` para suportar `provider`, `environment`, `branch`, `allowed_paths`, `blocked_paths`.
- Criar port `RepositoryContentClientPort` (separado de `RepositoryClientPort`, foco em conteúdo via API, sem sync local).
- Criar port `IngestionEventConsumerPort` para consumo de eventos.
- Não implementar Pub/Sub nem GitHub API neste passo.

**Prompt:** [agents/prompts/passo-03-event-driven-document-source-ingestion.md](../agents/prompts/passo-03-event-driven-document-source-ingestion.md)

### Passo 3.2 — GitHub Actions → Pub/Sub (template + infra)

O passo 3.2 é dividido em duas partes paralelas:

**3.2a — Template do workflow GitHub Actions:**

- Criar template em `docs/examples/github-actions/knowledge-ingestion-trigger.yml`.
- O workflow fica no **repositório cliente** — o template é copiado pelo time responsável.
- Acionar em `pull_request` tipo `closed` com `merged == true`.
- Extrair `base.ref`, PR number, merge commit SHA, base SHA, head SHA.
- Publicar evento normalizado no Pub/Sub via WIF.
- Documentar pré-requisitos e passo a passo em `docs/examples/github-actions/README.md`.

**Prompt:** [agents/prompts/passo-04-github-actions-to-pubsub.md](../agents/prompts/passo-04-github-actions-to-pubsub.md)

**3.2b — Infraestrutura Pub/Sub (Terraform no `techlead-joe-infra`):**

- Criar tópico `knowledge-ingestion-events` e subscription `knowledge-ingestion-events-sub`.
- Criar service accounts: `ki-publisher` (GitHub Actions via WIF) e `ki-consumer` (worker Python).
- Configurar Workload Identity Federation para autenticação sem chaves SA.
- IAM bindings: publisher → tópico, consumer → subscription.

**Prompt:** [agents/prompts/passo-04b-terraform-pubsub-infra.md](../agents/prompts/passo-04b-terraform-pubsub-infra.md)

### Passo 3.3 — Pub/Sub Ingestion Consumer

- Criar adapter `PubSubConsumer` em `infrastructure/pubsub/`.
- Deserializar e validar schema do evento.
- Chamar application handler/service.
- Garantir logs estruturados e idempotência preparada.

**Prompt:** [agents/prompts/passo-05-pubsub-ingestion-consumer.md](../agents/prompts/passo-05-pubsub-ingestion-consumer.md)

### Passo 3.4 — GitHub Content Client

- Criar adapter `GithubContentClient` em `infrastructure/github/`.
- Resolver diff do merge (`base_sha..head_sha`) via GitHub API.
- Identificar `added`, `modified`, `removed`, `renamed`.
- Baixar conteúdo apenas dos arquivos permitidos.
- Devolver objetos compatíveis com o domínio (`FileEntry`).
- Evitar clone/diretório temporário como caminho principal.

**Prompt:** [agents/prompts/passo-06-github-content-client.md](../agents/prompts/passo-06-github-content-client.md)

### Passo 3.5 — Incremental Ingestion Handler

- Implementar handler de ingestão incremental (application layer).
- Consultar catálogo / source config.
- Validar ambiente pela branch de destino.
- Aplicar `allowed_paths` / `blocked_paths`.
- Atualizar `knowledge_documents` (added, modified, removed, renamed).
- Gerar chunks (`ChunkingService`) e embeddings (`OllamaEmbeddingsClient`).
- Atualizar `knowledge_chunks`.
- Criar e finalizar `ingestion_runs` com contadores.
- Manter idempotência por `source_id + environment + merge_commit_sha`.

**Prompt:** [agents/prompts/passo-07-incremental-ingestion-handler.md](../agents/prompts/passo-07-incremental-ingestion-handler.md)

### Passo 3.6 — Initial Sync

- Implementar initial sync disparado quando fonte é cadastrada no catálogo.
- Processar todos os documentos listados em `allowed_paths`.
- Não processar o repositório inteiro.
- Reutilizar `GithubContentClient` e `ChunkingService`.

### Passo 3.7 — Reconciliação Periódica

- Implementar modo `full_allowed_sources_sync`.
- Comparar estado atual do catálogo com documentos persistidos.
- Corrigir divergências sem clonar o repositório inteiro.

### Passo 3.8 — Testes

- Testes unitários para validação de evento (`SourceIngestionEvent`).
- Testes unitários para filtro por branch/ambiente.
- Testes unitários para `allowed_paths` / `blocked_paths`.
- Testes do `GithubContentClient` com mocks de HTTP.
- Testes do handler incremental com mocks de ports.
- Teste de idempotência (mesmo `merge_commit_sha` não reprocessa).

---

### Passo 4 — `ChunkingService` (Phase 4 simplificado)

**Arquivo:** [src/knowledge_injector/application/chunking_service.py](../src/knowledge_injector/application/chunking_service.py)

**Estratégia MVP:** chunking por tamanho fixo de caracteres (sem markdown-aware ainda).

- `chunk(file_entry, document_id) -> list[KnowledgeChunk]`:
  - Janela deslizante: `chunk_size=1000`, `chunk_overlap=150` (já no `.env`).
  - `chunk_index` sequencial a partir de 0.
  - `content_hash`: sha256 do conteúdo do chunk.
  - `metadata`: `{"source_path": file_entry.relative_path, "char_start": int, "char_end": int}`.
  - `token_count`: `None` no MVP (TEI não retorna; podemos preencher depois com tiktoken/HF tokenizer).

**Trade-off explícito:** chunking por chars não respeita parágrafos/headers de markdown, então pode cortar no meio de uma sentença. É aceitável pra MVP — vamos validar embedding+RAG end-to-end primeiro, melhorar chunking em iteração separada (Phase 4 "real").

**Validação:** unit test com texto de 2500 chars → 3 chunks com overlap.

---

### Passo 5 — `OllamaEmbeddingsClient` (Phase 5)

**Arquivo:** [src/knowledge_injector/infrastructure/embeddings/ollama_embeddings_client.py](../src/knowledge_injector/infrastructure/embeddings/ollama_embeddings_client.py)

- `embed(texts) -> list[list[float]]`:
  - `httpx.Client(timeout=60.0)` (instance-level, reaproveitar entre chamadas).
  - POST `{base_url}{embeddings_path}` (`/api/embed`) com payload `{"model": model, "input": texts}`.
  - Resposta: `{"model": "...", "embeddings": [[...], [...]]}`.
  - A ordem da resposta é garantida por posição (alinhada com a entrada).
  - Validar que cada vetor tem `dimensions` (768) — se não, raise erro descritivo.
  - Batch de tamanho 32 por requisição. Se `len(texts) > 32`, dividir e concatenar.

**Pegadinhas:**
- Texto vazio → Ollama pode rejeitar. Filtrar `texts` vazios antes de mandar; no MVP, levanta se `texts` estiver vazio.
- Retry: 1 retry com backoff de 2s para 5xx. Sem retry em 4xx.
- O modelo precisa estar baixado no Ollama antes da primeira chamada (`ollama pull nomic-embed-text`).

**Validação:** chamada direta com `["hello world"]` retorna lista de 1 vetor de 768 floats.

---

### Passo 6 — `IngestionService` (orquestração)

**Arquivo:** [src/knowledge_injector/application/ingestion_service.py](../src/knowledge_injector/application/ingestion_service.py)

Constructor recebe via DI:
- `db: Database`
- `repo_client: RepositoryClientPort`
- `embeddings_client: EmbeddingsClientPort`
- `chunking_service: ChunkingService`
- `source_repo: KnowledgeSourceRepositoryPort`
- `run_repo: IngestionRunRepositoryPort`
- `doc_repo: KnowledgeDocumentRepositoryPort`
- `chunk_repo: KnowledgeChunkRepositoryPort`
- `settings: AppSettings`

`run_once()` implementa o fluxo da Seção 3. Pseudocódigo:

```python
def run_once(self):
    started = utcnow()
    with self.db.session() as s:
        source = self.source_repo.upsert(self._source_from_settings(), s)
        run = self.run_repo.create(IngestionRun(
            source_id=source.id, status=RUNNING, started_at=started), s)
    run_id = run.id

    errors = []
    counters = {"seen": 0, "changed": 0, "deleted": 0,
                "chunks_created": 0, "chunks_updated": 0, "chunks_deleted": 0}
    sha = None

    try:
        sha = self.repo_client.sync()
        files = self.repo_client.list_files(
            self.settings.knowledge_source.repo_base_path,
            self.settings.ingestion.include_patterns,
            self.settings.ingestion.exclude_patterns,
        )
        counters["seen"] = len(files)

        seen_paths = set()
        for f in files:
            seen_paths.add(f.relative_path)
            try:
                self._process_file(source.id, f, sha, counters)
            except Exception as e:
                logger.exception("ingestion.file.failed", path=f.relative_path)
                errors.append((f.relative_path, str(e)))

        # Garbage-collect documentos sumidos
        with self.db.session() as s:
            active = self.doc_repo.find_active_by_source(source.id, s)
            for d in active:
                if d.path not in seen_paths:
                    self.doc_repo.mark_deleted(d.id, s)
                    deleted = self.chunk_repo.delete_for_document(d.id, s)
                    counters["deleted"] += 1
                    counters["chunks_deleted"] += deleted

        status = PARTIAL if errors else SUCCEEDED
        error_msg = "; ".join(f"{p}: {e}" for p, e in errors[:5]) or None

    except Exception as e:
        logger.exception("ingestion.run.failed")
        status = FAILED
        error_msg = str(e)

    finally:
        with self.db.session() as s:
            run = self.run_repo.find_by_id(run_id, s)
            run.status = status
            run.finished_at = utcnow()
            run.repo_commit_sha = sha
            run.files_seen = counters["seen"]
            run.files_changed = counters["changed"]
            run.files_deleted = counters["deleted"]
            run.chunks_created = counters["chunks_created"]
            run.chunks_updated = counters["chunks_updated"]
            run.chunks_deleted = counters["chunks_deleted"]
            run.error_message = error_msg
            self.run_repo.update(run, s)
```

`_process_file(source_id, file_entry, sha, counters)`:

```python
with self.db.session() as s:
    existing = self.doc_repo.find_by_source_and_path(source_id, file_entry.relative_path, s)
    if existing and existing.content_hash == file_entry.content_hash:
        return  # skip — incremental

    doc = KnowledgeDocument(
        id=existing.id if existing else uuid4(),
        source_id=source_id, path=file_entry.relative_path,
        content_hash=file_entry.content_hash, status=ACTIVE,
        last_commit_sha=sha,
        title=_extract_title(file_entry.content),
        mime_type=_guess_mime(file_entry.relative_path),
    )
    doc = self.doc_repo.upsert(doc, s)

    chunks = self.chunking_service.chunk(file_entry, doc.id)
    if not chunks:
        return

    vectors = self.embeddings_client.embed([c.content for c in chunks])
    for c, v in zip(chunks, vectors):
        c.embedding = v

    self.chunk_repo.replace_for_document(doc.id, chunks, s)

    if existing:
        counters["chunks_updated"] += len(chunks)
    else:
        counters["chunks_created"] += len(chunks)
        counters["changed"] += 1
```

**Helpers:**
- `_extract_title`: primeira linha começando com `# ` em markdown, senão `None`.
- `_guess_mime`: `.md → text/markdown`, `.yaml/.yml → application/yaml`, `.txt → text/plain`.

---

### Passo 7 — Container DI: wirar tudo

**Arquivo:** [src/knowledge_injector/containers.py](../src/knowledge_injector/containers.py)

Adicionar providers para os 4 repositórios e injetar tudo no `IngestionService`:

```python
source_repo = providers.Factory(KnowledgeSourceRepository)
run_repo = providers.Factory(IngestionRunRepository)
doc_repo = providers.Factory(KnowledgeDocumentRepository)
chunk_repo = providers.Factory(KnowledgeChunkRepository)

ingestion_service = providers.Factory(
    IngestionService,
    db=db,
    repo_client=git_client,
    embeddings_client=embeddings_client,
    chunking_service=chunking_service,
    source_repo=source_repo,
    run_repo=run_repo,
    doc_repo=doc_repo,
    chunk_repo=chunk_repo,
    settings=settings,
)
```

---

### Passo 8 — Smoke test end-to-end

1. `uv run python -m knowledge_injector run-once` — primeira execução, popula tudo.
2. Conferir no Postgres:
   ```sql
   SELECT name, repo_url FROM knowledge.knowledge_sources;
   SELECT status, files_seen, files_changed, chunks_created, repo_commit_sha
     FROM knowledge.ingestion_runs ORDER BY started_at DESC LIMIT 1;
   SELECT count(*) FROM knowledge.knowledge_documents;
   SELECT count(*), count(embedding) FROM knowledge.knowledge_chunks;
   ```
3. Re-rodar `run-once` — `chunks_created` e `files_changed` da segunda run devem ser **0** (idempotência).
4. Editar um arquivo no `homelab-infra`, rodar de novo — deve aparecer `files_changed=1` e os chunks daquele documento atualizados.
5. Smoke RAG:
   ```bash
   QVEC=$(curl -s http://192.168.15.103:11434/api/embed \
     -H "Content-Type: application/json" \
     -d '{"model":"nomic-embed-text","input":["como funciona o cluster"]}' \
     | python -c "import sys,json; v=json.load(sys.stdin)['embeddings'][0]; print('['+','.join(str(x) for x in v)+']')")
   psql ... -c "SELECT d.path, left(c.content, 80), 1-(c.embedding<=>'$QVEC'::vector) AS sim
                FROM knowledge.knowledge_chunks c
                JOIN knowledge.knowledge_documents d ON d.id=c.document_id
                ORDER BY c.embedding<=>'$QVEC'::vector LIMIT 3;"
   ```

---

## 5. Out of scope (explícito)

Tudo abaixo fica para iterações futuras — **não** entrar no MVP:

- `GitRepositoryClient` como caminho principal de produção (pode ser mantido como fallback/local-dev).
- Webhook Receiver próprio — evento disparado diretamente pelo GitHub/GitHub Actions para Pub/Sub.
- Chunking markdown-aware (header splitting). Hoje é por chars.
- Async pipeline (asyncpg / asyncio).
- Auth git via token/SSH para clone local.
- Métricas Prometheus, OpenTelemetry tracing.
- Retry com exponential backoff sofisticado.
- Manifests Kubernetes (CronJob) — fase posterior.
- Tokenização real (`token_count` fica `None`).
- Deduplicação inter-documento de chunks idênticos.
- Limpeza incremental de embeddings órfãos (FK ON DELETE CASCADE já cuida do caso simples).
- Interface de catálogo completa — no MVP o catálogo pode ser simplificado via config/env.

---

## 6. Riscos & mitigações

| Risco | Probabilidade | Mitigação |
|---|---|---|
| `pgvector` não exposto via SQLAlchemy core sem o tipo customizado | Média | Usar `pgvector.sqlalchemy.Vector` (já em `pyproject.toml`) ou `cast(:val AS vector)` em SQL textual |
| Ollama rejeitar batch grande de markdown | Baixa | Batch de 32, com retry, e logar size |
| Repo `homelab-infra` não acessível por HTTPS | Média | Apontar `KNOWLEDGE_REPO_URL` para `file:///home/brunohsouza/code/Personal/homelab-infra` durante dev |
| Encoding de arquivos não utf-8 | Baixa | `decode("utf-8", errors="replace")` no leitor + log de warning |
| `appuser` sem permissão para INSERT em `knowledge.*` | Baixa | Ele já criou o schema na migração; se faltar, `GRANT ALL ON ALL TABLES IN SCHEMA knowledge TO appuser` |
| Conflito de `chunks_updated` vs `chunks_created` (semântica) | Média | Definir: documento pré-existente com hash diferente → todos os chunks novos contam como `chunks_updated`; documento novo → `chunks_created`. Cobrir no smoke test |

---

## 7. Critérios de aceite do MVP

1. ✅ `run-once` termina sem exceção em repo válido.
2. ✅ `knowledge_sources` tem 1 linha após o primeiro run.
3. ✅ `ingestion_runs` mostra `status='succeeded'`, `repo_commit_sha` preenchido, contadores coerentes.
4. ✅ `knowledge_documents.count` > 0, todos com `status='active'` e `content_hash` preenchido.
5. ✅ `knowledge_chunks.count` > 0, todos com `embedding IS NOT NULL` e dimensão 768.
6. ✅ Re-run sem mudança no repo: `chunks_created=0`, `files_changed=0`.
7. ✅ Edição de arquivo + re-run: documento ganha versão atualizada (mesmo `id`), chunks substituídos.
8. ✅ Query de similaridade retorna top-K com `cosine_sim` razoável (>0.3 para query relacionada).

---

## 8. Estimativa de esforço

| Passo | Esforço | Status |
|---|---|---|
| ~~1. Database engine~~ | ~~15 min~~ | ✅ |
| ~~2. Repositories (4)~~ | ~~60 min~~ | ✅ |
| 3.1 Revisão de domínio e contratos | 45 min | |
| 3.2 GitHub Actions → Pub/Sub (workflow YAML) | 30 min | |
| 3.3 Pub/Sub Ingestion Consumer | 60 min | |
| 3.4 GitHub Content Client | 60 min | |
| 3.5 Incremental Ingestion Handler | 90 min | |
| 3.6 Initial Sync | 45 min | |
| 3.7 Reconciliação periódica | 30 min | |
| 3.8 Testes | 60 min | |
| ChunkingService (necessário para 3.5) | 20 min | |
| OllamaEmbeddingsClient (necessário para 3.5) | 30 min | |
| Container wiring + smoke test | 30 min | |
| **Restante estimado** | **~9h** | |

> **Nota:** `GitRepositoryClient` (Passo 3 original, 30 min) foi removido do caminho principal. O `GithubContentClient` (Passo 3.4) substitui sua função core.
