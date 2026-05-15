# Prompt — Passo 3.5: Incremental Ingestion Handler

> Use este prompt em uma sessão limpa de outro chat (Claude Code, Cursor, etc.) para implementar **apenas o Passo 3.5** do backlog de ingestão event-driven.
>
> Este passo implementa a **orquestração da ingestão incremental**: o application service que coordena catálogo, GitHub Content Client, ChunkingService e OllamaEmbeddingsClient para processar um evento de PR mergeado.

---

## Contexto desta tarefa (para você que está coordenando)

- Projeto: `knowledge-injector` (Python 3.12, uv).
- Plano-mestre: `docs/implementation-plan.md` — seção "Backlog — Event-driven Knowledge Ingestion", Passo 3.5.
- Decisão arquitetural: `docs/architecture/knowledge-ingestion-event-driven.md`.
- **Pré-requisitos esperados concluídos:**
  - Passo 3.1: `SourceIngestionEvent`, `ChangedFile`, `FileChangeType`, `RepositoryContentClientPort`, contratos de domínio atualizados.
  - Passo 3.3: `PubSubConsumer` implementado.
  - Passo 3.4: `GithubContentClient` implementado.
  - `ChunkingService` e `OllamaEmbeddingsClient` podem ser stubs com `NotImplementedError` — o handler deve estar estruturado para chamá-los, mesmo que não estejam implementados ainda.
- Objetivo: implementar `IncrementalIngestionHandler` na camada de application, que orquestra todo o pipeline de ingestão a partir de um `SourceIngestionEvent`.

---

## PROMPT (copie a partir daqui)

````markdown
Você é um engenheiro de software trabalhando no repositório `techlead-joe-knowledge-injection-service` (Python 3.12, gerenciado com uv). Sua tarefa é implementar **apenas o Passo 3.5** do backlog: o `IncrementalIngestionHandler`.

## Como se orientar antes de escrever código

Leia, nesta ordem:

1. `agents/SKILL.md` — contexto master do projeto, regras de arquitetura e convenções.
2. `docs/architecture/knowledge-ingestion-event-driven.md` — decisão arquitetural completa.
3. `docs/implementation-plan.md` — Seção 3 (arquitetura de runtime do run-once) e Passo 3.5 do backlog.
4. `src/knowledge_injector/domain/models.py` — todos os modelos, especialmente `SourceIngestionEvent`, `ChangedFile`, `FileChangeType`, `KnowledgeSource`, `KnowledgeDocument`, `KnowledgeChunk`, `IngestionRun`.
5. `src/knowledge_injector/domain/ports.py` — todos os ports.
6. `src/knowledge_injector/application/ingestion_service.py` — implementação atual (stub) e padrão de orquestração.
7. `src/knowledge_injector/infrastructure/db/repositories.py` — implementações dos repositórios para entender os contratos reais.
8. `src/knowledge_injector/config.py` — configurações atuais.
9. `src/knowledge_injector/containers.py` — DI container para entender como wiar o novo handler.

## Contexto da tarefa

O `IncrementalIngestionHandler` é o componente de application que orquestra o pipeline de ingestão incremental para um único evento de PR mergeado.

Ele recebe um `SourceIngestionEvent`, consulta o catálogo, resolve o ambiente, calcula quais arquivos processar e persiste os resultados no banco de dados.

## Tarefa

### A) Criar `src/knowledge_injector/application/incremental_ingestion_handler.py`

**Construtor (via DI):**

```python
class IncrementalIngestionHandler:
    def __init__(
        self,
        db: Database,
        content_client: RepositoryContentClientPort,
        embeddings_client: EmbeddingsClientPort,
        chunking_service: ChunkingService,
        source_repo: KnowledgeSourceRepositoryPort,
        run_repo: IngestionRunRepositoryPort,
        doc_repo: KnowledgeDocumentRepositoryPort,
        chunk_repo: KnowledgeChunkRepositoryPort,
    ) -> None:
        ...
```

**Método principal: `handle(event: SourceIngestionEvent) -> None`**

O fluxo completo:

```
1. Abrir sessão DB — criar ingestion_run com status RUNNING
2. Buscar KnowledgeSource pelo source_id do evento
3. Validar que a target_branch do evento corresponde à branch da source
4. Validar que o environment do evento corresponde ao environment da source
5. Se validação falhar → marcar run como FAILED com mensagem clara
6. Chamar content_client.list_changed_files(repo, base_sha, head_sha)
7. Para cada ChangedFile:
   a. Verificar se path está na allowlist (source.allowed_paths)
   b. Verificar se path NÃO está na blocklist (source.blocked_paths)
   c. Se fora da allowlist ou na blocklist → ignorar, logar métrica
   d. Se change_type == REMOVED → marcar documento como deleted, deletar chunks
   e. Se change_type == RENAMED → marcar path antigo como deleted + processar path novo como ADDED
   f. Se change_type in (ADDED, MODIFIED) → processar arquivo
8. Finalizar ingestion_run com status SUCCEEDED | PARTIAL | FAILED e contadores
```

**Processamento de arquivo (ADDED / MODIFIED):**

