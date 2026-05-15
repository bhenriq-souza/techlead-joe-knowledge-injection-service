# Prompt — Passo 3.4: GitHub Content Client

> Use este prompt em uma sessão limpa de outro chat (Claude Code, Cursor, etc.) para implementar **apenas o Passo 3.4** do backlog de ingestão event-driven.
>
> Este passo implementa o **adapter para buscar arquivos alterados e conteúdo de arquivos via GitHub API**, sem clonar o repositório inteiro.

---

## Contexto desta tarefa (para você que está coordenando)

- Projeto: `knowledge-injector` (Python 3.12, uv).
- Plano-mestre: `docs/implementation-plan.md` — seção "Backlog — Event-driven Knowledge Ingestion", Passo 3.4.
- Decisão arquitetural: `docs/architecture/knowledge-ingestion-event-driven.md`.
- Passo 3.1 já deve estar concluído: `ChangedFile`, `FileChangeType`, `RepositoryContentClientPort` e `FileEntry` estão definidos no domínio.
- Objetivo deste passo: criar `GithubContentClient` que implementa `RepositoryContentClientPort`, usando a GitHub REST API para resolver diffs e baixar conteúdo sem clone local.

---

## PROMPT (copie a partir daqui)

````markdown
Você é um engenheiro de software trabalhando no repositório `techlead-joe-knowledge-injection-service` (Python 3.12, gerenciado com uv). Sua tarefa é implementar **apenas o Passo 3.4** do backlog: o adapter de conteúdo GitHub (`GithubContentClient`).

## Como se orientar antes de escrever código

Leia, nesta ordem:

1. `agents/SKILL.md` — contexto master do projeto, regras de arquitetura e convenções.
2. `docs/architecture/knowledge-ingestion-event-driven.md` — decisão arquitetural completa.
3. `docs/implementation-plan.md` — Passo 3.4 e contexto geral do backlog.
4. `src/knowledge_injector/domain/models.py` — em particular `FileEntry`, `ChangedFile`, `FileChangeType`.
5. `src/knowledge_injector/domain/ports.py` — em particular `RepositoryContentClientPort`.
6. `src/knowledge_injector/config.py` — configurações existentes; você precisará adicionar `GitHubSettings`.
7. `src/knowledge_injector/containers.py` — DI container atual.
8. `src/knowledge_injector/infrastructure/logging/logger.py` — padrão de logging.
9. `src/knowledge_injector/infrastructure/embeddings/ollama_embeddings_client.py` — referência de como implementar um adapter httpx seguindo as convenções do projeto.

## Contexto da tarefa

A abordagem event-driven exige que o worker baixe **apenas** os arquivos alterados em um PR mergeado — não o repositório inteiro.

Para isso, o worker precisa:

1. Consultar o diff entre `base_sha` e `head_sha` do merge → lista de arquivos `added`, `modified`, `removed`, `renamed`.
2. Para cada arquivo `added` ou `modified` que esteja na allowlist → baixar o conteúdo via GitHub API.
3. Para arquivos `removed` ou `renamed` → registrar no domínio para atualizar/deletar no banco.

Endpoints GitHub REST API relevantes:

- `GET /repos/{owner}/{repo}/compare/{base}...{head}` — retorna lista de arquivos alterados com `status` e `filename`.
- `GET /repos/{owner}/{repo}/contents/{path}?ref={sha}` — retorna conteúdo de um arquivo específico (base64-encoded).

## Tarefa

### A) Criar `src/knowledge_injector/infrastructure/github/github_content_client.py`

Implementar `GithubContentClient` que implementa `RepositoryContentClientPort`.

**Construtor:**

```python
class GithubContentClient(RepositoryContentClientPort):
    def __init__(
        self,
        token: str,
        base_url: str = "https://api.github.com",
        timeout: float = 30.0,
    ) -> None:
        ...
```

**Método `list_changed_files`:**

```python
def list_changed_files(
    self,
    repository_full_name: str,  # "org/repo"
    base_sha: str,
    head_sha: str,
) -> list[ChangedFile]:
```

