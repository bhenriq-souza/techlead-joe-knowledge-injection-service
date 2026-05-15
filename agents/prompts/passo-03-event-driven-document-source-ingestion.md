# Prompt — Passo 3.1: Revisão de Domínio para Ingestão Event-Driven

> Use este prompt em uma sessão limpa de outro chat (Claude Code, Cursor, etc.) para implementar **apenas o Passo 3.1** do backlog de ingestão event-driven.
>
> Este passo é de **revisão de contratos internos** — não implementa Pub/Sub, GitHub API nem infraestrutura.

---

## Contexto desta tarefa (para você que está coordenando)

- Projeto: `knowledge-injector` (Python 3.12, uv).
- Plano-mestre: `docs/implementation-plan.md` — seção "Backlog — Event-driven Knowledge Ingestion", Passo 3.1.
- Decisão arquitetural: `docs/architecture/knowledge-ingestion-event-driven.md`.
- Já está pronto: schema `knowledge`, ORM, domain models, ports, CLI, config, `Database` (Passo 1) e `Repositories` (Passo 2).
- Objetivo deste passo: preparar os contratos de domínio para suportar a abordagem de ingestão orientada a eventos. Nenhuma infraestrutura nova é implementada aqui.

---

## PROMPT (copie a partir daqui)

````markdown
Você é um engenheiro de software trabalhando no repositório `techlead-joe-knowledge-injection-service` (Python 3.12, gerenciado com uv). Sua tarefa é implementar **apenas o Passo 3.1** do backlog de ingestão event-driven: revisão de domínio e contratos.

## Como se orientar antes de escrever código

Leia, nesta ordem:

1. `agents/SKILL.md` — contexto master do projeto, regras de arquitetura e convenções.
2. `docs/implementation-plan.md` — seção "Backlog — Event-driven Knowledge Ingestion", Passos 3.1 a 3.8, para entender o quadro geral.
3. `docs/architecture/knowledge-ingestion-event-driven.md` — decisão arquitetural completa.
4. `src/knowledge_injector/domain/models.py` — modelos atuais.
5. `src/knowledge_injector/domain/ports.py` — ports/ABCs atuais.
6. `src/knowledge_injector/config.py` — configurações atuais.
7. `src/knowledge_injector/containers.py` — DI container atual.

## Contexto da mudança arquitetural

O serviço deixa de ser um "Git repository indexer" com clone/pull local e passa a ser um serviço de ingestão controlada orientado a eventos.

O novo fluxo principal é:

```text
GitHub PR mergeado
  → GitHub/GitHub Actions publica evento no Pub/Sub
  → Worker consome evento
  → Worker consulta catálogo
  → Worker resolve ambiente pela branch de destino
  → Worker baixa apenas documentos permitidos e alterados via GitHub API
  → Worker atualiza documentos, chunks e embeddings
```

Este passo (3.1) prepara **apenas os contratos de domínio**: novos modelos de dados e ports necessários para que os passos seguintes (3.2 a 3.8) possam ser implementados de forma limpa.

## Tarefa

### A) Criar `SourceIngestionEvent` em `domain/models.py`

Adicionar dataclass que representa o evento normalizado recebido do Pub/Sub:

```python
@dataclass
class SourceIngestionEvent:
    event_type: str                   # "pull_request_merged"
    provider: str                     # "github"
    repository_full_name: str         # "org/repo"
    project_id: str
    service_id: str
    source_id: str
    environment: str                  # "dev", "hml", "prd"
    target_branch: str                # "main", "develop", etc.
    pull_request_number: int
    merge_commit_sha: str
    base_sha: str
    head_sha: str
    delivery_id: str
```

### B) Criar `EnvironmentMapping` em `domain/models.py`

Dataclass que representa o mapeamento branch → ambiente para uma fonte:

```python
@dataclass
class EnvironmentMapping:
    branch: str          # ex.: "main"
    environment: str     # ex.: "prd"
```

### C) Revisar `KnowledgeSource` em `domain/models.py`

Adicionar campos para suportar o novo modelo event-driven. Os campos abaixo devem ser **opcionais com default** para não quebrar código existente:

- `provider: str = "github"` — provedor do repositório.
- `environment: str | None = None` — ambiente desta fonte (`dev`, `hml`, `prd`).
- `allowed_paths: list[str] = field(default_factory=list)` — globs de paths permitidos para ingestão.
- `blocked_paths: list[str] = field(default_factory=list)` — globs de paths bloqueados.
- `trust_level: str = "standard"` — nível de confiabilidade da fonte.

> **Nota:** `repo_url` e `branch` já existem. Mantenha-os como estão.

### D) Criar `RepositoryContentClientPort` em `domain/ports.py`

Novo port que representa acesso a conteúdo de repositório **sem** necessidade de clone local. Diferente do `RepositoryClientPort` (que faz sync local), este port resolve conteúdo via API (ex.: GitHub API):

```python
class RepositoryContentClientPort(ABC):
    """Port for fetching repository content without local clone."""

    @abstractmethod
    def list_changed_files(
        self,
        repository_full_name: str,
        base_sha: str,
        head_sha: str,
    ) -> list["ChangedFile"]:
        """List files changed between two commits."""

    @abstractmethod
    def get_file_content(
        self,
        repository_full_name: str,
        path: str,
        ref: str,
    ) -> FileEntry | None:
        """Fetch content of a single file at a given ref. Returns None if not found."""
```

### E) Criar `ChangedFile` em `domain/models.py`

