# Status: Tech Lead Joe

**Atualizado em:** 2026-05-28

### Visão geral

O Tech Lead Joe é uma plataforma de análise de incidentes com LLM local (Ollama), composta por dois repos ativos no workspace:

- `techlead-joe-infra` — documentação, decisões arquiteturais, prompts de agentes
- `techlead-joe-knowledge-injection-service` — serviço Python de ingestão de documentos para RAG

---

### Knowledge Injection Service

| Componente | Status |
|---|---|
| Migrations Alembic (0001 e 0002) | ✅ Aplicadas — schema `knowledge` + pgvector 768d |
| `domain/models.py` e `ports.py` | ✅ Implementados |
| `infrastructure/db/database.py` | ✅ Completo |
| `infrastructure/db/repositories.py` (4 repos) | ✅ Completo |
| `GitRepositoryClient` | ⚠️ SUPERSEDED — substituído pela abordagem event-driven |
| `ChunkingService` | 🚧 Stub |
| `OllamaEmbeddingsClient` | 🚧 Stub |
| `IngestionService` (orquestrador) | 🚧 Stub |

**Decisão arquitetural recente (2026-05-15):** o fluxo mudou de "clone/pull local" para **event-driven via GitHub PR → GitHub Actions → Pub/Sub → Worker**. O plano detalha 8 sub-passos (3.1 a 3.8), nenhum implementado ainda. Esforço restante estimado: ~9h.

Branch atual: `feat/repo-client` (limpo, sem pendências).

---

### CI/CD e GitOps (item 1.12)

**Status: Planejado, não iniciado.** Plano em 4 etapas sequenciais:

1. **Terraform WIF + Secrets** (homelab-infra) — adicionar `techlead-joe-*` ao allowlist OIDC e cadastrar secrets no GCP Secret Manager  
   _Base já existente em homelab-infra/homelab-gitops: WIF pool/provider GitHub OIDC, Artifact Registry `homelab-apps`, ESO operacional com ClusterSecretStore gcp-dev/prd. Esforço restante: apenas SA + secrets específicos do techlead-joe._
2. **Criar `techlead-joe-gitops`** — manifests Kubernetes + ExternalSecrets para o `knowledge-injection-service`
3. **ArgoCD AppProject + Application** (homelab-gitops) — apontando para `techlead-joe-gitops` no cluster ai-lab  
   _Scaffold `clusters/ai-lab` já existe em `homelab-gitops` (bootstrap/root, platform/external-secrets, platform/shared-config). Aguarda apenas K3s + ArgoCD bootstrap no host._
4. **Workflow CI** no repo da aplicação — chamando o workflow reutilizável do homelab  
   _Workflow reutilizável `docker-build-push.yaml` já implementado em `homelab-gitops/.github/workflows/`. Suporta `workflow_call` com inputs para app-name, environment, registry-url e gitops-repo. **Limitação:** manifest path está hardcoded para `clusters/homelab/workloads/{env}/manifests/{app-name}/deployment.yaml` — para ai-lab precisará de um parâmetro `gitops-cluster` ou path override._

Prompts de implementação por etapa já estão em `techlead-joe-infra/agents/prompts/`.

**Dependência bloqueante:** cluster ai-lab com k3s ativo + ArgoCD bootstrapped (item 1.9, também não iniciado).  
**Nota operacional:** Terraform cutover (`homelab-root` → `homelab-gitops`) ainda pendente de `terraform apply` em homelab-infra — não bloqueia o techlead-joe mas deve ser concluído antes de qualquer alteração no bootstrap do cluster homelab.

---

### Infraestrutura AI Lab (Ollama)

| Item | Status |
|---|---|
| Ollama em Docker Compose (admin laptop) | ✅ Operacional — `qwen2.5-coder:14b` + `bge-m3` |
| GPU enablement via NVIDIA Container Toolkit (Fase 1) | ✅ Fechado por DA-014 |
| Logs Ollama → Loki/Grafana via Alloy | ✅ Funcionando — dashboard "Ollama Server - AiLab" ativo |
| Métricas de host (CPU/RAM/GPU) | 🚧 Pendente — node_exporter, cAdvisor, DCGM Exporter |
| k3s no AI Lab + ArgoCD (Fase 2) | 🔴 Não iniciado — aguarda POC do Incident Analyzer validada |
| GPU enablement no k3s (NVIDIA Device Plugin) | 🔴 Não iniciado — aguarda estabilidade Fase 2 |

---

### Itens arquiteturais abertos (P0)

| Item | Status |
|---|---|
| RabbitMQ — onde rodar e topologia | 🔴 Aberto |
| Conectividade inter-cluster (timeout, auth, retry) | ⚠️ Parcialmente fechado — `LLM_BASE_URL` via ConfigMap definido, falta autenticação e observabilidade |
| Estratégia de backup SSD 2 (Postgres/Qdrant) | 🔴 Aberto |
| Contratos de evento e schema de incidente | 🔴 Não especificado |
| Policy engine (regras Jira/Slack, deduplicação) | 🔴 Não especificado |

---

### Próximo passo natural

O desbloqueador crítico do pipeline completo é o **Passo 3.1** do `knowledge-injection-service` (revisão de domínio para a arquitetura event-driven), em paralelo com a **Etapa 1 do CI/CD** (Terraform WIF no `homelab-infra`). Os prompts de implementação já estão escritos em `techlead-joe-infra/agents/prompts/`.
