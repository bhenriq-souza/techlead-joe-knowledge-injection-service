# Prompt — Passo 3.3: Pub/Sub Ingestion Consumer

> Use este prompt em uma sessão limpa de outro chat (Claude Code, Cursor, etc.) para implementar **apenas o Passo 3.3** do backlog de ingestão event-driven.
>
> Este passo implementa o **adapter de consumo de mensagens Pub/Sub** no worker Python. Não implementa a lógica de ingestão incremental (isso é o Passo 3.5).

---

## Contexto desta tarefa (para você que está coordenando)

- Projeto: `knowledge-injector` (Python 3.12, uv).
- Plano-mestre: `docs/implementation-plan.md` — seção "Backlog — Event-driven Knowledge Ingestion", Passo 3.3.
- Decisão arquitetural: `docs/architecture/knowledge-ingestion-event-driven.md`.
- Passo 3.1 já deve estar concluído: `SourceIngestionEvent`, `IngestionEventConsumerPort` e os demais contratos de domínio estão definidos.
- Objetivo deste passo: criar o adapter `PubSubConsumer` que implementa `IngestionEventConsumerPort`, recebe mensagens, deserializa e chama o handler de ingestão.

---

## PROMPT (copie a partir daqui)

````markdown
Você é um engenheiro de software trabalhando no repositório `techlead-joe-knowledge-injection-service` (Python 3.12, gerenciado com uv). Sua tarefa é implementar **apenas o Passo 3.3** do backlog de ingestão event-driven: o adapter de consumo de mensagens Pub/Sub.

## Como se orientar antes de escrever código

Leia, nesta ordem:

1. `agents/SKILL.md` — contexto master do projeto, regras de arquitetura e convenções.
2. `docs/architecture/knowledge-ingestion-event-driven.md` — decisão arquitetural completa.
3. `docs/implementation-plan.md` — Passo 3.3 e contexto do backlog geral.
4. `src/knowledge_injector/domain/models.py` — em particular `SourceIngestionEvent`.
5. `src/knowledge_injector/domain/ports.py` — em particular `IngestionEventConsumerPort`.
6. `src/knowledge_injector/config.py` — configurações existentes; você precisará adicionar novas.
7. `src/knowledge_injector/containers.py` — DI container atual para entender onde wiar o novo adapter.
8. `src/knowledge_injector/infrastructure/logging/logger.py` — padrão de logging estruturado.

## Tarefa

### A) Criar `src/knowledge_injector/infrastructure/pubsub/pubsub_consumer.py`

Implementar `PubSubConsumer` que implementa `IngestionEventConsumerPort`.

**Dependências de runtime:**

- `google-cloud-pubsub` para consumo de mensagens (adicionar ao `pyproject.toml` se não estiver).
- `httpx` já está disponível (não usar aqui — apenas para consulta futura).

**Comportamento:**

- Conectar ao subscription configurado (`PUBSUB_PROJECT_ID` + `PUBSUB_SUBSCRIPTION_ID`).
- Para cada mensagem recebida:
  1. Decodificar o payload base64 → bytes → string → dict JSON.
  2. Validar que o dict contém todos os campos obrigatórios de `SourceIngestionEvent`.
  3. Construir `SourceIngestionEvent` a partir do dict.
  4. Chamar o handler injetado com o evento.
  5. Fazer `ack` da mensagem se o handler completar sem exceção.
  6. Fazer `nack` se o handler levantar exceção (para reprocessamento).
- Logar estruturadamente cada etapa relevante (recebida, processando, ack, nack, erro de schema).

**Campos obrigatórios para validação de schema:**

```python
REQUIRED_FIELDS = {
    "event_type", "provider", "repository_full_name",
    "project_id", "service_id", "source_id",
    "environment", "target_branch", "pull_request_number",
    "merge_commit_sha", "base_sha", "head_sha", "delivery_id",
}
```

Se algum campo obrigatório estiver ausente: `ack` a mensagem (não reprocessar mensagens malformadas), logar erro com os campos faltantes.

Se `event_type != "pull_request_merged"`: `ack` e ignorar (logar como `event_type_not_supported`).

**Idempotência preparada:**

O consumer não implementa idempotência aqui — isso é responsabilidade do handler (Passo 3.5). O consumer apenas garante que a mesma mensagem não seja processada em paralelo (Pub/Sub garante at-least-once delivery; o handler garante idempotência por `merge_commit_sha`).

**Estrutura sugerida:**

```python
class PubSubConsumer(IngestionEventConsumerPort):
    def __init__(
        self,
        project_id: str,
        subscription_id: str,
    ) -> None:
        ...

    def consume(self, handler: Callable[[SourceIngestionEvent], None]) -> None:
        # subscriber.subscribe(subscription_path, callback=_make_callback(handler))
        # streaming pull — bloqueante até sinal de parada
        ...
```

### B) Adicionar configuração Pub/Sub em `config.py`

Adicionar nova classe `PubSubSettings`:

```python
class PubSubSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PUBSUB_", extra="ignore",
        env_file=".env", env_file_encoding="utf-8"
    )

    project_id: str = Field(default="")
    subscription_id: str = Field(default="knowledge-ingestion-events-sub")
```

Adicionar campo em `AppSettings`:

```python
pubsub: PubSubSettings = Field(default_factory=PubSubSettings)
```

### C) Wiar `PubSubConsumer` no container DI (`containers.py`)

Adicionar provider para `PubSubConsumer`:

