# Prompt — Passo 3.2b: Infraestrutura Pub/Sub (Terraform)

> Use este prompt em uma sessão limpa de outro chat (Claude Code, Cursor, etc.) para implementar **apenas o Passo 3.2b** do backlog de ingestão event-driven.
>
> Este passo cria a infraestrutura GCP necessária para o pipeline de ingestão event-driven no repositório **`techlead-joe-infra`** (Terraform). Não modifica o `knowledge-injection-service`.

---

## Contexto desta tarefa (para você que está coordenando)

- Repositório alvo: `techlead-joe-infra` (Terraform, GCP).
- Plano-mestre: `docs/implementation-plan.md` do `knowledge-injection-service` — Passo 3.2 do backlog.
- Decisão arquitetural: `docs/architecture/knowledge-ingestion-event-driven.md` no `knowledge-injection-service`.
- Este passo cria os recursos GCP necessários para que:
  - GitHub Actions (repositórios clientes) publiquem eventos no Pub/Sub via Workload Identity Federation.
  - O worker Python (`knowledge-injector`) consuma os eventos da subscription.
- Objetivo: ter tópico, subscription, service accounts e permissões WIF prontos para uso.

---

## PROMPT (copie a partir daqui)

````markdown
Você é um engenheiro de infraestrutura trabalhando no repositório `techlead-joe-infra` (Terraform, GCP). Sua tarefa é criar os recursos GCP necessários para o pipeline de ingestão event-driven do `knowledge-injection-service`.

## Contexto da tarefa

O pipeline de ingestão funciona assim:

```text
GitHub PR mergeado (repositório cliente)
  → GitHub Actions publica evento JSON no Pub/Sub (via WIF)
  → Knowledge Ingestion Worker (GCP) consome evento da subscription
  → Worker processa ingestão incremental
```

Os recursos GCP necessários são:

1. **Tópico Pub/Sub** — onde eventos de ingestão são publicados.
2. **Subscription Pub/Sub** — onde o worker consome os eventos.
3. **Service Account do publisher** — usada pelo GitHub Actions (WIF) para publicar no tópico.
4. **Service Account do consumer** — usada pelo worker Python para consumir da subscription.
5. **Workload Identity Pool + Provider** — para que GitHub Actions autentique sem chaves SA (WIF).
6. **IAM Bindings** — publisher pode publicar no tópico; consumer pode consumir da subscription.

## Como se orientar antes de criar os recursos

Antes de escrever código Terraform:

1. Leia os arquivos existentes no repositório para entender as convenções adotadas: prefixos de nomes, módulos locais, variáveis, workspaces, backend.
2. Identifique como outros recursos Pub/Sub ou service accounts são gerenciados (se existirem).
3. Identifique o padrão de nomeação de recursos (ex.: `{project}-{service}-{resource}` ou similar).
4. Verifique se já existe um Workload Identity Pool configurado — se sim, apenas adicione um novo Provider nele.

## Tarefa

### A) Tópico e Subscription Pub/Sub

**Tópico:**

```hcl
resource "google_pubsub_topic" "knowledge_ingestion_events" {
  name    = "knowledge-ingestion-events"
  project = var.project_id

  message_retention_duration = "86600s"  # ~24h

  labels = {
    service     = "knowledge-injector"
    managed-by  = "terraform"
  }
}
```

**Subscription:**

```hcl
resource "google_pubsub_subscription" "knowledge_ingestion_events_sub" {
  name    = "knowledge-ingestion-events-sub"
  topic   = google_pubsub_topic.knowledge_ingestion_events.name
  project = var.project_id

  ack_deadline_seconds       = 60
  message_retention_duration = "604800s"  # 7 dias
  retain_acked_messages      = false

  expiration_policy {
    ttl = ""  # nunca expira
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  labels = {
    service    = "knowledge-injector"
    managed-by = "terraform"
  }
}
```

### B) Service Accounts

**Publisher** (usado pelo GitHub Actions via WIF):

```hcl
resource "google_service_account" "ki_publisher" {
  account_id   = "ki-publisher"
  display_name = "Knowledge Injector — Pub/Sub Publisher"
  project      = var.project_id
}
```

**Consumer** (usado pelo worker Python):

```hcl
resource "google_service_account" "ki_consumer" {
  account_id   = "ki-consumer"
  display_name = "Knowledge Injector — Pub/Sub Consumer"
  project      = var.project_id
}
```

### C) IAM Bindings

```hcl
# Publisher pode publicar no tópico
resource "google_pubsub_topic_iam_member" "ki_publisher_publish" {
  project = var.project_id
  topic   = google_pubsub_topic.knowledge_ingestion_events.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.ki_publisher.email}"
}

# Consumer pode consumir da subscription
resource "google_pubsub_subscription_iam_member" "ki_consumer_subscribe" {
  project      = var.project_id
  subscription = google_pubsub_subscription.knowledge_ingestion_events_sub.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.ki_consumer.email}"
}

# Consumer pode ver o tópico (necessário para ack)
resource "google_pubsub_topic_iam_member" "ki_consumer_viewer" {
  project = var.project_id
  topic   = google_pubsub_topic.knowledge_ingestion_events.name
  role    = "roles/pubsub.viewer"
  member  = "serviceAccount:${google_service_account.ki_consumer.email}"
}
```

### D) Workload Identity Federation

O objetivo é permitir que GitHub Actions de **múltiplos repositórios clientes** publiquem no tópico sem necessidade de chave de service account.

**Pool WIF** (criar apenas se não existir):