```python
def _process_file(
    self,
    source: KnowledgeSource,
    changed_file: ChangedFile,
    event: SourceIngestionEvent,
    session: Session,
    counters: dict,
) -> None:
    file_entry = self.content_client.get_file_content(
        event.repository_full_name,
        changed_file.path,
        event.head_sha,
    )
    if file_entry is None:
        return  # arquivo removido entre o evento e o processamento

    existing = self.doc_repo.find_by_source_and_path(source.id, changed_file.path, session)
    if existing and existing.content_hash == file_entry.content_hash:
        return  # hash idêntico — sem mudança real

    doc = KnowledgeDocument(
        id=existing.id if existing else uuid4(),
        source_id=source.id,
        path=changed_file.path,
        content_hash=file_entry.content_hash,
        status=DocumentStatus.ACTIVE,
        last_commit_sha=event.merge_commit_sha,
        title=_extract_title(file_entry.content),
        mime_type=_guess_mime(changed_file.path),
    )
    doc = self.doc_repo.upsert(doc, session)

    chunks = self.chunking_service.chunk(file_entry, doc.id)
    if not chunks:
        return

    vectors = self.embeddings_client.embed([c.content for c in chunks])
    for c, v in zip(chunks, vectors):
        c.embedding = v

    self.chunk_repo.replace_for_document(doc.id, chunks, session)
    # atualizar contadores conforme ADDED vs MODIFIED
```

**Idempotência:**

Antes de criar o `ingestion_run`, verificar se já existe um run concluído (SUCCEEDED ou PARTIAL) com mesmo `source_id` e `merge_commit_sha`. Se existir, logar e retornar sem processar novamente.

Para isso, adicionar método `find_by_source_and_commit` em `IngestionRunRepositoryPort` (se ainda não existir) ou consultar via query existente.

**Allowlist / Blocklist:**

Usar glob matching com `pathlib.PurePosixPath(path).match(pattern)` ou `fnmatch.fnmatch(path, pattern)`. Função auxiliar privada `_is_allowed(path, source) -> bool`.

Regras:
- Se `source.allowed_paths` estiver vazio → aceitar todos.
- Se `source.blocked_paths` estiver vazio → não bloquear nenhum.
- Blocklist tem precedência sobre allowlist.

**Helpers (reaproveitar se já existirem no codebase):**

```python
def _extract_title(content: str) -> str | None:
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None

def _guess_mime(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return {
        "md": "text/markdown",
        "yaml": "application/yaml",
        "yml": "application/yaml",
        "txt": "text/plain",
    }.get(ext, "application/octet-stream")
```

### B) Atualizar `IngestionRunRepositoryPort` em `domain/ports.py` (se necessário)

Se não existir, adicionar:

```python
@abstractmethod
def find_by_source_and_commit(
    self, source_id: UUID, commit_sha: str, session: Session
) -> IngestionRun | None:
    """Find a completed run for the given source and commit SHA."""
```

E implementar o método correspondente em `infrastructure/db/repositories.py`.

### C) Adicionar campo `merge_commit_sha` em `IngestionRun` (se necessário)

Verificar se `IngestionRun` já possui um campo adequado para armazenar o commit SHA do evento. `repo_commit_sha` já existe — usar este campo para `merge_commit_sha` do evento.

### D) Wiar `IncrementalIngestionHandler` no container DI (`containers.py`)

```python
incremental_handler = providers.Factory(
    IncrementalIngestionHandler,
    db=db,
    content_client=github_content_client,
    embeddings_client=embeddings_client,
    chunking_service=chunking_service,
    source_repo=source_repo,
    run_repo=run_repo,
    doc_repo=doc_repo,
    chunk_repo=chunk_repo,
)
```

## Constraints

- **Application layer somente.** `IncrementalIngestionHandler` fica em `src/knowledge_injector/application/`.
- **Sem infraestrutura nova.** Não criar novos arquivos em `infrastructure/`.
- **Depende de abstrações.** O handler usa ports, não implementações concretas.
- **Síncrono.** Sem `async`/`asyncio`.
- **Idempotente.** Mesmo evento (`source_id + merge_commit_sha`) não reprocessa se já houver run bem-sucedido.
- **Transações por documento.** Cada arquivo processado é uma unidade transacional. Falha em um arquivo não derruba o run — registra erro e continua.
- **Type hints completos.** Python 3.12, use `|` em vez de `Optional`.
- **Logging via structlog.** Logar: `source_id`, `environment`, `pull_request_number`, `files_seen`, `files_changed`, `files_deleted`, `files_ignored`, `chunks_created`, `chunks_updated`.
- **Sem comentários decorativos.**

## Validação

