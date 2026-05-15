# Prompt — Passo 3.2: GitHub Actions → Pub/Sub

> Use este prompt em uma sessão limpa de outro chat (Claude Code, Cursor, etc.) para implementar **apenas o Passo 3.2** do backlog de ingestão event-driven.
>
> Este passo é de **documentação e template** — cria o arquivo de exemplo do workflow GitHub Actions e documenta como configurá-lo. O arquivo final deve ser copiado para o repositório cliente pelo time responsável. Não modifica o `knowledge-injection-service`.

---

## Contexto desta tarefa (para você que está coordenando)

- Projeto: `knowledge-injector` (Python 3.12, uv).
- Plano-mestre: `docs/implementation-plan.md` — seção "Backlog — Event-driven Knowledge Ingestion", Passo 3.2.
- Decisão arquitetural: `docs/architecture/knowledge-ingestion-event-driven.md`.
- O workflow GitHub Actions vive no **repositório cliente** (ex.: `org/repo`) — não neste repositório.
- Este passo entrega um arquivo de template em `docs/examples/github-actions/knowledge-ingestion-trigger.yml` dentro do `knowledge-injection-service`, acompanhado de documentação no próprio arquivo.
- Objetivo: o time responsável pelo repositório cliente copia o template, ajusta os secrets e ativa o workflow.

---

## PROMPT (copie a partir daqui)

````markdown
Você é um engenheiro de software trabalhando no repositório `techlead-joe-knowledge-injection-service` (Python 3.12, gerenciado com uv). Sua tarefa é implementar **apenas o Passo 3.2** do backlog de ingestão event-driven: criar um **template de workflow GitHub Actions** para o repositório cliente, com documentação completa sobre como configurá-lo.

## Como se orientar antes de escrever código

Leia, nesta ordem:

1. `agents/SKILL.md` — contexto master do projeto, regras de arquitetura e convenções.
2. `docs/architecture/knowledge-ingestion-event-driven.md` — decisão arquitetural completa.
3. `docs/implementation-plan.md` — Passo 3.2 e contexto do backlog geral.
4. `agents/prompts/passo-03-event-driven-document-source-ingestion.md` — definição do `SourceIngestionEvent` (o workflow deve publicar JSON compatível com este modelo).

## Contexto da tarefa

O workflow GitHub Actions que dispara eventos de ingestão **não faz parte deste repositório**. Ele deve residir no **repositório cliente** — o repositório cujos documentos serão ingeridos (ex.: `org/homelab-infra`).

Este passo entrega:

1. **Template do workflow** em `docs/examples/github-actions/knowledge-ingestion-trigger.yml` — arquivo YAML pronto para copiar.
2. **Documentação inline** no próprio arquivo YAML — comentários explicando cada seção, quais secrets configurar, como adaptar o mapeamento branch → ambiente.

O template não executa nada neste repositório. Ele serve como referência oficial para times que integram seus repositórios ao knowledge injector.

## Tarefa

### A) Criar `docs/examples/github-actions/knowledge-ingestion-trigger.yml`

Criar o diretório `docs/examples/github-actions/` e o arquivo de template com documentação inline.

**Requisitos do workflow:**

**Trigger:**

```yaml
on:
  pull_request:
    types: [closed]
```

**Guard de merge:**

O job principal deve executar apenas se o PR foi efetivamente mergeado:

```yaml
if: github.event.pull_request.merged == true
```

**Informações a extrair do contexto do GitHub Actions:**

| Campo | Origem no GitHub Actions |
|-------|--------------------------|
| `repository_full_name` | `github.repository` |
| `target_branch` | `github.event.pull_request.base.ref` |
| `pull_request_number` | `github.event.pull_request.number` |
| `merge_commit_sha` | `github.event.pull_request.merge_commit_sha` |
| `base_sha` | `github.event.pull_request.base.sha` |
| `head_sha` | `github.event.pull_request.head.sha` |
| `delivery_id` | `github.run_id` concatenado com `github.run_attempt` |

**Campos fixos no evento:**