Dataclass que representa um arquivo alterado em um merge:

```python
class FileChangeType(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    REMOVED = "removed"
    RENAMED = "renamed"

@dataclass
class ChangedFile:
    path: str
    change_type: FileChangeType
    previous_path: str | None = None   # preenchido apenas para RENAMED
```

### F) Criar `IngestionEventConsumerPort` em `domain/ports.py`

Port abstrato para consumer de eventos de ingestão (Pub/Sub ou outro broker):

```python
class IngestionEventConsumerPort(ABC):
    """Port for consuming ingestion trigger events."""

    @abstractmethod
    def consume(self, handler: Callable[[SourceIngestionEvent], None]) -> None:
        """Start consuming events and invoke handler for each one."""
```

> Use `from typing import Callable` para o type hint.

## Constraints

- **Não implemente infraestrutura.** Nenhum arquivo em `infrastructure/` deve ser criado ou modificado.
- **Não altere** `containers.py`, `config.py`, `application/ingestion_service.py` nem CLI.
- **Não remova ports ou modelos existentes.** Adicione; não substitua.
- **Síncrono.** Sem `async`/`asyncio`.
- **Type hints completos.** Python 3.12 — use `|` em vez de `Optional`.
- **Sem comentários decorativos.** Apenas onde o "porquê" não for óbvio.
- **Preserve os imports existentes** em `models.py` e `ports.py`.
- **Não comece o Passo 3.2** (GitHub Actions). Pare assim que este passo estiver verificável.

## Validação

Execute a partir da raiz do projeto:

```bash
uv run python -c "
from knowledge_injector.domain.models import (
    SourceIngestionEvent,
    EnvironmentMapping,
    KnowledgeSource,
    ChangedFile,
    FileChangeType,
    SourceType,
    DocumentStatus,
    IngestionStatus,
)
from knowledge_injector.domain.ports import (
    RepositoryClientPort,
    RepositoryContentClientPort,
    IngestionEventConsumerPort,
    EmbeddingsClientPort,
    KnowledgeSourceRepositoryPort,
    IngestionRunRepositoryPort,
    KnowledgeDocumentRepositoryPort,
    KnowledgeChunkRepositoryPort,
)
from uuid import uuid4
from datetime import datetime, timezone

# Testar SourceIngestionEvent
evt = SourceIngestionEvent(
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
    delivery_id='gh-delivery-id',
)
assert evt.environment == 'prd'

# Testar EnvironmentMapping
mapping = EnvironmentMapping(branch='main', environment='prd')
assert mapping.branch == 'main'

# Testar KnowledgeSource com novos campos
src = KnowledgeSource(
    name='my-service-docs',
    source_type=SourceType.GIT,
    repo_url='https://github.com/org/repo',
    branch='main',
    base_path='docs/',
    provider='github',
    environment='prd',
    allowed_paths=['docs/**/*.md'],
    blocked_paths=['docs/internal/**'],
    trust_level='standard',
)
assert src.provider == 'github'
assert src.allowed_paths == ['docs/**/*.md']

# Testar ChangedFile
cf = ChangedFile(path='docs/api.md', change_type=FileChangeType.MODIFIED)
assert cf.change_type == FileChangeType.MODIFIED
assert cf.previous_path is None

cf_renamed = ChangedFile(
    path='docs/api-v2.md',
    change_type=FileChangeType.RENAMED,
    previous_path='docs/api.md',
)
assert cf_renamed.previous_path == 'docs/api.md'

# Testar que ports antigos ainda existem
from abc import ABC
assert issubclass(RepositoryContentClientPort, ABC)
assert issubclass(IngestionEventConsumerPort, ABC)

print('OK — domain contracts revisados: SourceIngestionEvent, EnvironmentMapping, ChangedFile, FileChangeType, KnowledgeSource (novos campos), RepositoryContentClientPort, IngestionEventConsumerPort')
"
```

Se qualquer asserção falhar, corrija e re-rode antes de declarar concluído.

## Entregável final

- `src/knowledge_injector/domain/models.py` — com `SourceIngestionEvent`, `EnvironmentMapping`, `ChangedFile`, `FileChangeType` adicionados; `KnowledgeSource` com campos novos opcionais.
- `src/knowledge_injector/domain/ports.py` — com `RepositoryContentClientPort` e `IngestionEventConsumerPort` adicionados.
- A validação passando (`OK — domain contracts revisados: ...`).
- Uma resposta curta (até 5 linhas) descrevendo o que foi adicionado.

Não crie arquivos em `infrastructure/`, não modifique `containers.py` nem `config.py`, não avance para o Passo 3.2.
````

---

## Notas para o coordenador (não enviar para o outro chat)

- A revisão de `KnowledgeSource` é aditiva (campos opcionais com default). Isso garante que o código existente em `containers.py`, `repositories.py` e testes não quebra.
- `RepositoryContentClientPort` tem semântica diferente de `RepositoryClientPort`: não faz sync local, opera sobre repositório remoto via API. No Passo 3.4 será implementado pelo `GithubContentClient`.
- `IngestionEventConsumerPort` usa `Callable` para não acoplar o port a nenhum framework específico de messaging.
- O Passo 3.2 (GitHub Actions) não depende deste passo no sentido de código Python, mas o evento JSON que o workflow publica deve ser compatível com `SourceIngestionEvent`.
- Próximo passo nesta série: `agents/prompts/passo-04-github-actions-to-pubsub.md`.
