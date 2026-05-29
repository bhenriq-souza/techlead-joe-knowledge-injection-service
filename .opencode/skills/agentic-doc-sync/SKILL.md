---
name: agentic-doc-sync
description: Use when implementation or planning changes may require updates to project_status.md, README.md, docs/implementation-plan.md, docs/architecture/knowledge-ingestion-event-driven.md, AGENTS.md, or future specs.
---

# Agentic Doc Sync

Use this skill when a change may affect the project's operational documentation, implementation roadmap, architecture notes, or agent guidance.

## Authoritative Sources

- Treat `project_status.md` as the mandatory source of truth for current status, next steps, blockers, and active direction.
- Treat `docs/architecture/knowledge-ingestion-event-driven.md` as authoritative for the event-driven ingestion architecture.
- When documents disagree, prefer `project_status.md` and `docs/architecture/knowledge-ingestion-event-driven.md`.

## Files To Check

- `project_status.md`
- `README.md`
- `docs/implementation-plan.md`
- `docs/architecture/knowledge-ingestion-event-driven.md`
- future files under `specs/`
- `AGENTS.md`

## Known Drift

- `README.md` still contains clone/pull-centered wording.
- Parts of `docs/implementation-plan.md` still preserve clone/pull-centered MVP details for historical context.
- Do not treat stale clone/pull wording as current architecture when it conflicts with `project_status.md` or `docs/architecture/knowledge-ingestion-event-driven.md`.

## Sync Rules

- Update docs when code behavior, supported commands, runtime shape, database schema, event contracts, or active implementation status changes.
- Keep superseded guidance visibly marked instead of silently leaving conflicting instructions.
- Prefer small targeted documentation updates over broad rewrites.
- If documentation updates are outside the current task scope, report the drift clearly in the final summary.
- Do not create or update application code when the task is documentation-only.

## Validation

- For documentation-only and OpenCode skill-only changes, application tests are not required.
- Read changed documentation back when correctness depends on exact paths, frontmatter, or cross-references.