```python
pubsub_consumer = providers.Factory(
    PubSubConsumer,
    project_id=settings.provided.pubsub.project_id,
    subscription_id=settings.provided.pubsub.subscription_id,
)
```

### D) Adicionar `__init__.py` em `infrastructure/pubsub/` (se necessário)

Criar `src/knowledge_injector/infrastructure/pubsub/__init__.py` vazio para torná-lo um package Python.

### E) Adicionar variáveis ao `.env.example` (se existir)

```env
PUBSUB_PROJECT_ID=my-gcp-project
PUBSUB_SUBSCRIPTION_ID=knowledge-ingestion-events-sub
```

## Constraints

- **Síncrono no core, streaming pull do Pub/Sub.** O `google-cloud-pubsub` usa um modelo de callback em thread separada para streaming pull — isso é aceitável. Não usar `asyncio`.
- **Sem lógica de ingestão.** O consumer apenas recebe, valida schema, constrói `SourceIngestionEvent` e chama o handler. A lógica de processar arquivos, chunking e embeddings fica no Passo 3.5.
- **Logging via structlog.** `from knowledge_injector.infrastructure.logging.logger import get_logger`.
- **Type hints completos.** Python 3.12 — use `|` em vez de `Optional`.
- **Sem comentários decorativos.**
- **Não modifique** `domain/models.py`, `domain/ports.py` nem os arquivos de `infrastructure/db/`.

## Validação

```bash
# 1. Verificar que a nova dependência pode ser importada
uv add google-cloud-pubsub  # se ainda não estiver
uv run python -c "from google.cloud import pubsub_v1; print('pubsub_v1 importado')"

# 2. Verificar que o consumer importa sem erro
uv run python -c "
from knowledge_injector.infrastructure.pubsub.pubsub_consumer import PubSubConsumer
from knowledge_injector.domain.ports import IngestionEventConsumerPort
assert issubclass(PubSubConsumer, IngestionEventConsumerPort), 'PubSubConsumer deve implementar IngestionEventConsumerPort'
print('OK — PubSubConsumer importado e herança correta')
"

# 3. Testar parsing de evento válido (sem conexão Pub/Sub real)
uv run python -c "
import json, base64
from knowledge_injector.infrastructure.pubsub.pubsub_consumer import PubSubConsumer

consumer = PubSubConsumer(project_id='test-project', subscription_id='test-sub')

# Simular mensagem Pub/Sub válida
event_dict = {
    'event_type': 'pull_request_merged',
    'provider': 'github',
    'repository_full_name': 'org/repo',
    'project_id': 'proj-1',
    'service_id': 'svc-1',
    'source_id': 'src-1',
    'environment': 'prd',
    'target_branch': 'main',
    'pull_request_number': 42,
    'merge_commit_sha': 'abc123',
    'base_sha': 'old123',
    'head_sha': 'new456',
    'delivery_id': 'gh-1',
}
evt = consumer._parse_event(json.dumps(event_dict))
assert evt is not None
assert evt.environment == 'prd'
assert evt.merge_commit_sha == 'abc123'

# Simular mensagem com campo faltando (deve retornar None)
bad_dict = {k: v for k, v in event_dict.items() if k != 'source_id'}
evt_bad = consumer._parse_event(json.dumps(bad_dict))
assert evt_bad is None, 'evento com campo faltando deve retornar None'

print('OK — PubSubConsumer: parse de evento válido e inválido funcionando')
"

# 4. Testar que config foi atualizada
uv run python -c "
from knowledge_injector.config import AppSettings
s = AppSettings.from_env()
assert hasattr(s, 'pubsub'), 'AppSettings deve ter campo pubsub'
assert hasattr(s.pubsub, 'project_id'), 'PubSubSettings deve ter project_id'
print(f'OK — PubSubSettings carregado: project_id={s.pubsub.project_id!r}')
"
```

O método `_parse_event(raw_json: str) -> SourceIngestionEvent | None` deve ser um método auxiliar público-testável do `PubSubConsumer`.

## Entregável final

- `src/knowledge_injector/infrastructure/pubsub/__init__.py` (vazio).
- `src/knowledge_injector/infrastructure/pubsub/pubsub_consumer.py` — implementação do consumer.
- `src/knowledge_injector/config.py` — com `PubSubSettings` adicionado.
- `src/knowledge_injector/containers.py` — com `pubsub_consumer` wired.
- `pyproject.toml` — com `google-cloud-pubsub` adicionado (se necessário).
- Validação passando.
- Uma resposta curta (até 5 linhas) descrevendo o que foi implementado.

Não implemente a lógica de ingestão incremental, não avance para o Passo 3.4.
````

---

## Notas para o coordenador (não enviar para o outro chat)

- O `google-cloud-pubsub` usa streaming pull com callbacks em threads. O método `consume()` bloqueia até `streaming_pull_future.result()`. Isso é OK para o modo `run-once` via CLI.
- O `_parse_event` sendo método público facilita testes unitários sem conexão com Pub/Sub.
- O nack deve ser usado com cautela: mensagens malformadas (bad schema) devem receber `ack` para não criar loop infinito de reprocessamento. Apenas erros de handler (ex.: DB indisponível) devem receber `nack`.
- A idempotência real (não reprocessar mesmo `merge_commit_sha`) fica no handler do Passo 3.5, não no consumer.
- Próximo passo: `agents/prompts/passo-06-github-content-client.md`.
