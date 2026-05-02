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
- `docs/code_quality_sprint/` - active structural cleanup plan for routers,
  YAML write services, trace adapters, and `services/llm.py`
- `docs/alumni_schema/SPRINT-ALUMNI-CARDS.md` - card-native alumni integration sprint plan
- `docs/SPRINT-UX-WORKSPACE-CLARITY.md` - planned UX sprint for
  analysis visibility, Employer Fact Library save clarity, and screen economy

## Archived Specs And Plans

Completed or historical planning docs live under `docs/archived/`:

- `docs/archived/llm_hardening/` - completed LLM safety and hardening specs
- `docs/archived/counsellor_trust/` - completed counsellor-trust sprint specs and IA notes
- `docs/archived/student_chat_qdrant_ingestion/` - completed student chat insight epic and sprint specs
- `docs/archived/plans/` - dated planning docs from earlier sessions
- `docs/archived/code-quality-reviewer-prompt.md` - legacy code review guidance
- `docs/archived/implementer-prompt.md` - legacy implementation guidance
- `docs/archived/spec-reviewer-prompt.md` - legacy spec review guidance

## Cleanup Specs

Sprint status is tracked in `docs/code_quality_sprint/README.md`. The current
slice shipped Phase 0 plus the `trace_adapter` and `kb_writer` service
extractions. Remaining work is tracked in
`docs/code_quality_sprint/implementation_plan.md`.

## Navigation

Start here:

- `README.md` for the product and setup overview
- `DESIGN.md` for architecture and UI direction
- `TODOS.md` for the current backlog
- `docs/schema/` for active schema work
- `docs/code_quality_sprint/` for the active cleanup sprint specs
- `docs/archived/` for completed specs and historical context

## Adding New Docs

- Active specs and live working docs belong in the repo root or an active subfolder like `docs/schema/`
- Completed specs and planning docs should move into `docs/archived/`
- Update this index whenever a docs folder changes status