- `event_type`: `"pull_request_merged"` (literal)
- `provider`: `"github"` (literal)
- `project_id`: via secret `KI_PROJECT_ID`
- `service_id`: via secret `KI_SERVICE_ID`
- `source_id`: via secret `KI_SOURCE_ID`
- `environment`: derivado de `target_branch` — ver lógica abaixo

**Lógica de resolução de ambiente a partir da branch:**

```yaml
- name: Resolve environment
  id: resolve_env
  run: |
    BRANCH="${{ github.event.pull_request.base.ref }}"
    case "$BRANCH" in
      main)     echo "environment=prd" >> $GITHUB_OUTPUT ;;
      homolo)   echo "environment=hml" >> $GITHUB_OUTPUT ;;
      develop)  echo "environment=dev" >> $GITHUB_OUTPUT ;;
      *)        echo "environment=unknown" >> $GITHUB_OUTPUT ;;
    esac
```

Se o ambiente for `unknown`, o job deve **falhar com mensagem clara** (não publicar evento com ambiente inválido).

**Publicação no Pub/Sub:**

Usar `gcloud pubsub messages publish` via step de shell (mais portável que action de terceiro).

Autenticação via Workload Identity Federation (recomendado) com `google-github-actions/auth@v2`.

Secrets necessários:

| Secret | Descrição |
|--------|-----------|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Provider WIF (formato `projects/NUMBER/locations/global/workloadIdentityPools/POOL/providers/PROVIDER`) |
| `GCP_SERVICE_ACCOUNT` | Service account para WIF (ex.: `ki-publisher@PROJECT.iam.gserviceaccount.com`) |
| `GCP_PROJECT_ID` | Projeto GCP onde o Pub/Sub está |
| `PUBSUB_TOPIC_ID` | ID do tópico Pub/Sub (ex.: `knowledge-ingestion-events`) |
| `KI_PROJECT_ID` | ID do projeto no catálogo de conhecimento |
| `KI_SERVICE_ID` | ID do serviço no catálogo de conhecimento |
| `KI_SOURCE_ID` | ID da fonte documental no catálogo de conhecimento |

**Estrutura do JSON publicado** (compatível com `SourceIngestionEvent`):

```json
{
  "event_type": "pull_request_merged",
  "provider": "github",
  "repository_full_name": "<github.repository>",
  "project_id": "<KI_PROJECT_ID>",
  "service_id": "<KI_SERVICE_ID>",
  "source_id": "<KI_SOURCE_ID>",
  "environment": "<resolved_environment>",
  "target_branch": "<base.ref>",
  "pull_request_number": <number>,
  "merge_commit_sha": "<merge_commit_sha>",
  "base_sha": "<base.sha>",
  "head_sha": "<head.sha>",
  "delivery_id": "<github.run_id>-<github.run_attempt>"
}
```

**Documentação inline obrigatória no YAML:**

- No topo do arquivo: bloco de comentário explicando o propósito, onde o arquivo deve ser colocado, e que é um template gerado pelo `knowledge-injection-service`.
- Em cada secrets: comentário de uma linha explicando o que é e onde encontrar o valor.
- Na seção de mapeamento branch → ambiente: comentário explicando como adicionar novos mapeamentos.
- No step de publicação: comentário explicando que o tópico Pub/Sub é gerenciado pelo `techlead-joe-infra` (Terraform).

### B) Criar `docs/examples/github-actions/README.md`

Arquivo de documentação explicando:

- O que é o template e para quem é destinado.
- Pré-requisitos: Workload Identity Federation configurado, tópico Pub/Sub existente (gerenciado pelo `techlead-joe-infra`), secrets cadastrados no repositório cliente.
- Passo a passo para adotar o template:
  1. Copiar o arquivo para `.github/workflows/knowledge-ingestion-trigger.yml` no repositório cliente.
  2. Configurar os 7 secrets listados.
  3. Ajustar o mapeamento branch → ambiente se necessário.
  4. Abrir um PR de teste e verificar que o job executa e publica no Pub/Sub.
- Seção de troubleshooting: ambiente `unknown`, permissões WIF, rate limit do Pub/Sub.

