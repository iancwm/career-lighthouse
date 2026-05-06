# Langfuse Observability Sprint: Engineering

Status: Implemented, with eval-dataset follow-up still open  
Last updated: 2026-05-04  
Source artifacts:
- `/home/iancwm/.gstack/projects/iancwm-career-lighthouse/iancwm-main-design-20260503-110743.md`
- `/home/iancwm/.gstack/projects/iancwm-career-lighthouse/iancwm-main-eng-review-test-plan-20260503-122400.md`
Implementation commit:
- `7efbd83 feat: implement langfuse observability sprint`

## Goal

Make one session-card analysis run debuggable end to end so a developer can answer:

- which prompt version ran
- what the model returned
- whether repair changed the payload
- whether the alumni path ran
- where a card was dropped
- whether a prompt or logic change made outcomes better or worse

## Delivery Snapshot

Delivered in the merged implementation:

- backend-owned workflow contracts in `api/models_kb.py` and `web/types/llm-observability.ts`
- `/api/kb/workflow-summaries` and `/api/kb/workflow-detail` in `api/routers/kb_router.py`
- `api/services/trace_adapter.py` as the assembly layer that combines Langfuse observations, JSONL fallback traces, and router-side session evidence
- prompt provenance capture in `api/services/llm.py`, including `prompt_name`, `prompt_source`, `prompt_label`, and `prompt_version`
- router-side workflow state in `api/routers/session_router.py`, including step timeline, `drop_point`, alumni-path metadata, validation/append summaries, and card counts
- queue + drilldown surfaces in `SessionInbox.tsx`, `SmartCanvas.tsx`, `TraceExplorerTab.tsx`, and `LLMObservabilityTab.tsx`

Still deferred from the original plan:

- repo-fixture sync into the Langfuse eval dataset
- dedicated dual eval suite automation and prompt-version score comparison
- broader `services/llm.py` decomposition, now tracked in `TODOS.md` and the archived code-quality finish sprint notes

## Scope

Primary wedge:

- `generate_session_intents`
- `generate_alumni_extraction`
- JSON repair subflows
- validation and append path into `session.intent_cards`
- admin summary and workflow-detail surfaces for those runs

Not in scope for this sprint:

- migrating every repo prompt into Langfuse
- building a full observability control room for every LLM path
- making Langfuse the only source of truth for debug UX

## Approved Decisions

1. Use a backend-owned workflow-detail contract.
2. Add a small prompt resolver seam in `api/services/llm.py`.
3. Use hybrid scoring:
   - cheap factual flags inline
   - workflow scores after completion
4. Split prompt-fetch policy by environment.
5. Define one canonical backend workflow-detail model.
6. Keep summary and workflow-detail contracts separate.
7. Maintain a dual-source eval corpus:
   - repo fixtures
   - mirrored Langfuse dataset
8. Run both eval suites on any prompt/workflow-affecting change.
9. Poll summary only; load workflow detail on demand.

## Target Files

- `api/services/llm.py`
- `api/services/trace_adapter.py`
- `api/routers/session_router.py`
- `api/routers/kb_router.py`
- `api/models_kb.py`
- `web/components/admin/TraceExplorerTab.tsx`
- `web/components/admin/LLMObservabilityTab.tsx`
- `web/components/admin/SessionInbox.tsx`
- `web/components/admin/SmartCanvas.tsx`
- shared frontend types module for workflow detail

## Architecture

### 1. Summary vs Workflow Detail

Keep two contracts:

- Summary contract for polling/list surfaces
  - cheap to assemble
  - stable for tables and widgets
  - no deep nested workflow structure
- Workflow-detail contract for drilldown
  - session-scoped or run-scoped
  - timeline and child-step detail
  - prompt provenance
  - repair and validation evidence
  - card counts and drop-point analysis

The UI must not reconstruct workflow logic from raw Langfuse objects directly.

### 2. Workflow Truth Assembly

Add one backend endpoint under `/api/kb/*` that returns a normalized workflow-detail object assembled from:

- Langfuse observations when available
- router/card metadata emitted during session analysis
- JSONL trace fallback when Langfuse detail is incomplete or unavailable

Summary endpoint remains the existing `/api/kb/llm-traces` path or its stable successor.

### 3. Prompt Resolver

Add a small resolver seam local to `api/services/llm.py` that returns:

- prompt text
- `prompt_name`
- `prompt_source`
- `prompt_label`
- `prompt_version`

Phase 1 behavior:

- repo prompts remain default unless explicitly enabled per flow
- card-extraction prompts are the first candidates for Langfuse-managed versions

