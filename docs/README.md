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

- `docs/session_pipeline_stabilization/` - active session publishing
  stabilization sprint. Covers Staging Area create-state trust, live queue
  updates, malformed JSON hardening, richer workflow detail, SmartCanvas
  scroll reduction, and alumni-card reliability. Started 2026-05-05.

## Archived Specs And Plans

Completed or historical planning docs live under `docs/archived/`:

- `docs/archived/code_quality_sprint/` - archived structural cleanup sprint
  plan. Phase 0 and part of Phase 1 shipped; the remaining Phase 1, Phase 2,
  and Phase 3 follow-ups now live in `TODOS.md`.
- `docs/archived/code_quality_finish/SPRINT.md` - archived code-quality
  finish sprint. Verified on 2026-05-06 as a partial sprint: Phase 1 shipped
  and passed focused verification; the remaining accuracy artifact, alumni
  verification artifact, `llm.py` decomposition, and Langfuse eval-sync work
  remain in `TODOS.md`.
- `docs/archived/SPRINT-UX-WORKSPACE-CLARITY.md` - shipped counsellor
  workspace clarity sprint. The follow-up pass closed the remaining admin-tab
  loading-state sweep, sticky two-pane local context, and focused Vitest /
  Playwright verification on 2026-05-02.
- `docs/archived/SPRINT-LAUNCH-READINESS.md` - shipped launch-readiness sprint (security, reliability, KB performance, alumni follow-ups, quick wins). Residual follow-ups (B3 UX polish, E1 accuracy artifact, F3 manual verification) tracked in `TODOS.md`.
- `docs/archived/alumni_schema/SPRINT-ALUMNI-CARDS.md` - shipped card-native alumni integration sprint. Residual manual end-to-end verification tracked in `TODOS.md`.
- `docs/archived/langfuse_observability_sprint/` - shipped Langfuse observability sprint. Workflow summary/detail contracts and admin debugging surfaces landed on 2026-05-04; remaining eval-sync follow-up work is tracked in `TODOS.md` and the archived code-quality finish sprint notes.
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

The structural cleanup sprint has been archived to
`docs/archived/code_quality_sprint/`. The shipped slice covered Phase 0 plus
the `trace_adapter`, `kb_writer`, and `kb_ingestion_service` extractions.
Remaining work — the router split, the `services/llm.py` decomposition, and
the Langfuse eval-sync follow-up — is now tracked in `TODOS.md`.

## Navigation

Start here:

- `README.md` for the product and setup overview
- `DESIGN.md` for architecture and UI direction
- `TODOS.md` for the current backlog
- `docs/session_pipeline_stabilization/` for the active session publishing sprint
- `docs/archived/` for completed specs and historical context

## Adding New Docs

- Active specs and live working docs belong in the repo root or an active subfolder like `docs/code_quality_sprint/`
- Completed specs and planning docs should move into `docs/archived/`
- Update this index whenever a docs folder changes status
