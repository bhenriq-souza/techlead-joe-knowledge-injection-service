````markdown
Você é um engenheiro de software trabalhando no repositório `techlead-joe-knowledge-injection-service` (Python 3.12, gerenciado com uv). Sua tarefa é implementar **apenas** o Passo 2 do plano de implementação MVP.

## Como se orientar antes de escrever código

Leia, nesta ordem:

1. `docs/implementation-plan.md` — Seção 4, Passo 2 (repositórios), e a Seção 6 (pseudocódigo do `IngestionService`).
2. `src/knowledge_injector/domain/models.py` — dataclasses de domínio (`KnowledgeSource`, `IngestionRun`, `KnowledgeDocument`, `KnowledgeChunk`).
3. `src/knowledge_injector/domain/ports.py` — ABCs que os repositórios devem implementar (**você vai modificar este arquivo**; veja abaixo).
4. `src/knowledge_injector/infrastructure/db/orm.py` — modelos ORM; note que `KnowledgeChunkORM` **não** mapeia a coluna `embedding`.
5. `src/knowledge_injector/infrastructure/db/database.py` — o `Database` já implementado no Passo 1 (use só para entender como a `Session` é construída; não modifique).
6. `src/knowledge_injector/infrastructure/db/repositories.py` — stub vazio que você vai substituir.

## Tarefa

Você vai modificar **dois** arquivos:

### A) `src/knowledge_injector/domain/ports.py` — adicionar `session: Session` a cada método

O pseudocódigo do `IngestionService` (Seção 6 do plano) passa a sessão explicitamente em cada chamada:

```python
with self.db.session() as s:
    source = self.source_repo.upsert(source, s)
    run = self.run_repo.create(run, s)
```

Por isso, cada método abstrato nos ports precisa aceitar um `Session` como último parâmetro. Atualize as assinaturas de `KnowledgeSourceRepositoryPort`, `IngestionRunRepositoryPort`, `KnowledgeDocumentRepositoryPort` e `KnowledgeChunkRepositoryPort` para incluir `session: Session`. Não altere nenhuma outra lógica; apenas adicione o parâmetro.

### B) `src/knowledge_injector/infrastructure/db/repositories.py` — implementação real

Implemente as quatro classes abaixo, cada uma implementando o port correspondente.

#### 1. `KnowledgeSourceRepository`

```python
def upsert(self, source: KnowledgeSource, session: Session) -> KnowledgeSource
def find_by_name(self, name: str, session: Session) -> KnowledgeSource | None
```

- `upsert`: usa `INSERT INTO knowledge.knowledge_sources ... ON CONFLICT (name) DO UPDATE SET ...`.
  Use `sqlalchemy.dialects.postgresql.insert` para o upsert Postgres nativo.
  Retorna o registro atualizado (faça `RETURNING *` ou releia com `find_by_name`).
- `find_by_name`: query simples por `name`.

#### 2. `IngestionRunRepository`

```python
def create(self, run: IngestionRun, session: Session) -> IngestionRun
def update(self, run: IngestionRun, session: Session) -> IngestionRun
def find_by_id(self, run_id: UUID, session: Session) -> IngestionRun | None
```

- `create`: `session.add(_from_domain(run))` + `session.flush()` para obter campos gerados pelo DB (ex.: `created_at`). Retorna o domínio com campos atualizados.
- `update`: carrega o ORM por `run.id`, aplica os campos mudados, `flush()`, retorna o domínio.
- `find_by_id`: query por PK.

#### 3. `KnowledgeDocumentRepository`

```python
def upsert(self, document: KnowledgeDocument, session: Session) -> KnowledgeDocument
def find_by_source_and_path(self, source_id: UUID, path: str, session: Session) -> KnowledgeDocument | None
def find_active_by_source(self, source_id: UUID, session: Session) -> list[KnowledgeDocument]
def mark_deleted(self, document_id: UUID, session: Session) -> None
```