Environment policy:

- staging/debug: fetch `latest`, disable cache
- production: fetch `production`, allow short TTL cache, optional repo fallback

Every run must record resolved prompt provenance.

### 4. Scoring Model

Inline factual metadata:

- `repair_applied`
- `card_count_raw`
- `card_count_repaired`
- `card_count_committed`
- alumni path invoked/skipped flags

Workflow-level scores after completion:

- `json_validity`
- `repair_invoked`
- `card_presence`
- `alumni_card_presence`
- `expected_domain_recall`
- `schema_rejection`
- optional `manual_debug_severity`

Scoring/post-processing failure must not fail session analysis.

## Data Model

### Summary Contract

The summary object should stay lean and support:

- run/session identifiers
- function or workflow name
- status
- timestamps/duration
- session linkage
- brief prompt provenance
- brief failure/drop-point summary

### Workflow-Detail Contract

The detail object should include:

- workflow identity
- session identity
- prompt provenance
- model metadata
- step timeline
- context-pack summary
- raw output summary
- repair summary
- parsed payload summary
- validation/append evidence
- card counts:
  - raw
  - repaired
  - committed
- alumni-heavy decision
- alumni extraction invoked/skipped result
- suspected `drop_point`
- scores
- limitation/fallback notes when only partial evidence exists

## Instrumentation Requirements

### `api/services/llm.py`

Extend run metadata to capture:

- `prompt_name`
- `prompt_source`
- `prompt_label`
- `prompt_version`
- `schema_name`
- `error_class`
- `domain_mix`
- `repair_applied`
- card counts where known

Add child observations or spans for:

- prompt selection/context assembly
- generation
- repair
- validation/checks where meaningful

### `api/routers/session_router.py`

Emit workflow metadata around:

- alumni-heavy detection
- alumni extraction invoked/skipped
- number of alumni cards built
- validation rejection
- append result into `session.intent_cards`
- explicit drop-point classification

### `api/services/trace_adapter.py`

Keep flattening for summaries, but do not use that flattened view as the only truth.

## Delivery Phases

### Phase 1: Workflow Evidence

- shipped:
  - richer metadata in the tracing path
  - workflow summary/detail endpoints
  - session-router drop-point and alumni-path metadata
  - session-scoped debug drilldown in the admin UI

### Phase 2: Scores and Regression Loop

- partially shipped:
  - workflow-level scores now attach in `api/services/trace_adapter.py`
- still open:
  - curated corpus of canonical cases
  - Langfuse dataset mirror
  - score comparison by prompt/version

### Phase 3: Prompt Promotion

- partially shipped:
  - prompt resolver seam and environment-sensitive label policy are live in `api/services/llm.py`
  - per-flow Langfuse prompt enablement exists for `generate_session_intents` and `generate_alumni_extraction`
- still open:
  - full prompt-management promotion as an operational workflow rather than just code support

## Test Strategy

Shipped coverage:

- `api/tests/test_llm_observability.py` covers structured trace logging, prompt provenance, Langfuse/JSONL fallback behavior, and workflow-detail assembly
- `web/components/admin/__tests__/TraceExplorerTab.test.tsx` covers summary loading plus detail drilldown
- `web/components/admin/__tests__/LLMObservabilityTab.test.tsx` covers the workflow watchlist embedded in the observability surface
- `web/components/admin/__tests__/SessionInbox.test.tsx`, `SmartCanvas.test.tsx`, and `AdminWorkspace.test.tsx` keep the queue and route wiring honest
- `web/e2e/admin-workspace.e2e.ts` remains the end-to-end guardrail for the admin workspace shell

Still open:

- dedicated dual eval suites for `session_intents` and `alumni_extraction`
- automated reruns whenever prompt text, resolver logic, workflow scoring, workflow-detail shaping, or session-card routing changes

## Performance Rules

- Poll summary surfaces only.
- Load workflow detail on click.
- Auto-refresh detail only while the selected workflow is active/in flight.
- Do not bind heavy Langfuse reads to the same polling cadence as summary tables.

## Risks

- Prompt-source drift if prompt resolution is done ad hoc at call sites
- Vendor-shaped UI if frontend consumes raw Langfuse structures directly
- Corpus drift between repo fixtures and Langfuse dataset
- Load spikes if heavy workflow detail is polled continuously

## Follow-ups

Tracked in `TODOS.md`:

- sync repo fixtures into the Langfuse eval dataset
- future prompt/eval workflow hardening as adoption grows
