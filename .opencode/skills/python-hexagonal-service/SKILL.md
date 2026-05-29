---
name: python-hexagonal-service
description: Use when changing Python 3.12 service code in src/knowledge_injector, especially domain models, ports, application services, infrastructure adapters, CLI commands, or dependency-injector wiring.
---

# Python Hexagonal Service

Use this skill when implementing or reviewing Python service changes in `src/knowledge_injector`.

## Architecture Rules

- Keep the domain layer framework-free: dataclasses, enums, value objects, and ABC ports only.
- Keep SQLAlchemy, Alembic, HTTP clients, Pub/Sub, GitHub clients, provider SDKs, Pydantic Settings, and other runtime configuration details out of `src/knowledge_injector/domain/`.
- Put provider and persistence details in infrastructure adapters.
- Keep application services responsible for orchestration across ports.
- Keep CLI commands thin: load configuration, bootstrap dependencies, call application services, and return process results.
- Prefer synchronous implementation unless an ADR or explicit user instruction changes the runtime model.
- Do not add speculative abstraction layers or backward-compatibility code without a concrete need.

## Implementation Guidance

- Model business concepts in the domain before wiring infrastructure.
- Define port contracts in the domain when an application service needs an external dependency.
- Implement adapters in `infrastructure/` and inject them through `containers.py`.
- Validate behavior through ports, application services, and focused tests rather than provider internals.
- Preserve idempotency: repeated processing of unchanged input must not create duplicate documents or chunks.
- Do not revive clone/pull local ingestion as the main production path.

## Validation

- When Python code changes, run `uv run pytest` unless the task is explicitly limited to a narrower test.
- When Python code changes, run `uv run ruff check .`.
- If only documentation or OpenCode skill files changed, application tests are not required.
