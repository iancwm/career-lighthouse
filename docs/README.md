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

- `docs/code_quality_sprint/` - active structural cleanup plan for routers,
  YAML write services, trace adapters, and `services/llm.py`. Phase 0 plus
  the `trace_adapter`, `kb_writer`, and `kb_ingestion_service` extractions
  shipped 2026-04-27; Phase 1 remainder, Phase 2 router split, and Phase 3
  `services/llm.py` decomposition are still open.

## Archived Specs And Plans

Completed or historical planning docs live under `docs/archived/`:

- `docs/archived/SPRINT-UX-WORKSPACE-CLARITY.md` - shipped counsellor
  workspace clarity sprint. The follow-up pass closed the remaining admin-tab
  loading-state sweep, sticky two-pane local context, and focused Vitest /
  Playwright verification on 2026-05-02.
- `docs/archived/SPRINT-LAUNCH-READINESS.md` - shipped launch-readiness sprint (security, reliability, KB performance, alumni follow-ups, quick wins). Residual follow-ups (B3 UX polish, E1 accuracy artifact, F3 manual verification) tracked in `TODOS.md`.
- `docs/archived/alumni_schema/SPRINT-ALUMNI-CARDS.md` - shipped card-native alumni integration sprint. Residual manual end-to-end verification tracked in `TODOS.md`.
- `docs/archived/schema/` - completed structured schema foundation specs and metadata samples
- `docs/archived/code_smell_cleanup/` - completed Sprint 3 structural cleanup specs
- `docs/archived/llm_hardening/` - completed LLM safety and hardening specs
- `docs/archived/counsellor_trust/` - completed counsellor-trust sprint specs and IA notes
- `docs/archived/student_chat_qdrant_ingestion/` - completed student chat insight epic and sprint specs
- `docs/archived/plans/` - dated planning docs from earlier sessions
- `docs/archived/code-quality-reviewer-prompt.md` - legacy code review guidance
- `docs/archived/implementer-prompt.md` - legacy implementation guidance
- `docs/archived/spec-reviewer-prompt.md` - legacy spec review guidance

## Cleanup Specs

Sprint status is tracked in `docs/code_quality_sprint/README.md`. The current
slice shipped Phase 0 plus the `trace_adapter`, `kb_writer`, and
`kb_ingestion_service` service extractions. Remaining work — `kb_health` lift,
prompt externalization, inline-import cleanup, the router split, and the
`services/llm.py` decomposition — is tracked in
`docs/code_quality_sprint/implementation_plan.md`.

## Navigation

Start here:

- `README.md` for the product and setup overview
- `DESIGN.md` for architecture and UI direction
- `TODOS.md` for the current backlog
- `docs/code_quality_sprint/` for the active cleanup sprint specs
- `docs/archived/` for completed specs and historical context

## Adding New Docs

- Active specs and live working docs belong in the repo root or an active subfolder like `docs/code_quality_sprint/`
- Completed specs and planning docs should move into `docs/archived/`
- Update this index whenever a docs folder changes status