- `upsert`: `INSERT ... ON CONFLICT (source_id, path) DO UPDATE SET content_hash=..., status=..., ...`. Conflito na constraint `ix_knowledge_documents_source_path`.
- `find_active_by_source`: filtra `status = 'active'`.
- `mark_deleted`: `UPDATE ... SET status='deleted'` por PK; não deleta fisicamente.

#### 4. `KnowledgeChunkRepository`

```python
def replace_for_document(self, document_id: UUID, chunks: list[KnowledgeChunk], session: Session) -> list[KnowledgeChunk]
def delete_for_document(self, document_id: UUID, session: Session) -> int
```

- `delete_for_document`: `DELETE FROM knowledge.knowledge_chunks WHERE document_id = :id`, retorna contagem de linhas deletadas.
- `replace_for_document`: chama `delete_for_document`, depois insere todos os chunks com embedding via SQL textual (veja abaixo), retorna os chunks com `id` preenchido.

### Tratamento especial do embedding

A coluna `embedding` é do tipo `vector(384)` (pgvector) e **não está mapeada no ORM**. Use inserção via SQL textual:

```python
from sqlalchemy import text

session.execute(
    text("""
        INSERT INTO knowledge.knowledge_chunks
            (id, document_id, chunk_index, content, content_hash,
             token_count, metadata, embedding)
        VALUES
            (:id, :document_id, :chunk_index, :content, :content_hash,
             :token_count, :metadata::jsonb, CAST(:embedding AS vector))
    """),
    {
        "id": str(chunk.id),
        "document_id": str(chunk.document_id),
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "content_hash": chunk.content_hash,
        "token_count": chunk.token_count,
        "metadata": json.dumps(chunk.metadata),
        "embedding": "[" + ",".join(str(v) for v in chunk.embedding) + "]"
        if chunk.embedding else None,
    },
)
```

Se `chunk.embedding` for `None`, grave `NULL` na coluna (o banco aceita `NULL` no MVP).

### Helpers de mapeamento

Implemente funções privadas de módulo (não métodos) para manter os repositórios sem estado:

```python
def _source_to_domain(orm: KnowledgeSourceORM) -> KnowledgeSource: ...
def _run_to_domain(orm: IngestionRunORM) -> IngestionRun: ...
def _document_to_domain(orm: KnowledgeDocumentORM) -> KnowledgeDocument: ...
# Chunks lidos do banco não precisam de mapeamento no MVP (não os lemos de volta aqui)
```

### Constraints

- **Síncrono.** Sem `async`/`asyncio`.
- **Sem novas dependências.** `sqlalchemy`, `psycopg`, `pgvector` já estão em `pyproject.toml`.
- **Sem `session.commit()`** nos repositórios. Quem faz commit é o context manager `Database.session()` — os repos apenas `flush()` quando precisam de campos gerados pelo DB.
- **Logging via structlog.** `from knowledge_injector.infrastructure.logging.logger import get_logger`.
- **Type hints completos.** Python 3.12 — use `|` em vez de `Optional`.
- **Sem comentários decorativos.** Apenas onde a lógica não for óbvia.
- **Não toque em outros arquivos** além de `ports.py` e `repositories.py`.
- **Não comece o Passo 3.** Pare assim que o Passo 2 estiver verificável.

## Validação (você executa antes de declarar concluído)

Execute cada bloco a partir da raiz do projeto (`uv run python -c "..."`):

### 1 — KnowledgeSource: upsert + find_by_name

```bash
uv run python -c "
import uuid
from knowledge_injector.containers import Container
from knowledge_injector.domain.models import KnowledgeSource, SourceType
from knowledge_injector.infrastructure.db.repositories import KnowledgeSourceRepository

c = Container()
db = c.db()
repo = KnowledgeSourceRepository()

source = KnowledgeSource(
    name='test-source-' + str(uuid.uuid4())[:8],
    source_type=SourceType.GIT,
    repo_url='file:///tmp/test',
    branch='main',
    base_path='',
)

with db.session() as s:
    saved = repo.upsert(source, s)
    assert saved.id is not None
    found = repo.find_by_name(saved.name, s)
    assert found is not None
    assert found.name == saved.name

# Idempotência: segundo upsert não deve falhar
with db.session() as s:
    saved2 = repo.upsert(source, s)
    assert saved2.id == saved.id

print('OK — KnowledgeSourceRepository: upsert + find_by_name + idempotência')
"
```

