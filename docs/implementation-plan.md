# Implementation Plan — knowledge-injector MVP end-to-end

> Objetivo: sair do estado atual (schema criado, todo o resto stub) para um `run-once` que clona o repositório `homelab-infra`, descobre arquivos, gera chunks, gera embeddings via TEI e persiste tudo no Postgres, com a `ingestion_runs` registrando o resultado.

---

## 1. Estado atual (baseline)

| Componente | Estado | Observação |
|---|---|---|
| Migração Alembic `0001` | ✅ Aplicada | Schema `knowledge` + 4 tabelas + índice HNSW em `vector(384)` |
| `domain/models.py`, `domain/ports.py` | ✅ Pronto | Dataclasses + ABCs já refletem o schema |
| `infrastructure/db/orm.py` | ✅ Pronto | ORM models alinhados com a migração |
| `config.py` (Pydantic Settings) | ✅ Pronto | Carrega `.env` automaticamente |
| `cli/commands.py` | ✅ Pronto | `run-once`, `run-loop`, `db-migrate` |
| `containers.py` (DI) | ⚠️ Parcial | Falta wirar repositórios e session factory no `IngestionService` |
| `infrastructure/git/git_repository_client.py` | 🚧 Stub | `NotImplementedError` |
| `infrastructure/db/database.py` | 🚧 Stub | `NotImplementedError` |
| `infrastructure/db/repositories.py` | 🚧 Vazio | Só TODO |
| `application/chunking_service.py` | 🚧 Stub | `NotImplementedError` |
| `infrastructure/embeddings/tei_embeddings_client.py` | 🚧 Stub | `NotImplementedError` |
| `application/ingestion_service.py` | 🚧 Stub | Apenas log |

**Ambientes validados:**
- Postgres `192.168.15.97:5432` / DB `homelab_ai` / role `appuser` / schema `knowledge`, pgvector 0.8.2.
- TEI `http://127.0.0.1:8080`, modelo `BAAI/bge-small-en-v1.5`, 384 dimensões, endpoint `/v1/embeddings` (compat OpenAI) confirmado.

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

### Passo 1 — `Database`: engine + session factory

**Arquivo:** [src/knowledge_injector/infrastructure/db/database.py](../src/knowledge_injector/infrastructure/db/database.py)

- Criar `create_engine(dsn, future=True)` síncrono.
- Expor `session_factory: sessionmaker[Session]` com `expire_on_commit=False`.
- Helper context manager `with db.session() as s: yield s` que faz commit/rollback automático.
- `health_check()`: `SELECT 1`.

**Validação:** chamar `db.health_check()` num REPL retorna `True`.

---

### Passo 2 — Repositories (SQLAlchemy adapters dos ports)

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

### Passo 3 — `GitRepositoryClient` (Phase 2)

**Arquivo:** [src/knowledge_injector/infrastructure/git/git_repository_client.py](../src/knowledge_injector/infrastructure/git/git_repository_client.py)

- `sync()`:
  - Se `workdir` não existe ou não é um repo válido → `git.Repo.clone_from(repo_url, workdir, branch=branch)`.
  - Se já existe → `repo.remotes.origin.fetch()` + `repo.git.checkout(branch)` + `repo.git.reset("--hard", f"origin/{branch}")`.
  - Retornar `repo.head.commit.hexsha`.
- `list_files(base_path, include_patterns, exclude_patterns)`:
  - Caminhar a partir de `workdir/base_path`.
  - Aplicar `pathlib.PurePath.match()` para include/exclude (semântica glob).
  - Para cada arquivo elegível: ler bytes, decodificar utf-8 (errors="replace"), calcular `sha256` do conteúdo.
  - `relative_path` é relativo a `workdir/base_path` (canonical key para upsert).
  - Retornar `list[FileEntry]`.

**Pegadinhas:**
- `auth_mode != "none"` no MVP é fora de escopo — quando vier, implementar via `GIT_ASKPASS` ou URL com token. Por enquanto: `if auth_mode != "none": raise NotImplementedError(...)`.
- Tamanho máximo por arquivo: skipar arquivos > 5 MB (proteção). Logar warning.

**Validação:** apontar para o `homelab-infra` local via `file:///home/brunohsouza/code/Personal/homelab-infra`, rodar `sync()` e `list_files(...)`, conferir contagem de arquivos.

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