```hcl
resource "google_iam_workload_identity_pool" "github_actions" {
  workload_identity_pool_id = "github-actions"
  display_name              = "GitHub Actions"
  description               = "Pool para autenticação de GitHub Actions via WIF"
  project                   = var.project_id
}
```

**Provider WIF para GitHub:**

```hcl
resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_actions.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub OIDC"
  project                            = var.project_id

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.actor"            = "assertion.actor"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
  }

  # Restringir ao owner da organização — ajustar conforme necessário
  attribute_condition = "assertion.repository_owner == \"<GITHUB_ORG_OR_USER>\""
}
```

> **Importante:** substituir `<GITHUB_ORG_OR_USER>` pela organização ou usuário GitHub que possui os repositórios clientes. Isso impede que repositórios de outros owners usem o pool.

**Binding WIF → Service Account do publisher:**

```hcl
resource "google_service_account_iam_member" "ki_publisher_wif" {
  service_account_id = google_service_account.ki_publisher.name
  role               = "roles/iam.workloadIdentityUser"

  # Permite qualquer repositório da org autenticar como este SA
  # Para restringir a repositórios específicos, use:
  # "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_actions.name}/attribute.repository/ORG/REPO"
  member = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_actions.name}/attribute.repository_owner/<GITHUB_ORG_OR_USER>"
}
```

### E) Outputs úteis

```hcl
output "pubsub_topic_name" {
  value       = google_pubsub_topic.knowledge_ingestion_events.name
  description = "Nome do tópico Pub/Sub para eventos de ingestão"
}

output "pubsub_subscription_name" {
  value       = google_pubsub_subscription.knowledge_ingestion_events_sub.name
  description = "Nome da subscription para o worker consumir"
}

output "ki_publisher_sa_email" {
  value       = google_service_account.ki_publisher.email
  description = "Email do SA publisher — usar em GCP_SERVICE_ACCOUNT no GitHub Actions"
}

output "ki_consumer_sa_email" {
  value       = google_service_account.ki_consumer.email
  description = "Email do SA consumer — usar na configuração do worker"
}

output "wif_provider" {
  value       = google_iam_workload_identity_pool_provider.github.name
  description = "Provider WIF — usar em GCP_WORKLOAD_IDENTITY_PROVIDER no GitHub Actions"
}
```

## Constraints

- **Terraform HCL apenas.** Sem scripts shell, sem Python, sem `local-exec` desnecessário.
- **Seguir convenções existentes do repositório.** Prefixos de nomes, variáveis, estrutura de arquivos.
- **Sem hardcode de project IDs ou emails.** Usar `var.project_id` e referências a recursos.
- **Substituir `<GITHUB_ORG_OR_USER>`** pelo valor correto antes de aplicar.
- **Se o pool WIF já existir,** usar `data "google_iam_workload_identity_pool"` em vez de criar novo.
- **Não criar chaves de service account.** A autenticação do worker usa WIF ou metadata de VM/Cloud Run.
- **Labels obrigatórias:** `service = "knowledge-injector"` e `managed-by = "terraform"` em todos os recursos.

## Validação

```bash
# 1. Verificar que o plano Terraform não tem erros
terraform init
terraform plan

# 2. Verificar que os outputs estão definidos
terraform output -json | jq 'keys'
# esperado: ["ki_consumer_sa_email", "ki_publisher_sa_email", "pubsub_subscription_name", "pubsub_topic_name", "wif_provider"]

# 3. Após apply, verificar tópico via gcloud
gcloud pubsub topics list --project=<PROJECT_ID> --filter="name:knowledge-ingestion-events"

# 4. Verificar subscription
gcloud pubsub subscriptions list --project=<PROJECT_ID> --filter="name:knowledge-ingestion-events-sub"

# 5. Verificar WIF pool
gcloud iam workload-identity-pools list --location=global --project=<PROJECT_ID>
```

## Entregável final

- Arquivo(s) Terraform com todos os recursos acima (seguindo estrutura do `techlead-joe-infra`).
- `terraform plan` sem erros.
- Outputs documentados.
- Uma resposta curta (até 8 linhas) descrevendo o que foi criado, os valores dos outputs que devem ser usados como secrets no GitHub Actions, e como configurar o worker Python com o SA consumer.

Não avance para outros passos. Não modifique o `knowledge-injection-service`.
````

---

## Notas para o coordenador (não enviar para o outro chat)

- Os valores de saída do `terraform output` devem ser usados para configurar:
  - `wif_provider` → secret `GCP_WORKLOAD_IDENTITY_PROVIDER` nos repositórios clientes.
  - `ki_publisher_sa_email` → secret `GCP_SERVICE_ACCOUNT` nos repositórios clientes.
  - `pubsub_subscription_name` → variável `PUBSUB_SUBSCRIPTION_ID` no worker Python.
  - `ki_consumer_sa_email` → permissão do worker Python (Cloud Run / VM / Pod).
- Se o `techlead-joe-infra` usar workspaces por ambiente (`dev`, `hml`, `prd`), os nomes dos recursos devem incluir o sufixo de ambiente (ex.: `knowledge-ingestion-events-dev`).
- O `attribute_condition` no provider WIF deve ser ajustado para o owner correto da organização GitHub. Sem essa restrição, qualquer repositório GitHub poderia autenticar.
- Para restringir a repositórios específicos (não a org inteira), substituir o binding WIF por um por repositório.
- Próximo passo paralelo: `agents/prompts/passo-05-pubsub-ingestion-consumer.md` (consumer Python) pode ser iniciado assim que os nomes dos recursos forem decididos.
