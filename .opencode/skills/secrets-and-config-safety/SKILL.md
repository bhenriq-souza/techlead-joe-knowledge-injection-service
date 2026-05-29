---
name: secrets-and-config-safety
description: Use ONLY when work touches .env, .env.example, Pydantic Settings, database DSNs, GitHub tokens, Pub/Sub credentials, Ollama endpoints, deployment config, or secret-handling guidance.
---

# Secrets And Config Safety

Use this skill only when changing or reviewing configuration, secret handling, environment variables, or deployment-related settings.

## Covered Areas

- `.env` and `.env.example`
- Pydantic Settings in `src/knowledge_injector/config.py`
- PostgreSQL database DSNs, hosts, usernames, and passwords
- GitHub tokens and GitHub Actions authentication
- Pub/Sub project, topic, subscription, and credential configuration
- Ollama endpoints and embedding model configuration
- Docker, Compose, CI/CD, GitOps, and deployment-related config

## Secret Rules

- Never print, commit, or summarize real secrets.
- Never expose credential-bearing DSNs.
- Redact secrets in errors, logs, examples, and final summaries.
- Prefer placeholders such as `change-me`, `example-token`, `postgresql+psycopg://user:password@host:5432/dbname`, and `https://example.invalid`.
- Keep `.env.example` useful but non-sensitive.
- Keep actual `.env` values local and uncommitted.

## Command Safety

- Do not run secret-modifying commands unless explicitly requested.
- Do not run GCP write commands unless explicitly requested.
- Do not run Terraform write commands unless explicitly requested.
- Do not run Kubernetes write commands unless explicitly requested.
- Do not run ArgoCD write commands unless explicitly requested.

## Configuration Design

- Prefer environment-driven runtime config loaded by Pydantic Settings.
- Keep provider credentials in infrastructure/config layers, not domain models.
- Document required variables with safe examples and clear descriptions.
- Avoid default values that could accidentally target production resources.

## Validation

- Review diffs for accidental secrets before reporting completion.
- If config changes affect runtime behavior, run the smallest relevant validation command that does not expose secrets.