### 2 — IngestionRun: create + find_by_id + update

```bash
uv run python -c "
import uuid
from datetime import datetime, timezone
from knowledge_injector.containers import Container
from knowledge_injector.domain.models import (
    KnowledgeSource, SourceType, IngestionRun, IngestionStatus,
)
from knowledge_injector.infrastructure.db.repositories import (
    KnowledgeSourceRepository, IngestionRunRepository,
)

c = Container()
db = c.db()
source_repo = KnowledgeSourceRepository()
run_repo = IngestionRunRepository()

# Precisa de um source_id válido
source = KnowledgeSource(
    name='run-test-' + str(uuid.uuid4())[:8],
    source_type=SourceType.GIT,
    repo_url='file:///tmp/test',
    branch='main',
    base_path='',
)
with db.session() as s:
    source = source_repo.upsert(source, s)

run = IngestionRun(
    source_id=source.id,
    status=IngestionStatus.RUNNING,
    started_at=datetime.now(timezone.utc),
)
with db.session() as s:
    created = run_repo.create(run, s)
    assert created.id is not None

with db.session() as s:
    found = run_repo.find_by_id(created.id, s)
    assert found is not None
    assert found.status == IngestionStatus.RUNNING
    found.status = IngestionStatus.SUCCEEDED
    found.files_seen = 42
    updated = run_repo.update(found, s)
    assert updated.status == IngestionStatus.SUCCEEDED

print('OK — IngestionRunRepository: create + find_by_id + update')
"
```

### 3 — KnowledgeDocument: upsert + find + mark_deleted

```bash
uv run python -c "
import uuid
from knowledge_injector.containers import Container
from knowledge_injector.domain.models import (
    KnowledgeSource, SourceType, KnowledgeDocument, DocumentStatus,
)
from knowledge_injector.infrastructure.db.repositories import (
    KnowledgeSourceRepository, KnowledgeDocumentRepository,
)

c = Container()
db = c.db()
source_repo = KnowledgeSourceRepository()
doc_repo = KnowledgeDocumentRepository()

source = KnowledgeSource(
    name='doc-test-' + str(uuid.uuid4())[:8],
    source_type=SourceType.GIT,
    repo_url='file:///tmp/test',
    branch='main',
    base_path='',
)
with db.session() as s:
    source = source_repo.upsert(source, s)

doc = KnowledgeDocument(
    source_id=source.id,
    path='docs/test.md',
    content_hash='abc123',
    status=DocumentStatus.ACTIVE,
)
with db.session() as s:
    saved = doc_repo.upsert(doc, s)
    assert saved.id is not None

    found = doc_repo.find_by_source_and_path(source.id, 'docs/test.md', s)
    assert found is not None
    assert found.content_hash == 'abc123'

    active = doc_repo.find_active_by_source(source.id, s)
    assert any(d.id == saved.id for d in active)

# Idempotência do upsert com hash diferente
with db.session() as s:
    doc.content_hash = 'def456'
    updated = doc_repo.upsert(doc, s)
    assert updated.id == saved.id
    found2 = doc_repo.find_by_source_and_path(source.id, 'docs/test.md', s)
    assert found2.content_hash == 'def456'

with db.session() as s:
    doc_repo.mark_deleted(saved.id, s)
    active_after = doc_repo.find_active_by_source(source.id, s)
    assert not any(d.id == saved.id for d in active_after)

print('OK — KnowledgeDocumentRepository: upsert + find + mark_deleted')
"
```

### 4 — KnowledgeChunk: replace_for_document + delete_for_document

