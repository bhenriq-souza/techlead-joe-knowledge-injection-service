# Knowledge Ingestion Event-Driven

**Data:** 2026-05-15
**Status:** Ativo — substitui a abordagem de clone/pull local como caminho principal

---

## Contexto

O `knowledge-injection-service` é responsável por transformar documentação viva em conhecimento recuperável.

A abordagem inicial planejada era baseada em `clone/pull` local: clonar o repositório Git inteiro (ou atualizá-lo via fetch), listar arquivos e processar os que se enquadram nas regras de inclusão.

Esse caminho foi revisado por conflitar com princípios centrais do produto.

---

## Problema com clone/pull local

A abordagem de clone/pull local:

- Materializa todo ou boa parte do repositório antes de filtrar arquivos.
- Não está alinhada com a regra de "não indexar indiscriminadamente".
- Não respeita a granularidade de "processar apenas fontes documentais confiáveis e aprovadas".
- Torna a sincronização incremental mais complexa (comparação de SHAs local vs. remote).
- Impede uma visão clara de "quais arquivos mudaram neste PR específico".

---

## Decisão

Adotar uma arquitetura de ingestão orientada a eventos:

```text
GitHub PR Merge
  → GitHub/GitHub Actions publica evento normalizado no Pub/Sub
  → Knowledge Ingestion Worker consome evento
  → Worker consulta catálogo (fonte de verdade)
  → Worker resolve ambiente pela branch de destino
  → Worker calcula delta (arquivos alterados no merge)
  → Worker baixa apenas documentos permitidos e alterados via GitHub API
  → Worker atualiza embeddings, chunks e documentos no PostgreSQL
```

Não haverá Webhook Receiver próprio neste momento. O evento é disparado pelo GitHub/GitHub Actions diretamente para o tópico Pub/Sub.

---

## Catálogo como fonte de verdade

O catálogo define:

| Campo | Descrição |
|-------|-----------|
| `project_id` | Projeto ao qual a fonte pertence |
| `service_id` | Serviço ao qual a fonte pertence |
| `source_id` | Identificador único da fonte documental |
| `repository_full_name` | Ex.: `org/repo` |
| `environment` | Ambiente: `dev`, `hml`, `prd` |
| `branch` | Branch monitorada para o ambiente |
| `allowed_paths` | Lista de paths (globs) permitidos |
| `blocked_paths` | Lista de paths (globs) bloqueados |
| `doc_type` | Tipo documental (ex.: `markdown`, `openapi`) |
| `trust_level` | Nível de confiabilidade da fonte |

O worker **não confia cegamente no evento** para decidir o que indexar.  
Ele **sempre consulta o catálogo** antes de baixar qualquer conteúdo.

---

## Branch por ambiente

O gatilho conceitual do incremental sync é:

```text
pull_request closed + merged=true
```

Com validação de que a branch de destino do PR corresponde à branch cadastrada no catálogo para o ambiente.

Exemplo de mapeamento:

| Branch | Ambiente |
|--------|----------|
| `develop` | `dev` |
| `homolo` | `hml` |
| `main` | `prd` |

---

## Tipos de sincronização

### Initial sync

Ocorre quando um repositório/fonte documental é associado ao catálogo pela primeira vez.

- Processa todas as fontes documentais permitidas no catálogo.
- **Não** clona nem processa o repositório inteiro.
- Consulta apenas os paths explicitamente listados como permitidos.

### Incremental sync

Ocorre quando um PR é mergeado na branch configurada para o ambiente.

- Evento recebido via Pub/Sub.
- Worker consulta catálogo, resolve ambiente, calcula delta.
- Processa apenas arquivos alterados e permitidos.

---

## Estrutura do evento Pub/Sub

O evento deve ser normalizado, pequeno e explícito:

```json
{
  "event_type": "pull_request_merged",
  "provider": "github",
  "repository_full_name": "org/repo",
  "project_id": "project-123",
  "service_id": "service-abc",
  "source_id": "source-xyz",
  "environment": "prd",
  "target_branch": "main",
  "pull_request_number": 42,
  "merge_commit_sha": "abc123",
  "base_sha": "old123",
  "head_sha": "new456",
  "delivery_id": "github-event-id"
}
```

