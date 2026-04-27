---
status: in_progress
created: 2026-04-27
last_updated: 2026-04-27
---

# Code Quality Sprint — Implementation Plan

This is the ordered work breakdown that supersedes
`conductor/refactor-kb-router.md`. Each item is a separate PR. The order is
chosen so that no PR depends on a not-yet-merged sibling.

## Guiding rules

- **No behaviour change.** Endpoint contracts, prompt content, and YAML write
  semantics are frozen for the duration of the sprint. Any required fix lands
  as its own ticket.
- **Tests stay green at every commit.** `cd api && pytest` must pass before
  PR is opened. Frontend `npm test` (web) is in scope only when the router
  split lands and the admin client needs path adjustments.
- **One concern per PR.** A PR that splits the router is not also allowed to
  rename a function or introduce a new helper.
- **Prefer `Edit` over `Write`** when moving code. Track moves with `git mv`
  where possible so blame is preserved.

## Phase ordering rationale

The conductor plan ordered things utilities → routers → services. That is
backwards. If you split the router first, the new sub-routers still contain
business logic — you've just spread the smell across five files and made the
service extraction harder to land. Correct order:

1. **Phase 0 — Utilities & adapters.** Lift the obvious helpers. Zero risk.
2. **Phase 1 — Service extractions.** Pull business logic out of the router
   bodies into named services. Routers shrink in place.
3. **Phase 2 — Router split.** Now that routers are thin, splitting them is
   a mechanical move.
4. **Phase 3 — `services/llm.py` decomposition.** Independent of Phase 0–2;
   can run in parallel after Phase 0.

## Phase 0 — Utilities & Adapters

### P0-1 · Add `Singleton` mixin to `services/shared_yaml.py` (CS-03) — Done

**Files:** `api/services/shared_yaml.py` plus the eight singleton classes
listed in `code_smell_inventory.md` § H3.

**Change:** add a `Singleton` mixin (or `@singleton` class decorator) and
replace the 8 hand-rolled `_instance` / `__new__` blocks. Keep behaviour
identical (lazy first-access load, `invalidate()` keeps state).

**Risk:** low. Mixin replaces equivalent code. Test fixtures that monkeypatch
`_instance` keep working unchanged.

**Verify:** existing 276 backend tests, plus add a one-test file
`tests/test_singleton_mixin.py` that proves a single instance across
constructors.

**Shipped:** `api/services/shared_yaml.py` now exposes `Singleton`, and the
eight service singletons listed in H3 inherit from it. Added
`api/tests/test_singleton_mixin.py`.

---

### P0-2 · Create `api/utils/sdk_shapes.py` — Done

**Files:** `api/utils/sdk_shapes.py` (new), `api/routers/kb_router.py` (delete
helpers).

**Change:** move `_coerce_mapping`, `_coerce_sequence`, `_get_value`,
`_format_timestamp`, `_estimate_input_chars`, `_estimate_output_chars`,
`_truncate_preview`, `_preview_input`, `_preview_output` from `kb_router.py`
to `utils/sdk_shapes.py`. Update one importer.

**Risk:** low. These functions have no side effects.

**Verify:** unit tests for sdk_shapes. The existing
`tests/test_llm_observability.py` exercises the trace-shape paths.

**Shipped:** `api/utils/sdk_shapes.py` owns the SDK coercion and preview
helpers. Added `api/tests/test_sdk_shapes.py`.

---

### P0-3 · Promote `runtime_paths.knowledge_dir(name)` (M2) — Done

**Files:** `api/services/runtime_paths.py`, six service files.