```bash
uv run python -c "
import uuid
from knowledge_injector.containers import Container
from knowledge_injector.domain.models import (
    KnowledgeSource, SourceType, KnowledgeDocument, DocumentStatus, KnowledgeChunk,
)
from knowledge_injector.infrastructure.db.repositories import (
    KnowledgeSourceRepository, KnowledgeDocumentRepository, KnowledgeChunkRepository,
)

c = Container()
db = c.db()
source_repo = KnowledgeSourceRepository()
doc_repo = KnowledgeDocumentRepository()
chunk_repo = KnowledgeChunkRepository()

source = KnowledgeSource(
    name='chunk-test-' + str(uuid.uuid4())[:8],
    source_type=SourceType.GIT,
    repo_url='file:///tmp/test',
    branch='main',
    base_path='',
)
with db.session() as s:
    source = source_repo.upsert(source, s)

doc = KnowledgeDocument(
    source_id=source.id,
    path='docs/chunks.md',
    content_hash='aaa',
    status=DocumentStatus.ACTIVE,
)
with db.session() as s:
    doc = doc_repo.upsert(doc, s)

fake_embedding = [0.1] * 384
chunks = [
    KnowledgeChunk(
        document_id=doc.id,
        chunk_index=i,
        content=f'chunk content {i}',
        content_hash=f'hash{i}',
        embedding=fake_embedding,
    )
    for i in range(3)
]

with db.session() as s:
    result = chunk_repo.replace_for_document(doc.id, chunks, s)
    assert len(result) == 3

# replace deve deletar os antigos e inserir novos (idempotente)
with db.session() as s:
    result2 = chunk_repo.replace_for_document(doc.id, chunks, s)
    assert len(result2) == 3

with db.session() as s:
    deleted = chunk_repo.delete_for_document(doc.id, s)
    assert deleted == 3

print('OK — KnowledgeChunkRepository: replace_for_document + delete_for_document')
"
```

Se qualquer uma das validações falhar, corrija e re-rode antes de finalizar.

## Pré-condições do ambiente (já validadas)

- Postgres disponível em `192.168.15.97:5432`, DB `homelab_ai`, role `appuser`.
- `.env` na raiz do projeto já populado.
- Schema `knowledge` com 4 tabelas existe (`0001_initial_schema` aplicada).
- `pgvector` 0.8.2 instalado no banco.
- O `Database` do Passo 1 já foi implementado e está funcional.

Se algum desses pré-requisitos falhar, **pare e reporte ao usuário**.

## Entregável final

- Dois arquivos modificados:
  - `src/knowledge_injector/domain/ports.py` (apenas assinaturas com `session: Session`)
  - `src/knowledge_injector/infrastructure/db/repositories.py` (implementação real)
- Os 4 comandos de validação passando.
- Uma resposta curta (até 5 linhas) descrevendo o que foi implementado e quais validações passaram.

Crie testes unitários em `tests/unit` quando necessário, não atualize `implementation-plan.md`, não avance para o Passo 3.
````

---

## Notas para o coordenador (não enviar para o outro chat)

- O único ponto de atenção arquitetural neste passo é a adição de `session: Session` nos ports. O agente foi instruído a modificar `ports.py` explicitamente — se recusar, insista: a alternativa (repos guardando sessão como estado) é pior.
- Se o agente tentar usar `session.commit()` dentro dos repositórios, corrija: quem commita é o `Database.session()` context manager; os repos só fazem `flush()`.
- A inserção de `embedding` via SQL textual é obrigatória pois a coluna não está mapeada no ORM. Se o agente tentar mapear `embedding` no `KnowledgeChunkORM`, peça para não fazer isso — essa coluna é intencional do lado do ORM para evitar poluir o modelo com o tipo pgvector.
- Validação 4 (chunks) requer que as tabelas de source e document existam primeiro — o script já cria as dependências na sequência correta.
- Próximo prompt nesta série será `passo-03-git-repository-client.md` — só crie depois que este passo estiver validado.
- Se o agente reportar `psycopg.errors.UndefinedTable` durante a validação, confirme que o schema `knowledge` existe: `psql -h 192.168.15.97 -U appuser -d homelab_ai -c '\dn'`.