---

## Fluxo do worker

1. Consumir mensagem do Pub/Sub.
2. Criar `ingestion_run` com status `running`.
3. Consultar catálogo pelo `source_id`.
4. Resolver ambiente pela `target_branch`.
5. Calcular diff do merge (`base_sha..head_sha`).
6. Filtrar arquivos por `allowed_paths` e `blocked_paths`.
7. Baixar conteúdo dos documentos aprovados via GitHub API.
8. Extrair metadados e classificar confiabilidade.
9. Gerar chunks (ChunkingService).
10. Gerar embeddings via Ollama (OllamaEmbeddingsClient).
11. Atualizar `knowledge_documents`.
12. Atualizar `knowledge_chunks`.
13. Finalizar `ingestion_run` com contadores e status.

---

## Regras para tipos de mudança de arquivo

| Tipo de mudança | Ação |
|-----------------|------|
| `added` | Criar documento, chunks e embeddings |
| `modified` | Recalcular hash, chunks e embeddings |
| `removed` | Marcar documento como `deleted`, remover/desativar chunks |
| `renamed` | Marcar path antigo como `deleted`, criar/atualizar path novo |
| Fora da allowlist | Ignorar e registrar métrica |
| Hash inalterado | Ignorar para evitar reprocessamento (idempotência) |

---

## Reconciliação periódica

Mesmo com eventos, manter um processo periódico de reconciliação com modo `full_allowed_sources_sync`:

- Reavaliar todos os documentos permitidos no catálogo.
- Comparar estado atual do catálogo/repositório com documentos persistidos.
- Corrigir divergências (documentos ausentes, SHAs desatualizados).
- **Não** clonar nem indexar o repositório inteiro.

---

## Posição do GitRepositoryClient

O `GitRepositoryClient` (baseado em clone/pull local) deixa de ser o caminho principal.

Pode ser mantido futuramente como:

- Adapter auxiliar para desenvolvimento local sem acesso ao GitHub API.
- Fallback para repositórios não hospedados no GitHub.
- Ferramenta de initial sync em ambientes sem Pub/Sub.

Não deve ser removido agora, mas não deve ser implementado como caminho principal de produção.

---

## Consequências

| Aspecto | Impacto |
|---------|---------|
| `KnowledgeSource` | Precisa de campos: `provider`, `environment`, `branch`, `allowed_paths`, `blocked_paths` |
| `RepositoryClientPort` | Separar em `RepositoryContentClientPort` (foco em conteúdo, sem sync local) |
| Novos ports | `IngestionEventConsumerPort` para consumo de Pub/Sub |
| Config | Novas variáveis: `PUBSUB_PROJECT_ID`, `PUBSUB_SUBSCRIPTION_ID`, `GITHUB_TOKEN` |
| Infra | Novo adapter: `GithubContentClient` em `infrastructure/github/` |
| Infra | Novo adapter: `PubSubConsumer` em `infrastructure/pubsub/` |
| Testes | Mocks de GitHub API e Pub/Sub para unit tests |

---

## Arquivos relacionados

- [agents/prompts/passo-03-event-driven-document-source-ingestion.md](../../agents/prompts/passo-03-event-driven-document-source-ingestion.md) — Revisão de contratos de domínio
- [agents/prompts/passo-04-github-actions-to-pubsub.md](../../agents/prompts/passo-04-github-actions-to-pubsub.md) — GitHub Actions workflow
- [agents/prompts/passo-05-pubsub-ingestion-consumer.md](../../agents/prompts/passo-05-pubsub-ingestion-consumer.md) — Consumer Pub/Sub
- [agents/prompts/passo-06-github-content-client.md](../../agents/prompts/passo-06-github-content-client.md) — GitHub Content Client
- [agents/prompts/passo-07-incremental-ingestion-handler.md](../../agents/prompts/passo-07-incremental-ingestion-handler.md) — Incremental Ingestion Handler
- [agents/prompts/passo-03-git-repository-client.md](../../agents/prompts/passo-03-git-repository-client.md) — Prompt original (SUPERSEDED)
