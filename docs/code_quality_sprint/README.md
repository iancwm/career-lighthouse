---
status: in_progress
owner: iancwm
created: 2026-04-27
supersedes: conductor/refactor-kb-router.md
relates_to: docs/archived/code_smell_cleanup/implementation_plan.md (Sprint 3)
---

# Code Quality Sprint — Updated Plan

This folder is the active home for the next round of structural cleanup. It
replaces the standalone `conductor/refactor-kb-router.md` plan and extends the
unfinished Sprint 3 lanes from `docs/archived/code_smell_cleanup/`.

## Current progress

Shipped on 2026-04-27:

- Phase 0 utilities and adapters:
  - `services.shared_yaml.Singleton` now owns the shared singleton pattern for
    the YAML-backed stores and embedder.
  - `runtime_paths.knowledge_dir(name)` now centralizes knowledge-directory
    resolution while keeping existing `_default_*` shims.
  - `utils.sdk_shapes` now owns SDK object coercion, timestamp formatting, and
    trace preview helpers.
- Phase 1 service extractions:
  - `services.trace_adapter` now owns Langfuse/JSONL trace adaptation for the
    `/api/kb/llm-traces` endpoint.
  - `services.kb_writer` now owns the duplicated profile, employer, alumni, and
    vector-chunk write pipeline used by `kb_router` and `session_router`.
  - `services.kb_ingestion_service` now owns diff-first KB analysis, research
    input extraction, KB retrieval, prompt summary assembly, and provenance
    filling for `/api/kb/analyse` plus the draft-track research helpers.
- QA follow-up:
  - Playwright QA found the student chat was preloading `/api/tracks`, which
    404s. `ChatInterface` now uses the existing `/api/tracks/active` backend
    route.

Verification for this slice:

- `cd api && uv run pytest -q` → `302 passed, 2 skipped`
- `cd api && uv run python -m compileall routers/kb_router.py services/kb_ingestion_service.py`
- Docker web rebuild passed with `docker compose up -d --build web`
- Playwright smoke covered all admin views, student chat entry, and mobile
  admin layout.

## Why a new plan

The conductor plan was scoped only to `api/routers/kb_router.py`. After
exploring the wider codebase, three things made an updated plan necessary:

1. **The same smell exists in two other files.** `services/llm.py` (1,843 lines)
   and `routers/session_router.py` (729 lines) carry the same "monolith mixing
   transport, business logic, and infrastructure" pattern. Splitting only
   `kb_router.py` leaves the worst offender (`llm.py`) untouched.
2. **Sprint 3 of the prior cleanup pass already drafted most of the same work.**
   Lanes for `kb_router` sub-split, `_observation_to_trace_entries` extraction,
   `analyze_session` extraction, a singleton base class, and the LLM repair
   circuit-breaker were all queued and never shipped. Dropping the conductor
   plan in without acknowledging Sprint 3 would silently re-litigate decisions
   that were already made.
3. **The conductor plan understates the duplication risk.** `commit-analysis`
   in `kb_router.py` and `_apply_field_updates_to_*` in `session_router.py`
   reimplement the same write-validate-snapshot-invalidate pipeline three times
   over (profile / employer / alumni). Splitting routers without first lifting
   that pipeline into a service just relocates the duplication.

## Index

- [`evaluation.md`](evaluation.md) — review of the conductor plan: what holds,
  what is wrong, what is missing.
- [`code_smell_inventory.md`](code_smell_inventory.md) — concrete smells found
  across the codebase, grouped by severity.
- [`implementation_plan.md`](implementation_plan.md) — ordered, PR-sized work
  breakdown with risk and verification notes.

## Scope guardrail

This is a **structural** cleanup pass. No endpoint contract changes, no schema
changes, no UI changes. Every PR must keep `api/tests/` green and the admin
dashboard functionally unchanged. If a PR needs a behaviour change to land,
spike it separately and bring it back as its own ticket.