- Chamar `GET /repos/{owner}/{repo}/compare/{base_sha}...{head_sha}`.
- Header `Authorization: Bearer {token}`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`.
- Iterar sobre `response["files"]` e mapear `file["status"]` para `FileChangeType`:
  - `"added"` → `FileChangeType.ADDED`
  - `"modified"` → `FileChangeType.MODIFIED`
  - `"removed"` → `FileChangeType.REMOVED`
  - `"renamed"` → `FileChangeType.RENAMED` (com `previous_filename` → `ChangedFile.previous_path`)
  - outros → logar warning e ignorar
- Retornar lista de `ChangedFile`.
- A API retorna no máximo 300 arquivos por chamada. Se `response["total_commits"] > 0` e a lista parecer truncada, logar warning. Não paginar no MVP.

**Método `get_file_content`:**

```python
def get_file_content(
    self,
    repository_full_name: str,
    path: str,
    ref: str,
) -> FileEntry | None:
```

- Chamar `GET /repos/{owner}/{repo}/contents/{path}?ref={ref}`.
- Se status 404 → retornar `None` (arquivo não existe nesse ref).
- Validar que `response["type"] == "file"` (ignorar diretórios).
- Validar tamanho: se `response["size"] > 5 * 1024 * 1024` (5 MB) → logar warning e retornar `None`.
- Decodificar `response["content"]` (base64) → bytes → string com `decode("utf-8", errors="replace")`.
- Calcular `content_hash = hashlib.sha256(<bytes brutos>).hexdigest()` — usar bytes, não string decodificada.
- Retornar `FileEntry(path=path, content=<string>, content_hash=<hash>, relative_path=path)`.

**Tratamento de erros:**

- Timeout: levanta exceção descritiva com `repository_full_name` e `path`.
- 401/403: levanta `PermissionError` com mensagem clara (não logar o token).
- 429 (rate limit): logar warning com `Retry-After` header se disponível, levantar exceção.
- 5xx: levanta exceção com status code.

**Reutilização do cliente httpx:**

```python
self._client = httpx.Client(
    base_url=base_url,
    headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    },
    timeout=timeout,
)
```

### B) Adicionar `GitHubSettings` em `config.py`

```python
class GitHubSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GITHUB_", extra="ignore",
        env_file=".env", env_file_encoding="utf-8"
    )

    token: str = Field(default="")
    api_base_url: str = Field(default="https://api.github.com")
    api_timeout: float = Field(default=30.0)
```

Adicionar em `AppSettings`:

```python
github: GitHubSettings = Field(default_factory=GitHubSettings)
```

### C) Criar `src/knowledge_injector/infrastructure/github/__init__.py` (vazio)

### D) Wiar `GithubContentClient` no container DI (`containers.py`)

```python
github_content_client = providers.Factory(
    GithubContentClient,
    token=settings.provided.github.token,
    base_url=settings.provided.github.api_base_url,
    timeout=settings.provided.github.api_timeout,
)
```

### E) Adicionar variáveis ao `.env.example` (se existir)

```env
GITHUB_TOKEN=ghp_your_personal_access_token
GITHUB_API_BASE_URL=https://api.github.com
GITHUB_API_TIMEOUT=30.0
```

## Constraints

- **httpx síncrono.** `httpx.Client`, não `AsyncClient`.
- **Sem clone local.** Nenhuma chamada a `git.Repo`, `subprocess`, `GitPython`.
- **Sem dependências novas além de httpx.** `httpx` já está em `pyproject.toml`.
- **Não expor o token nos logs.** Logar o endpoint e o status, não o token.
- **Type hints completos.** Python 3.12 — `|` em vez de `Optional`.
- **Sem comentários decorativos.**
- **Não modifique** `domain/models.py` nem `domain/ports.py`.

## Validação

```bash
# 1. Verificar importação sem erro
uv run python -c "
from knowledge_injector.infrastructure.github.github_content_client import GithubContentClient
from knowledge_injector.domain.ports import RepositoryContentClientPort
assert issubclass(GithubContentClient, RepositoryContentClientPort)
print('OK — GithubContentClient importado e herança correta')
"

