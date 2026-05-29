---
name: python-uv-validation
description: Use when validating this uv-managed Python project, selecting test or lint commands, updating validation guidance, or explaining why full validation is unnecessary.
---

# Python UV Validation

Use this skill for validation decisions in this uv-managed Python project.

## Current Tooling

Use only validation commands that match the current project configuration:

```bash
uv sync
uv run pytest
uv run pytest --cov=src/knowledge_injector --cov-report=term-missing
uv run ruff check .
```

## Command Selection

- Run `uv sync` when dependency installation, lockfile state, or environment setup matters.
- Run `uv run pytest` for normal Python behavior changes.
- Run `uv run pytest --cov=src/knowledge_injector --cov-report=term-missing` when coverage is requested or when a broader verification pass is appropriate.
- Run `uv run ruff check .` for Python lint validation.
- Do not add `mypy` guidance unless mypy is intentionally added to the project.

## When Full Validation Is Not Required

- If only documentation or OpenCode skill files changed, application tests are not required.
- If validation is skipped because the change is docs-only or skill-only, state that clearly in the final summary.
- If a narrower test command is used, explain the scope.

## Safety

- Do not invent validation scripts that do not exist in the project.
- Do not add new tooling or configuration only to satisfy validation unless explicitly requested.
