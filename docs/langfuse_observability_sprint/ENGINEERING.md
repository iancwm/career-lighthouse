# Langfuse Observability Sprint: Engineering

Status: Approved, ready for implementation  
Last updated: 2026-05-03  
Source artifacts:
- `/home/iancwm/.gstack/projects/iancwm-career-lighthouse/iancwm-main-design-20260503-110743.md`
- `/home/iancwm/.gstack/projects/iancwm-career-lighthouse/iancwm-main-eng-review-test-plan-20260503-122400.md`

## Goal

Make one session-card analysis run debuggable end to end so a developer can answer:

- which prompt version ran
- what the model returned
- whether repair changed the payload
- whether the alumni path ran
- where a card was dropped
- whether a prompt or logic change made outcomes better or worse

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

- richer metadata in tracing path
- workflow-detail endpoint
- session-router drop-point metadata
- session-scoped debug drilldown in admin UI

### Phase 2: Scores and Regression Loop

- workflow-level scores
- curated corpus of 10 canonical cases
- Langfuse dataset mirror
- score comparison by prompt/version

### Phase 3: Prompt Promotion

- migrate `generate_session_intents` into Langfuse prompt management
- migrate `generate_alumni_extraction` into Langfuse prompt management
- use staging/production labels

## Test Strategy

Backend coverage to add:

- `api/tests/test_llm_observability.py`
  - prompt provenance fields
  - workflow-detail endpoint shape
  - JSONL fallback behavior
  - score attachment and failure isolation
- `api/tests/test_session_router.py`
  - alumni-heavy invoked/skipped metadata
  - committed-count metadata
  - drop-point classification
  - regression where alumni extraction ran but no alumni card survived
- `api/tests/test_session_intents.py`
  - prompt resolver behavior
  - staging vs production prompt policy
  - repo fallback semantics

Frontend coverage to add:

- `web/components/admin/__tests__/TraceExplorerTab.test.tsx`
  - workflow-detail rendering
  - partial-detail state
  - session-filtered drilldown
- `web/components/admin/__tests__/LLMObservabilityTab.test.tsx`
  - failed-workflow widgets
  - repair/card-presence summaries
  - open-detail interactions
- `web/components/admin/__tests__/SessionInbox.test.tsx`
  - renamed debug affordance
  - ready-to-review routing behavior
- `web/components/admin/__tests__/SmartCanvas.test.tsx`
  - auto-reveal on analysis completion
- `web/components/admin/__tests__/AdminWorkspace.test.tsx`
  - workflow-detail route wiring

E2E coverage to add:

- `web/e2e/admin-workspace.e2e.ts`
  - Staging Area -> Debug Workflow -> session-scoped detail
  - missing-card diagnosis happy path

Eval coverage to add:

- dual suites:
  - `session_intents`
  - `alumni_extraction`
- run both suites whenever prompt text, prompt resolver logic, workflow scoring, workflow-detail shaping, or session-card routing changes

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