```bash
# 1. Verificar importação
uv run python -c "
from knowledge_injector.application.incremental_ingestion_handler import IncrementalIngestionHandler
print('OK — IncrementalIngestionHandler importado')
"

# 2. Testar instanciação com mocks
uv run python -c "
from unittest.mock import MagicMock
from knowledge_injector.application.incremental_ingestion_handler import IncrementalIngestionHandler
from knowledge_injector.domain.models import (
    SourceIngestionEvent, KnowledgeSource, SourceType, ChangedFile, FileChangeType, FileEntry
)

# Criar mocks para todos os ports
mock_db = MagicMock()
mock_content_client = MagicMock()
mock_embeddings_client = MagicMock()
mock_chunking_service = MagicMock()
mock_source_repo = MagicMock()
mock_run_repo = MagicMock()
mock_doc_repo = MagicMock()
mock_chunk_repo = MagicMock()

handler = IncrementalIngestionHandler(
    db=mock_db,
    content_client=mock_content_client,
    embeddings_client=mock_embeddings_client,
    chunking_service=mock_chunking_service,
    source_repo=mock_source_repo,
    run_repo=mock_run_repo,
    doc_repo=mock_doc_repo,
    chunk_repo=mock_chunk_repo,
)

# Testar _is_allowed
assert handler._is_allowed('docs/api.md', ['docs/**'], []) == True
assert handler._is_allowed('docs/api.md', ['docs/**'], ['docs/internal/**']) == True
assert handler._is_allowed('docs/internal/secret.md', ['docs/**'], ['docs/internal/**']) == False
assert handler._is_allowed('src/app.py', ['docs/**'], []) == False
assert handler._is_allowed('src/app.py', [], []) == True  # allowlist vazia = aceitar tudo

print('OK — IncrementalIngestionHandler instanciado e _is_allowed validado')
"

# 3. Testar idempotência (run já existente)
uv run python -c "
from unittest.mock import MagicMock, patch
from knowledge_injector.application.incremental_ingestion_handler import IncrementalIngestionHandler
from knowledge_injector.domain.models import (
    SourceIngestionEvent, KnowledgeSource, SourceType, IngestionRun, IngestionStatus
)
from datetime import datetime, timezone
from uuid import uuid4

handler = IncrementalIngestionHandler(
    db=MagicMock(),
    content_client=MagicMock(),
    embeddings_client=MagicMock(),
    chunking_service=MagicMock(),
    source_repo=MagicMock(),
    run_repo=MagicMock(),
    doc_repo=MagicMock(),
    chunk_repo=MagicMock(),
)

# Simular que já existe run bem-sucedido para este commit
existing_run = IngestionRun(
    source_id=uuid4(),
    status=IngestionStatus.SUCCEEDED,
    started_at=datetime.now(timezone.utc),
    repo_commit_sha='abc123',
)
handler.run_repo.find_by_source_and_commit.return_value = existing_run

event = SourceIngestionEvent(
    event_type='pull_request_merged',
    provider='github',
    repository_full_name='org/repo',
    project_id='proj-1',
    service_id='svc-1',
    source_id='src-1',
    environment='prd',
    target_branch='main',
    pull_request_number=42,
    merge_commit_sha='abc123',
    base_sha='old123',
    head_sha='new456',
    delivery_id='gh-1',
)

# Se já existe run, não deve chamar content_client
source = MagicMock()
source.allowed_paths = ['docs/**']
source.blocked_paths = []
handler.source_repo.find_by_name.return_value = source

with MagicMock():
    handler.handle(event)

# content_client NÃO deve ter sido chamado
handler.content_client.list_changed_files.assert_not_called()
print('OK — idempotência: run existente não reprocessa')
"
```

## Entregável final

- `src/knowledge_injector/application/incremental_ingestion_handler.py` — handler completo.
- `src/knowledge_injector/domain/ports.py` — com `find_by_source_and_commit` adicionado (se necessário).
- `src/knowledge_injector/infrastructure/db/repositories.py` — implementação de `find_by_source_and_commit` (se port foi adicionado).
- `src/knowledge_injector/containers.py` — com `incremental_handler` wired.
- Validação passando.
- Uma resposta curta (até 5 linhas) descrevendo o que foi implementado e eventuais stubs ainda pendentes (ChunkingService, OllamaEmbeddingsClient).

Não implemente Initial Sync (Passo 3.6) nem Reconciliação (Passo 3.7) agora.
````

---

## Notas para o coordenador (não enviar para o outro chat)

- Se `ChunkingService` e `OllamaEmbeddingsClient` ainda forem stubs com `NotImplementedError`, o handler estará implementado mas não executável end-to-end até esses componentes serem completados.
- A idempotência por `merge_commit_sha` requer um método `find_by_source_and_commit` no repositório. Se o agente não conseguir implementar sem migration, orientar a usar uma query simples por `repo_commit_sha` na tabela `ingestion_runs`.
- O campo `IngestionRun.repo_commit_sha` já existe — usar ele para armazenar o `merge_commit_sha` do evento.
- O campo `KnowledgeSource.source_id` do evento é uma string que identifica a fonte no catálogo. No modelo atual, `KnowledgeSource.id` é um UUID interno. Pode ser necessário adicionar um campo `external_id: str | None = None` em `KnowledgeSource` ou buscar por `name`. O agente deve decidir a estratégia e ser explícito.
- Próximos passos: Passo 3.6 (Initial Sync) e Passo 3.7 (Reconciliação) — não possuem prompts ainda e podem ser criados após este passo ser validado.
