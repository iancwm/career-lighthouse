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

- `docs/sprint_cq_finish/` - Code Quality Finish & Backlog Close-out sprint.
  Covers the three remaining "Now" backlog items (B3 SmartCanvas UX, E1
  accuracy testing, F3 alumni verification), Code Quality Phase 1 finish
  (P1-4 kb_health extract, P1-5 prompt externalization, P1-6 inline-import
  lift), Code Quality Phase 3 (P3-1 through P3-4 llm.py decomposition), and
  the Langfuse eval dataset sync follow-up. Started 2026-05-04.
- `docs/langfuse_observability_sprint/` - Langfuse observability sprint specs.
  Implementation shipped 2026-05-04 (PR #22). Design and engineering reference
  docs retained here for the follow-up eval-sync work.

## Archived Specs And Plans

Completed or historical planning docs live under `docs/archived/`:

- `docs/archived/code_quality_sprint/` - archived structural cleanup sprint
  plan. Phase 0 and part of Phase 1 shipped; the remaining Phase 1, Phase 2,
  and Phase 3 follow-ups now live in `TODOS.md`.
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

The structural cleanup sprint has been archived to
`docs/archived/code_quality_sprint/`. The shipped slice covered Phase 0 plus
the `trace_adapter`, `kb_writer`, and `kb_ingestion_service` extractions.
Remaining work — `kb_health` lift, prompt externalization, inline-import
cleanup, the router split, and the `services/llm.py` decomposition — is now
tracked in `TODOS.md`.

## Navigation

Start here:

- `README.md` for the product and setup overview
- `DESIGN.md` for architecture and UI direction
- `TODOS.md` for the current backlog
- `docs/langfuse_observability_sprint/` for the active Langfuse observability sprint
- `docs/archived/` for completed specs and historical context

## Adding New Docs

- Active specs and live working docs belong in the repo root or an active subfolder like `docs/code_quality_sprint/`
- Completed specs and planning docs should move into `docs/archived/`
- Update this index whenever a docs folder changes status