# 2. Testar com mock HTTP (sem token real)
uv run python -c "
import json, hashlib, base64
from unittest.mock import MagicMock, patch
from knowledge_injector.infrastructure.github.github_content_client import GithubContentClient
from knowledge_injector.domain.models import FileChangeType

client = GithubContentClient(token='fake-token')

# Mock da resposta de compare
compare_response = {
    'total_commits': 2,
    'files': [
        {'filename': 'docs/api.md', 'status': 'modified'},
        {'filename': 'docs/old.md', 'status': 'removed'},
        {'filename': 'docs/new.md', 'status': 'renamed', 'previous_filename': 'docs/v1.md'},
        {'filename': 'src/app.py', 'status': 'added'},
    ]
}

mock_resp = MagicMock()
mock_resp.status_code = 200
mock_resp.json.return_value = compare_response
mock_resp.raise_for_status = MagicMock()

with patch.object(client._client, 'get', return_value=mock_resp):
    files = client.list_changed_files('org/repo', 'old123', 'new456')

assert len(files) == 4
by_path = {f.path: f for f in files}
assert by_path['docs/api.md'].change_type == FileChangeType.MODIFIED
assert by_path['docs/old.md'].change_type == FileChangeType.REMOVED
assert by_path['docs/new.md'].change_type == FileChangeType.RENAMED
assert by_path['docs/new.md'].previous_path == 'docs/v1.md'
assert by_path['src/app.py'].change_type == FileChangeType.ADDED
print('OK — list_changed_files com mock funcionando')

# Mock da resposta de get_file_content
content_bytes = b'# Hello World'
encoded = base64.b64encode(content_bytes).decode()
content_response = {
    'type': 'file',
    'size': len(content_bytes),
    'content': encoded + '\n',
    'encoding': 'base64',
}
mock_content_resp = MagicMock()
mock_content_resp.status_code = 200
mock_content_resp.json.return_value = content_response
mock_content_resp.raise_for_status = MagicMock()

with patch.object(client._client, 'get', return_value=mock_content_resp):
    entry = client.get_file_content('org/repo', 'docs/api.md', 'abc123')

assert entry is not None
assert entry.content == '# Hello World'
expected_hash = hashlib.sha256(content_bytes).hexdigest()
assert entry.content_hash == expected_hash, 'hash deve ser sha256 dos bytes brutos'
print('OK — get_file_content com mock funcionando')
print('OK — GithubContentClient: todos os testes passaram')
"

# 3. Testar config
uv run python -c "
from knowledge_injector.config import AppSettings
s = AppSettings.from_env()
assert hasattr(s, 'github')
assert hasattr(s.github, 'token')
print(f'OK — GitHubSettings: api_base_url={s.github.api_base_url!r}')
"
```

## Entregável final

- `src/knowledge_injector/infrastructure/github/__init__.py` (vazio).
- `src/knowledge_injector/infrastructure/github/github_content_client.py` — implementação completa.
- `src/knowledge_injector/config.py` — com `GitHubSettings`.
- `src/knowledge_injector/containers.py` — com `github_content_client` wired.
- Validação passando.
- Uma resposta curta (até 5 linhas) descrevendo o que foi implementado.

Não implemente a lógica de ingestão incremental, não avance para o Passo 3.5.
````

---

## Notas para o coordenador (não enviar para o outro chat)

- A API de compare do GitHub retorna no máximo 300 arquivos. PRs muito grandes podem ter o campo `files` truncado. O MVP aceita esse limite; o log de warning é suficiente.
- O content da API `contents` vem com newlines embutidos no base64 — usar `base64.b64decode(content.replace('\n', ''))` ou `base64.decodebytes(content.encode())`.
- `relative_path` no `FileEntry` retornado por `get_file_content` pode ser o mesmo que `path` (sem prefixo de repositório). O handler (Passo 3.5) aplicará allowlist/blocklist sobre esse path.
- O token GitHub precisa de permissão `contents: read` para repositórios privados.
- Para repositórios privados de organização, considerar usar GitHub App em vez de PAT no futuro.
- Próximo passo: `agents/prompts/passo-07-incremental-ingestion-handler.md`.
