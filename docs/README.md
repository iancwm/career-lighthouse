# Documentation Structure

This directory is the index for active specs, working notes, and archived planning material.

## Active Documentation

The repo root holds the active project docs:

- `README.md` - product and setup overview
- `DESIGN.md` - current design system and architecture rationale
- `TODOS.md` - active backlog, ordered by priority
- `CHANGELOG.md` - release notes and version history
- `AUDIT.md` - production readiness and security review

## Active Specs

These docs are still maintained against the codebase:

- `docs/schema/SCHEMA-FOUNDATION.md` - structured schema foundation for the knowledge base
- `docs/schema/SPRINT-SCHEMA-FOUNDATION.md` - current schema execution plan and remaining work
- `docs/schema/singapore_metadata.yaml` - supporting schema metadata sample
- `docs/schema/structured_metadata.yaml` - supporting structured metadata sample
- `docs/llm_hardening/llm_hardening.md` - LLM safety and hardening notes
- `docs/code_smell_cleanup/` - cleanup specs for the non-router/service code-smell sprint

## Archived Specs And Plans

Completed or historical planning docs live under `docs/archived/`:

- `docs/archived/counsellor_trust/` - completed counsellor-trust sprint specs and IA notes
- `docs/archived/student_chat_qdrant_ingestion/` - completed student chat insight epic and sprint specs
- `docs/archived/plans/` - dated planning docs from earlier sessions
- `docs/archived/code-quality-reviewer-prompt.md` - legacy code review guidance
- `docs/archived/implementer-prompt.md` - legacy implementation guidance
- `docs/archived/spec-reviewer-prompt.md` - legacy spec review guidance

## Cleanup Specs

Sprint status is tracked in `docs/code_smell_cleanup/README.md`. Sprint 3 items are next:

- `docs/code_smell_cleanup/api-models-split.md` — split `models.py` by domain
- `docs/code_smell_cleanup/terraform-module-split.md` — low-priority infra split
- `docs/code_smell_cleanup/` — `kb_router` sub-split, `analyze_session` extract, singleton base class

## Navigation

Start here:

- `README.md` for the product and setup overview
- `DESIGN.md` for architecture and UI direction
- `TODOS.md` for the current backlog
- `docs/schema/` for active schema work
- `docs/llm_hardening/` for active LLM safety work
- `docs/code_smell_cleanup/` for the cleanup sprint specs
- `docs/archived/` for completed specs and historical context

## Adding New Docs

- Active specs and live working docs belong in the repo root or an active subfolder like `docs/schema/` or `docs/llm_hardening/`
- Completed specs and planning docs should move into `docs/archived/`
- Update this index whenever a docs folder changes status