### Passo 5 — `TeiEmbeddingsClient` (Phase 5)

**Arquivo:** [src/knowledge_injector/infrastructure/embeddings/tei_embeddings_client.py](../src/knowledge_injector/infrastructure/embeddings/tei_embeddings_client.py)

- `embed(texts) -> list[list[float]]`:
  - `httpx.Client(timeout=60.0)` (instance-level, reaproveitar entre chamadas).
  - POST `{base_url}{embeddings_path}` (`/v1/embeddings`) com payload `{"input": texts, "model": model}`.
  - Resposta: `{"data": [{"embedding": [...], "index": i}, ...]}`.
  - Ordenar por `index` para garantir alinhamento com a entrada.
  - Validar que cada vetor tem `dimensions` (384) — se não, raise erro descritivo.
  - Batch de tamanho 32 por requisição (TEI aguenta mais, mas 32 é seguro). Se `len(texts) > 32`, dividir e concatenar.

**Pegadinhas:**
- Texto vazio → TEI rejeita. Filtrar `texts` vazios antes de mandar; o caller é responsável por reinjetar `[]` na posição correta (ou levantar — no MVP, levanta).
- Retry: 1 retry com backoff de 2s para 5xx. Sem retry em 4xx.

**Validação:** chamada direta com `["hello world"]` retorna lista de 1 vetor de 384 floats.

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
   QVEC=$(curl -s http://127.0.0.1:8080/v1/embeddings \
     -H "Content-Type: application/json" \
     -d '{"input":"como funciona o cluster","model":"BAAI/bge-small-en-v1.5"}' \
     | python -c "import sys,json; v=json.load(sys.stdin)['data'][0]['embedding']; print('['+','.join(str(x) for x in v)+']')")
   psql ... -c "SELECT d.path, left(c.content, 80), 1-(c.embedding<=>'$QVEC'::vector) AS sim
                FROM knowledge.knowledge_chunks c
                JOIN knowledge.knowledge_documents d ON d.id=c.document_id
                ORDER BY c.embedding<=>'$QVEC'::vector LIMIT 3;"
   ```

---

## 5. Out of scope (explícito)

Tudo abaixo fica para iterações futuras — **não** entrar no MVP:

- Chunking markdown-aware (header splitting). Hoje é por chars.
- Async pipeline (asyncpg / asyncio).
- Auth git via token/SSH.
- Métricas Prometheus, OpenTelemetry tracing.
- Retry com exponential backoff sofisticado.
- Manifests Kubernetes (CronJob) — Phase 7 do README.
- Suporte a múltiplas `KnowledgeSource` por execução (hoje é uma só, vinda do `.env`).
- Tokenização real (`token_count` fica `None`).
- Deduplicação inter-documento de chunks idênticos.
- Limpeza incremental de embeddings órfãos (FK ON DELETE CASCADE já cuida do caso simples).

---

## 6. Riscos & mitigações

| Risco | Probabilidade | Mitigação |
|---|---|---|
| `pgvector` não exposto via SQLAlchemy core sem o tipo customizado | Média | Usar `pgvector.sqlalchemy.Vector` (já em `pyproject.toml`) ou `cast(:val AS vector)` em SQL textual |
| TEI rejeitar batch grande de markdown | Baixa | Batch de 32, com retry, e logar size |
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
5. ✅ `knowledge_chunks.count` > 0, todos com `embedding IS NOT NULL` e dimensão 384.
6. ✅ Re-run sem mudança no repo: `chunks_created=0`, `files_changed=0`.
7. ✅ Edição de arquivo + re-run: documento ganha versão atualizada (mesmo `id`), chunks substituídos.
8. ✅ Query de similaridade retorna top-K com `cosine_sim` razoável (>0.3 para query relacionada).

---

## 8. Estimativa de esforço

| Passo | Esforço |
|---|---|
| 1. Database engine | 15 min |
| 2. Repositories (4) | 60 min |
| 3. GitRepositoryClient | 30 min |
| 4. ChunkingService (MVP) | 20 min |
| 5. TeiEmbeddingsClient | 30 min |
| 6. IngestionService | 60 min |
| 7. Container wiring | 15 min |
| 8. Smoke test + correções | 30 min |
| **Total** | **~4h focadas** |

Realístico em 1-2 sessões de trabalho.