## Constraints

- **Não implementar código Python.** Apenas YAML, Markdown e shell script inline (bash).
- **Não baixar arquivos do repositório.** O workflow não faz `actions/checkout`.
- **Não processar documentos.** Não gera chunks, não chama Ollama.
- **Não hardcodar IDs.** Todos os IDs devem vir de secrets.
- **JSON válido.** O payload publicado deve ser JSON válido e compatível com `SourceIngestionEvent`.
- **Ambientes inválidos devem falhar explicitamente.** Não publicar eventos com `environment=unknown`.
- **Usar WIF.** Service account key apenas como nota de fallback no README, não no workflow.
- **Comentários em inglês no YAML.** O YAML é para times externos; comentários em inglês são mais universais.
- **README em português.** Segue o padrão deste repositório.

## Validação

```bash
# 1. Verificar que o diretório e arquivos existem
ls docs/examples/github-actions/

# 2. Verificar sintaxe YAML
uv run python -c "
import yaml, pathlib
content = pathlib.Path('docs/examples/github-actions/knowledge-ingestion-trigger.yml').read_text()
doc = yaml.safe_load(content)
# 'on' vira True em pyyaml; verificar via texto
assert 'pull_request' in content
assert 'closed' in content
print('YAML válido')
"

# 3. Verificar guards obrigatórios
grep -q 'pull_request.merged == true' docs/examples/github-actions/knowledge-ingestion-trigger.yml && echo 'guard de merge presente' || echo 'ERRO: guard ausente'
grep -q 'environment=unknown' docs/examples/github-actions/knowledge-ingestion-trigger.yml && echo 'guard de ambiente presente' || echo 'ERRO: guard de ambiente ausente'
grep -q 'KI_SOURCE_ID' docs/examples/github-actions/knowledge-ingestion-trigger.yml && echo 'secret KI_SOURCE_ID referenciado' || echo 'ERRO: KI_SOURCE_ID ausente'
grep -q 'GCP_WORKLOAD_IDENTITY_PROVIDER' docs/examples/github-actions/knowledge-ingestion-trigger.yml && echo 'WIF referenciado' || echo 'ERRO: WIF ausente'

# 4. Verificar que README existe e tem seções mínimas
grep -q 'Pré-requisitos' docs/examples/github-actions/README.md && echo 'README tem pré-requisitos' || echo 'ERRO: seção pré-requisitos ausente'
grep -q 'Passo a passo' docs/examples/github-actions/README.md && echo 'README tem passo a passo' || echo 'ERRO: seção passo a passo ausente'
```

## Entregável final

- `docs/examples/github-actions/knowledge-ingestion-trigger.yml` — template completo com documentação inline.
- `docs/examples/github-actions/README.md` — guia de adoção para times.
- Validação passando.
- Uma resposta curta (até 5 linhas) descrevendo o que foi criado e como um time externo deve usá-lo.

Não implemente código Python, não avance para o Passo 3.3 (Pub/Sub Consumer).
````

---

## Notas para o coordenador (não enviar para o outro chat)

- O template YAML vai para `docs/examples/github-actions/` neste repositório — não é executado aqui, serve como referência oficial.
- Times que integram um repositório copiam o arquivo para `.github/workflows/` no próprio repositório.
- O tópico Pub/Sub é criado pelo Terraform no `techlead-joe-infra` (ver `agents/prompts/passo-04b-terraform-pubsub-infra.md`).
- A action `google-github-actions/auth@v2` + `gcloud pubsub messages publish` é preferível à action `google-github-actions/publish-pubsub-message` (mais dependência de terceiro; gcloud já está disponível no runner ubuntu-latest).
- O campo `delivery_id` pode ser `${{ github.run_id }}-${{ github.run_attempt }}` — não é o delivery ID real do webhook, mas é único o suficiente para rastreabilidade.
- Próximos passos paralelos: `agents/prompts/passo-04b-terraform-pubsub-infra.md` (infra) e `agents/prompts/passo-05-pubsub-ingestion-consumer.md` (consumer Python).
