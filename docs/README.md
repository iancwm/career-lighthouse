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

- `docs/unified_session_and_quality/SPRINT.md` - active unified sprint for
  session pipeline stabilization plus remaining backlog close-out artifacts.
  Covers create-state trust, JSON/workflow-debug reliability, SmartCanvas
  review loop usability, alumni-card reliability verification, and Langfuse
  eval-sync follow-up. Started 2026-05-06.
- `docs/unified_session_and_quality/reliability_scorecard.md` - compact closure
  artifact mapping each observable failure mode (JSON repair, alumni path,
  validation, append) to its TraceExplorerTab evidence location.
- `docs/sprint_cq_finish/E1_accuracy_report.md` - LLM extraction accuracy
  test methodology for `extract_facts_from_prose`; three real employer note
  inputs, ≥ 80% scoring rubric, and prompt-refinement guidance.
- `docs/sprint_cq_finish/F3_alumni_verification.md` - alumni card failure-mode
  verification record for all four modes (hallucinated slug, company-links
  discrepancy, slug collision, unknown-field rejection).
- `docs/sprint_cq_finish/langfuse_eval_sync.md` - operator guide for
  `scripts/sync_langfuse_eval_dataset.py`: when to run, prereqs, verification
  steps, and dataset schema.

## Archived Specs And Plans

Completed or historical planning docs live under `docs/archived/`:

- `docs/archived/code_quality_sprint/` - archived structural cleanup sprint
  plan. Phase 0 and part of Phase 1 shipped; the remaining Phase 1, Phase 2,
  and Phase 3 follow-ups now live in `TODOS.md`.
- `docs/archived/code_quality_finish/SPRINT.md` - archived code-quality
  finish sprint. Verified on 2026-05-06 with Phase 1 plus the `llm.py`
  decomposition shipped and focused verification recorded. Follow-up artifacts
  (E1 accuracy, F3 alumni verification, Langfuse eval-sync script/docs) landed
  after archival; remaining structural follow-up is tracked in `TODOS.md`.
- `docs/archived/session_pipeline_stabilization/SPRINT-2026-05-05.md` -
  archived standalone session pipeline stabilization spec, superseded by the
  unified sprint spec on 2026-05-06.
- `docs/archived/plans/2026-05-06-sprint-completion.md` - archived
  sprint-completion execution checklist, merged into the unified sprint spec
  on 2026-05-06.
- `docs/archived/SPRINT-UX-WORKSPACE-CLARITY.md` - shipped counsellor
  workspace clarity sprint. The follow-up pass closed the remaining admin-tab
  loading-state sweep, sticky two-pane local context, and focused Vitest /
  Playwright verification on 2026-05-02.
- `docs/archived/SPRINT-LAUNCH-READINESS.md` - shipped launch-readiness sprint (security, reliability, KB performance, alumni follow-ups, quick wins). Residual follow-ups (B3 UX polish, E1 accuracy artifact, F3 manual verification) tracked in `TODOS.md`.
- `docs/archived/alumni_schema/SPRINT-ALUMNI-CARDS.md` - shipped card-native alumni integration sprint. Residual manual end-to-end verification tracked in `TODOS.md`.
- `docs/archived/langfuse_observability_sprint/` - shipped Langfuse observability sprint. Workflow summary/detail contracts and admin debugging surfaces landed on 2026-05-04; eval-sync follow-up has since shipped via `scripts/sync_langfuse_eval_dataset.py` with operator docs in `docs/sprint_cq_finish/langfuse_eval_sync.md`.
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
the `trace_adapter`, `kb_writer`, `kb_ingestion_service`, and `llm.py`
decomposition extractions. Remaining work — primarily the router split — is now
tracked in `TODOS.md`.

## Navigation

Start here:

- `README.md` for the product and setup overview
- `DESIGN.md` for architecture and UI direction
- `TODOS.md` for the current backlog
- `docs/unified_session_and_quality/SPRINT.md` for the active unified sprint
- `docs/archived/` for completed specs and historical context

## Adding New Docs

- Active specs and live working docs belong in the repo root or an active subfolder like `docs/code_quality_sprint/`
- Completed specs and planning docs should move into `docs/archived/`
- Update this index whenever a docs folder changes status
