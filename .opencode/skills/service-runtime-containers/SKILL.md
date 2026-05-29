---
name: service-runtime-containers
description: Use when changing Dockerfile, docker-compose.yml, service packaging, runtime command, environment loading, local pgvector profile, or container execution guidance.
---

# Service Runtime Containers

Use this skill for Dockerfile, Docker Compose, packaging, and runtime behavior work.

## Runtime Model

- Preserve the single-run worker model as the default runtime command:

```bash
python -m knowledge_injector run-once
```

- Keep the container suitable for batch execution and future CronJob-style scheduling.
- Do not add Kubernetes manifests in this repository as part of container runtime work.
- Do not switch to a long-running service model unless explicitly requested.

## Dockerfile

- Keep the Python runtime aligned with Python 3.12.
- Preserve `uv`-based dependency installation unless the project intentionally changes package management.
- Keep production images free of dev-only dependencies unless explicitly needed.
- Keep service packaging aligned with `pyproject.toml` and `src/knowledge_injector`.

## Docker Compose

- Preserve `.env` loading through `env_file` for local development.
- Preserve the optional local pgvector profile for offline development.
- Keep external Ollama and production PostgreSQL assumptions explicit in comments or documentation.
- Do not hard-code real secrets, private DSNs, GitHub tokens, or cloud credentials.

## Configuration

- Keep runtime config environment-driven.
- Prefer safe placeholders and documented variables over committed local values.
- Never print secrets or credential-bearing DSNs in logs or summaries.

## Validation

- For Dockerfile or Compose changes, validate with the smallest relevant Docker command when practical.
- If only documentation or OpenCode skill files changed, container validation is not required.