**Change:** add `knowledge_dir(name)` to `runtime_paths.py`. Replace the six
`_default_<name>_dir()` walks with calls to it. Keep the `_default_…_dir`
shims as one-line wrappers for now (so callers and tests don't churn).

**Risk:** low. Pure refactor of path resolution.

**Verify:** existing tests; spot-check Docker bind-mount layout (CLAUDE.md
pre-flight item).

**Shipped:** `runtime_paths.knowledge_dir(name)` now backs the default
knowledge path helpers while the old `_default_*` wrappers remain in place.

---

## Phase 1 — Service Extractions

### P1-1 · Extract `services/trace_adapter.py` (CS-08, depends on P0-2) — Done

**Files:** `api/services/trace_adapter.py` (new), `api/routers/kb_router.py`.

**Change:** move `_observation_to_trace_entries`, `_read_langfuse_trace_log`,
`_read_llm_trace_log` from `kb_router.py` to `trace_adapter.py`. Router
keeps only the `@router.get("/llm-traces")` handler, which becomes a thin
wrapper around `trace_adapter.list_recent(limit, …)`.

**Risk:** low-medium. Touches one endpoint; covered by
`tests/test_llm_observability.py`.

**Verify:** that test file plus a manual check of the admin Trace Explorer
tab (no path changes; only the response should still be identical).

**Shipped:** `api/services/trace_adapter.py` now owns trace conversion and
trace-log reading. `kb_router.py` keeps compatibility wrappers for tests that
patch router-local settings.

---

### P1-2 · Extract `services/kb_writer.py` (B1) — Done

**Files:** `api/services/kb_writer.py` (new), `api/routers/kb_router.py`,
`api/routers/session_router.py`.

**Change:** introduce one service module with the canonical write pipeline:

```python
# api/services/kb_writer.py
def apply_profile_diff(slug, diff, *, snapshot=True, source=None) -> WriteResult: ...
def apply_employer_diff(slug, diff, *, snapshot=True, source=None) -> WriteResult: ...
def apply_alumni_diff(slug, diff, *, snapshot=True, source=None) -> WriteResult: ...
def upsert_kb_chunks(chunks, *, vector_store, embedder) -> ChunkUpsertResult: ...
```

Each function: validates slug, loads YAML, snapshots history (if applicable),
applies allowlist filter, calls `_derive_structured_fields`, writes via
`shared_yaml.atomic_yaml_write`, invalidates the relevant store cache.

`commit_analysis` ([kb_router.py:1704](../../api/routers/kb_router.py#L1704))
shrinks from 175 lines to ~30 (validation + dispatch). The
`_apply_field_updates_to_*` trio in
[session_router.py:229-372](../../api/routers/session_router.py#L229-L372)
becomes three two-line wrappers.

**Risk:** medium. Touches both routers' commit paths. This is the PR that
needs the most review attention.

**Verify:**
- `tests/test_kb_router.py` (1,615 lines — exhaustive)
- `tests/test_kb_analyse.py`
- `tests/test_session_router.py`
- `tests/test_alumni_router.py`
- Manual: counsellor commit-card and admin commit-analysis flows in the
  admin dashboard. Confirm history snapshots still appear.

**Shipped:** `api/services/kb_writer.py` now owns profile, employer, alumni,
and chunk writes. `commit_analysis` delegates to the service, and the
`_apply_field_updates_to_*` session wrappers are now thin compatibility
functions.

---

### P1-3 · Extract `services/kb_ingestion_service.py` — Done

**Files:** `api/services/kb_ingestion_service.py` (new),
`api/routers/kb_router.py`.

**Change:** move `analyse` business logic (text extraction, chunking,
KB search, prompt summary build, LLM call, validation) into the new service.
Router endpoint becomes ~15 lines: form parsing + dispatch + response
serialization. Move `_build_profile_summary`, `_build_employer_summary`,
`_first_sentence`, `_extract_generation_input`, `_retrieve_generation_chunks`,
`_merge_source_refs` here too.

**Risk:** medium. Same coverage as P1-2.

**Verify:** `tests/test_kb_analyse.py`, manual analyse → commit flow in admin.

**Shipped:** `api/services/kb_ingestion_service.py` now owns input extraction,
semantic retrieval, profile/employer summary assembly, `analyse_kb_input`
dispatch, Pydantic validation, and provenance/chunk-id filling. The
`/api/kb/analyse` endpoint is now a thin upload-size guard plus service call,
and draft-track generation endpoints use the same research-input helpers.

---

### P1-4 · Extract `services/kb_health.py`

**Files:** `api/services/kb_health.py` (new), `api/routers/kb_router.py`.

**Change:** move `_compute_overlap_pairs`, `_read_query_log`, the assembly
logic from the `kb_health` endpoint, into the new service. Endpoint becomes
a 5-line caller.

**Risk:** low.

**Verify:** existing `kb_health` tests in `test_kb_router.py`.

---

### P1-5 · Move `auto_complete_profile` prompt to `cfg/prompts.yaml` (B3)

**Files:** `api/cfg/prompts.yaml`, `api/services/llm.py`,
`api/routers/kb_router.py`.

**Change:** add an `auto_complete_profile` entry to `prompts.yaml`. Add an
`llm.auto_complete_profile_fields(...)` helper in `llm.py` that mirrors the
shape of `analyse_kb_input`. Endpoint in `kb_router.py` becomes a router-thin
caller.

**Risk:** low. Single endpoint; isolated tests.

**Verify:** add a unit test for the new prompt-loaded helper if one does not
already exist (none found in `test_kb_router.py`).

---

### P1-6 · Lift inline imports out of `session_router.py` and `kb_router.py` (H5, M4)

**Files:** `api/routers/session_router.py`, `api/routers/kb_router.py`,
plus the services whose private names are now used cross-module
(`career_profiles.py`, `employer_store.py`, `alumni_store.py`).

**Change:** promote `_default_profiles_dir`, `_default_employers_dir`,
`_derive_structured_fields`, `_normalize_profile_payload` to public names
(drop underscore). Lift all inline `from cfg`/`from services` imports to the
top of each router module.

**Risk:** low-medium. Public-name promotion is a rename; keep one-line
underscore aliases for one PR cycle if any external consumer (scripts/) uses
them — `scripts/validate_profiles.py` already imports
`profile_to_context_block` publicly so this should be fine.

**Verify:** `pytest`; `python -m compileall api` for import-cycle checks.

---

## Phase 2 — Router Split

Only run after Phase 1 lands. By this point `kb_router.py` should be ~600
lines of thin endpoint handlers.

### P2-1 · Split `kb_router.py` into 5 sub-routers

**Files:** `api/routers/profile_router.py`, `tracks_router.py`,
`employers_router.py`, `facts_router.py`, `kb_admin_router.py`,
`kb_router.py` (deleted), `api/main.py`, `api/routers/__init__.py`.

**Allocation:**
- `profile_router.py` — `/career-profiles*`, `/career-profiles/{slug}/auto-complete`
- `tracks_router.py` — `/tracks*`, `/draft-tracks*`, `/publish-journal`
- `employers_router.py` — `/employers*`, `/employers/{slug}/extract-facts`
- `facts_router.py` — `/facts*`
- `kb_admin_router.py` — `/analyse`, `/commit-analysis`, `/test-query`,
  `/health`, `/llm-traces`

All five share the `prefix="/api/kb"` and the
`Depends(require_admin_key)` router-level guard. Register all five in
`main.py`.

**Risk:** medium — touches every KB endpoint at the routing layer. URL paths
do not change; only Python module paths do.

**Verify:**
- `tests/test_kb_router.py` (parametrize the client to hit every endpoint)
- The web client at
  [`web/lib/api-proxy.ts`](../../web/lib/api-proxy.ts) does not need updates
  because URLs are unchanged
- Manual smoke: every admin tab loads without 404.

---

### P2-2 · Split `tests/test_kb_router.py` to mirror the new routers

**Files:** `api/tests/test_profile_router.py`,
`tests/test_tracks_router.py`, `tests/test_employers_router.py`,
`tests/test_facts_router.py`, `tests/test_kb_admin_router.py`,
`tests/test_kb_router.py` (deleted or thinned to integration smoke).

**Risk:** low. Pure test reorganization.

**Verify:** total test count unchanged; coverage report unchanged.

---

## Phase 3 — `services/llm.py` Decomposition

Can run in parallel with Phases 1–2 after P0-2 lands. Independently
reviewable.

### P3-1 · Extract `services/llm_tracing.py` (B2)

**Files:** `api/services/llm_tracing.py` (new), `api/services/llm.py`.

**Change:** introduce `class LLMTraceRecorder` as a context manager that owns
the started/ok/error state machine and the dual-emit (JSONL + Langfuse)
behaviour. Move `_append_llm_trace`, `_langfuse_*` helpers (except client
construction), `_call_with_trace` infrastructure into the new module.
`_call_with_trace` collapses to ~40 lines that call the recorder.

**Risk:** medium-high. This is the most-exercised path in the system.

**Verify:**
- `tests/test_llm_observability.py` (655 lines — exhaustive)
- `tests/test_llm_hardening.py`
- Manual: trigger one analyse + one chat turn in the admin and student UIs;
  confirm Langfuse session shows both, with started + terminal entries.

---

### P3-2 · Extract `services/llm_json.py`

**Files:** `api/services/llm_json.py` (new), `api/services/llm.py`.

**Change:** move `_extract_json_block`, `_parse_json_payload`,
`_json_dumps_safe`, `_repair_json_output`, `_validate_or_repair`,
`call_structured_json` to `llm_json.py`. `llm.py` imports the public
`call_structured_json`.

**Risk:** medium. JSON repair is exercised every time an LLM call returns a
non-trivial structure.

**Verify:** `tests/test_llm_hardening.py` covers the repair paths.

---

### P3-3 · Extract `services/llm_budgets.py`

**Files:** `api/services/llm_budgets.py` (new), `api/services/llm.py`.

**Change:** move `_trim_to_budget`, `_budget_chunks`,
`_join_budgeted_sections`, `_budget_history`, the `_llm_setting`/`_llm_int`/
`_llm_bool` config readers, and `_effective_session_multi_pass_setting` to
the new module.

**Risk:** low.

**Verify:** existing tests; the budgets are pure functions.

---

### P3-4 · Generalize the three merge routines (M1)

**Files:** `api/services/llm.py`.

**Change:** introduce `merge_chunked_results(results, spec=MergeSpec(...))`
that takes a small declarative spec (which fields are list-merged with which
dedupe key, which are dict-merged, which are scalar-overwritten).
`_merge_intents`, `_merge_analysis_results`, `_merge_track_drafts` become
one-liners.

**Risk:** low-medium. Each variant has its own test today.

**Verify:** `tests/test_session_intents.py`, `tests/test_kb_analyse.py`.

---

## Out of scope (deferred)

The following items were considered and explicitly deferred:

- **LLM repair circuit-breaker (CS-13).** Real concern (no shared deadline
  across retry attempts), but it is a behaviour change and the rest of this
  sprint is structural-only. Keep as a separate ticket once Phase 3 lands.
- **`list_docs()` 60s cache.** Tracked in TODOS.md.
- **`health_cache` thundering herd.** Tracked in TODOS.md.
- **Frontend monolith decomposition** (EmployerFactsTab, SmartCanvas, etc.).
  Different reviewer profile; own sprint.
- **`terraform/main.tf` split** (RS-06). Still under 200 lines.

## Definition of done

- `kb_router.py` is deleted; the five sub-routers each are < 400 lines.
- `services/llm.py` is < 800 lines; the four extracted modules
  (`llm_tracing`, `llm_json`, `llm_budgets`, `trace_adapter`) each are
  < 400 lines.
- The triple-implemented field-write pipeline collapses to one entry point
  per domain in `services/kb_writer.py`. No router-layer YAML writes remain
  in `kb_router.py` or `session_router.py`.
- All eight stores use the `Singleton` mixin from `shared_yaml.py`.
- No function-local `from services...` imports remain in any router.
- All current `api/tests/` pass with no test deletions (only test moves).
- Manual admin-dashboard smoke list (file under `tests/manual/admin_smoke.md`
  if not present, otherwise existing checklist) is verified.
