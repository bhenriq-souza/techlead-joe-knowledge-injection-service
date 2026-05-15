# Prompt — Passo 1: Database engine + session factory

> Use este prompt em uma sessão limpa de outro chat (Claude Code, Cursor, etc.) para executar **somente o Passo 1** do plano de implementação. Cole tudo da seção "PROMPT" abaixo.

---

## Contexto desta tarefa (para você que está coordenando)

- Projeto: `knowledge-injector` (Python 3.12, uv).
- Plano-mestre: [docs/implementation-plan.md](../../implementation-plan.md). Esta tarefa cobre **apenas o Passo 1** da Seção 4.
- Já está pronto: schema `knowledge` no Postgres, ORM, domain models, ports, CLI, config carregando `.env`.
- Objetivo deste passo: implementar o módulo `Database` que hoje é um stub com `NotImplementedError`.

---

## PROMPT (copie a partir daqui)

````markdown
Você é um engenheiro de software trabalhando no repositório `techlead-joe-knowledge-injection-service` (Python 3.12, gerenciado com uv). Sua tarefa é implementar **apenas** o Passo 1 do plano de implementação MVP.

## Como se orientar antes de escrever código

Leia, nesta ordem, para entender o contexto:

1. `docs/implementation-plan.md` — leia a Seção 1 (baseline), Seção 2 (princípios), Seção 3 (fluxo) e **especialmente a Seção 4, Passo 1** (a tarefa).
2. `pyproject.toml` — confira as dependências disponíveis (sqlalchemy, psycopg, pydantic-settings já estão lá; não adicione novas).
3. `src/knowledge_injector/config.py` — entenda como `AppSettings.database.dsn` e `AppSettings.database.schema_` são expostos.
4. `src/knowledge_injector/infrastructure/db/database.py` — o stub atual que você vai substituir.
5. `src/knowledge_injector/infrastructure/db/orm.py` — o `Base` declarativo e os modelos ORM (não precisa modificar).
6. `src/knowledge_injector/containers.py` — como `Database` é instanciado via DI (provider `db`).

## Tarefa

Substituir o stub em `src/knowledge_injector/infrastructure/db/database.py` por uma implementação real que:

1. Cria um `Engine` síncrono do SQLAlchemy 2.0 a partir do DSN recebido no construtor.
   - Use `create_engine(dsn, future=True, pool_pre_ping=True)`.
   - O DSN já vem com o driver `postgresql+psycopg://` configurado pela `DatabaseSettings.dsn` (não monte o DSN manualmente).
2. Expõe uma `sessionmaker` configurada como:
   - `class_=Session` (síncrono, do `sqlalchemy.orm`).
   - `expire_on_commit=False`.
   - `autoflush=False`.
3. Disponibiliza um context manager `session()` que:
   - Abre uma `Session`.
   - Faz `commit()` ao sair sem exceção.
   - Faz `rollback()` ao sair com exceção e re-levanta.
   - Sempre fecha a sessão no `finally`.
4. Mantém o método `health_check() -> bool`:
   - Abre uma sessão, executa `SELECT 1`, retorna `True`.
   - Em caso de qualquer exceção, loga warning e retorna `False`.
5. Armazena `self.dsn` e `self.schema` (já no construtor existente) — não remover.

### Constraints

- **Síncrono.** Não use `AsyncEngine`, `async_sessionmaker`, nem `asyncio` neste passo, mesmo que o `pyproject.toml` tenha `sqlalchemy[asyncio]`.
- **Não adicione dependências.** Tudo necessário já está em `pyproject.toml`.
- **Não toque em outros arquivos** além do `database.py`. O wiring no `containers.py` virá em um passo posterior.
- **Não comece os Passos 2–8.** Pare assim que o Passo 1 estiver verificável.
- **Logging via structlog.** Use `from knowledge_injector.infrastructure.logging.logger import get_logger` (mesmo padrão do stub atual).
- **Tipagem.** Type hints completos; o projeto é Python 3.12 — pode usar `|` em vez de `Optional`.
- **Sem comentários decorativos.** Só comente uma coisa se ela for não-óbvia (alguma sutileza do SQLAlchemy 2.0, por exemplo). Não escreva docstrings de mais de uma linha.

### Forma esperada (referência)

```python
from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from knowledge_injector.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class Database:
    def __init__(self, dsn: str, schema: str = "knowledge") -> None:
        self.dsn = dsn
        self.schema = schema
        self._engine = create_engine(dsn, future=True, pool_pre_ping=True)
        self._session_factory = sessionmaker(
            bind=self._engine,
            class_=Session,
            expire_on_commit=False,
            autoflush=False,
        )

    @contextmanager
    def session(self) -> Iterator[Session]:
        ...

    def health_check(self) -> bool:
        ...
```

Adapte conforme necessário; a forma acima é orientativa, não normativa.

## Validação (você executa antes de declarar concluído)

1. Rodar a partir da raiz do projeto:
   ```bash
   uv run python -c "
   from knowledge_injector.containers import Container
   c = Container()
   db = c.db()
   assert db.health_check() is True, 'health_check should return True'
   print('OK — Database connecting and health check passed')
   "
   ```
   Resultado esperado: `OK — Database connecting and health check passed`.

2. Verificar que uma sessão consegue executar uma query trivial e commitar:
   ```bash
   uv run python -c "
   from knowledge_injector.containers import Container
   from sqlalchemy import text
   c = Container()
   db = c.db()
   with db.session() as s:
       result = s.execute(text('SELECT 1 AS one')).scalar_one()
       assert result == 1
   print('OK — session() context manager works')
   "
   ```

3. Confirmar que rollback funciona em caso de exceção:
   ```bash
   uv run python -c "
   from knowledge_injector.containers import Container
   from sqlalchemy import text
   c = Container()
   db = c.db()
   try:
       with db.session() as s:
           s.execute(text('SELECT 1'))
           raise RuntimeError('boom')
   except RuntimeError:
       pass
   print('OK — rollback path executed without leaking session')
   "
   ```

Se algum dos três falhar, corrija e re-rode antes de finalizar.

## Pré-condições do ambiente (já validadas pelo time)

- Postgres disponível em `192.168.15.97:5432`, DB `homelab_ai`, role `appuser`.
- O arquivo `.env` na raiz do projeto está populado (`POSTGRES_*`, `KNOWLEDGE_*`, `TEI_*`, etc.).
- A migração `0001_initial_schema` já foi aplicada (schema `knowledge` existe com 4 tabelas).
- O `pgvector` 0.8.2 está instalado no banco.

Se algum desses pré-requisitos falhar durante a validação, **pare e reporte ao usuário** — não tente reaplicar migrações nem mexer no `.env`.

## Entregável final

- Um único arquivo modificado: `src/knowledge_injector/infrastructure/db/database.py`.
- Os 3 comandos de validação acima passando.
- Uma resposta curta (até 5 linhas) descrevendo o que foi implementado e quais comandos de validação rodaram com sucesso.

Não escreva README, não atualize o `implementation-plan.md`, não crie testes em `tests/` (isso vem em outra fase). Foque exclusivamente no Passo 1.
````

---

## Notas para o coordenador (não enviar para o outro chat)

- O prompt foi pensado para ser auto-contido — qualquer agente com acesso ao repositório consegue executar sem histórico.
- Se o agente tentar avançar para o Passo 2 sozinho (ex.: começar a implementar repositórios), interrompa e relembre o escopo.
- Próximo prompt nesta série será `passo-02-repositories.md` — só crie depois que este passo estiver mergeado/validado.
- Se o agente reportar falha de conexão durante a validação, conferir primeiro:
  1. `.env` carregado corretamente (`POSTGRES_HOST=192.168.15.97`, não `postgres.dev.svc.cluster.local`).
  2. Conectividade de rede do WSL para `192.168.15.97:5432` (`nc -zv 192.168.15.97 5432`).
  3. Role `appuser` ainda válido (senha não rotacionada).
