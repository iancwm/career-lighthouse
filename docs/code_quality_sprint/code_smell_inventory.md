---
status: in_progress
created: 2026-04-27
last_updated: 2026-04-27
---

# Code Smell Inventory

Smells found while exploring the API surface for the cleanup sprint. Ranked
by severity (impact × frequency-of-edit). Each item links back to the source.

## Severity legend

- **🔴 Blocker** — actively producing bugs or near-miss bugs; cannot ship more
  features in the area without thrashing.
- **🟠 High** — significant duplication or coupling; PR conflicts and review
  cost are noticeably elevated.
- **🟡 Medium** — slows down navigation and onboarding; tolerable short-term.
- **⚪ Low** — cosmetic; defer.

---

## 🔴 Blocker smells

### B1. Triple-implemented "field-write pipeline"

The same load → snapshot → allowlist → merge → derive → atomic-write →
invalidate sequence exists in three places:

- [`commit_analysis` — kb_router.py:1704-1878](../../api/routers/kb_router.py#L1704-L1878) — handles profiles + employers, plus chunk upsert
- [`_apply_field_updates_to_profile` — session_router.py:229-280](../../api/routers/session_router.py#L229-L280)
- [`_apply_field_updates_to_employer` — session_router.py:283-325](../../api/routers/session_router.py#L283-L325)
- [`_apply_field_updates_to_alumni` — session_router.py:328-372](../../api/routers/session_router.py#L328-L372)

Each variant has slightly different error wrapping and different
cache-invalidation paths. `session_router` instantiates store singletons
inside a `try: ... except: pass` block ([session_router.py:275-279](../../api/routers/session_router.py#L275-L279))
to invalidate the cache, which silently swallows real failures.

**Fix:** lift to `services/kb_writer.py` with one entry point per domain
(`apply_profile_diff`, `apply_employer_diff`, `apply_alumni_diff`). Routers
become four-line dispatchers.

**Status:** fixed in this sprint slice. `api/services/kb_writer.py` now owns
the canonical write pipeline. `kb_router.commit_analysis` and the
`session_router` card-commit wrappers delegate to it.

### B2. `_call_with_trace` dual-emit error paths are copy-pasted

[`_call_with_trace` — llm.py:688-883](../../api/services/llm.py#L688-L883) is
~200 lines and contains three nearly identical blocks (HTTPException, generic
Exception, success) that each emit an LLM trace JSONL row, optionally update a
Langfuse observation, and schedule a flush. Any change to the trace shape
must be made in three places. The hand-rolled "if Langfuse is not None" guards
duplicate state machine transitions.

**Fix:** extract `services/llm_tracing.py` with a single `LLMTraceRecorder`
context manager that owns the started/ok/error transitions. The 200 lines of
`_call_with_trace` collapse to ~40.

### B3. Hardcoded prompt inside the router

[`auto_complete_profile` — kb_router.py:828-929](../../api/routers/kb_router.py#L828-L929)
embeds a full LLM system prompt as Python f-strings (lines 860-876, 869-876).
Every other LLM prompt in the system lives in `api/cfg/prompts.yaml` and is
loaded via `prompts_cfg["prompts"]`. This one drifts on its own clock.

**Fix:** move the prompt to `cfg/prompts.yaml`; have the endpoint call a new
`llm.auto_complete_profile()` helper.

---

## 🟠 High-severity smells

### H1. `kb_router.py` is 2,029 lines / 29 endpoints

[`kb_router.py`](../../api/routers/kb_router.py) covers seven distinct domains
(profiles, tracks, draft tracks, employers, facts, ingestion, observability).
Confirmed by grep: 29 `@router.*` decorators across the file. PR conflicts are
inevitable and code review is hard.

### H2. `services/llm.py` is 1,843 lines

Already detailed in `evaluation.md` § "What the conductor plan misses". This
is the single biggest module in the codebase ahead of `kb_router.py`.

### H3. Eight singletons re-implement the same `__new__` dance

Found via `grep` for `_instance =` inside `api/services/`:

- `session_store.py:67-75`
- `embedder.py:27-39`
- `career_profiles.py:187-193`
- `alumni_store.py:487-503`
- `track_guidance.py:55-62`
- `source_ledger.py` (singleton class)
- `track_drafts.py:215-225`
- `employer_store.py` (singleton class)

`track_drafts.py` is the only one with a thread `Lock`; the rest race on first
import in test fixtures. CS-03 from Sprint 3 already drafted a `Singleton`
base class — fold it in here.

**Status:** fixed in this sprint slice. `api/services/shared_yaml.py` now
provides `Singleton`, and all eight listed classes inherit from it.

### H4. SDK-shape adapters live inside the router

[kb_router.py:285-426](../../api/routers/kb_router.py#L285-L426) defines
`_coerce_mapping`, `_coerce_sequence`, `_get_value`, `_format_timestamp`,
`_estimate_input_chars`, `_estimate_output_chars`, `_truncate_preview`,
`_preview_input`, `_preview_output`. None of these are HTTP concerns; all of
them adapt third-party SDK objects (Anthropic responses, Langfuse
observations) to the API's response models. They are used **only** by
`_observation_to_trace_entries`, which itself is only used by the
`/llm-traces` endpoint.

**Fix:** new `api/utils/sdk_shapes.py` (small) and `api/services/trace_adapter.py`
(houses `_observation_to_trace_entries` and the Langfuse-specific reading
logic). The `/llm-traces` endpoint becomes a five-line caller.

**Status:** fixed in this sprint slice. SDK-shape helpers moved to
`api/utils/sdk_shapes.py`; trace adaptation moved to
`api/services/trace_adapter.py`.

### H5. Inline imports inside `session_router.py`

13 function-local imports across [session_router.py:74-569](../../api/routers/session_router.py#L74-L569).
Several reach into private names from other services
(`_default_profiles_dir`, `_default_employers_dir`, `_derive_structured_fields`,
`_normalize_profile_payload`). This pattern is what CLAUDE.md's "Import timing
and helper choice matter" learning was written about.

**Fix:** lift imports to module top; promote private functions used across
modules to public names.

---

## 🟡 Medium-severity smells

### M1. Three near-identical merge routines for chunked LLM extraction

- [`_merge_intents` — llm.py:1378-1408](../../api/services/llm.py#L1378-L1408)
- [`_merge_analysis_results` — llm.py:1411-1458](../../api/services/llm.py#L1411-L1458)
- [`_merge_track_drafts` — llm.py:1461-1489](../../api/services/llm.py#L1461-L1489)

All three iterate `results: list[dict]`, dedupe by some tuple key, and emit
one merged dict. They differ only in which keys are list-merged vs dict-merged
vs scalar-overwritten.

**Fix (deferred):** introduce a small `merge_chunked_extraction(results,
spec={...})` helper. Lower priority than B1/B2 because each variant has its
own test coverage today.

### M2. `_default_*_dir` resolution is duplicated per service

Each entity store (`career_profiles`, `employer_store`, `alumni_store`,
`track_drafts`, `source_ledger`, `session_store`) has its own
`_default_<name>_dir()` that walks `Path(__file__).resolve().parent.parent
/ "knowledge" / "<name>"` with a fallback for the Docker layout. Six copies
of the same path-discovery logic.

**Fix:** add `runtime_paths.knowledge_dir(name)` — one function that returns
the resolved knowledge subdirectory. Stores call it once.

**Status:** fixed in this sprint slice. `runtime_paths.knowledge_dir(name)` now
backs the default knowledge path helpers while compatibility wrappers remain.

### M3. KB writes and reads bypass `shared_yaml.atomic_yaml_write`

After Sprint 2 consolidated `atomic_yaml_write` into `shared_yaml`, several
new write sites still inline the temp-file dance:

- [kb_router.py:1309-1313](../../api/routers/kb_router.py#L1309-L1313) (create_employer)
- [kb_router.py:1377-1381](../../api/routers/kb_router.py#L1377-L1381) (update_employer)
- [kb_router.py:1818-1821](../../api/routers/kb_router.py#L1818-L1821) (commit_analysis profile write)
- [kb_router.py:1856-1859](../../api/routers/kb_router.py#L1856-L1859) (commit_analysis employer write)
- [kb_router.py:917-921](../../api/routers/kb_router.py#L917-L921) (auto_complete_profile)
- [session_router.py:265-269](../../api/routers/session_router.py#L265-L269)
- [session_router.py:310-314](../../api/routers/session_router.py#L310-L314)

These all become single calls to `atomic_yaml_write` once the kb_writer
service from B1 owns them.

**Status:** partially fixed. The `commit_analysis` and `session_router`
card-commit write paths now go through `kb_writer` and
`shared_yaml.atomic_yaml_write`. Employer create/update and profile
auto-complete writes are still pending.

### M4. `kb_router.py` has 5 inline `from cfg`/`from services` imports inside
endpoint bodies

[kb_router.py:743, 841-842, 849, 912, 1323, 1390](../../api/routers/kb_router.py).
Mostly leftover from incremental feature work. Same fix as H5.

### M5. `session_router._touch_session` instantiates a fresh `SessionStore()`

[session_router.py:387](../../api/routers/session_router.py#L387) calls
`SessionStore()` even though the surrounding endpoint already received a
`store: SessionStore = Depends(...)`. Works because the store is a singleton,
but obscures the dependency graph and breaks test injection.

### M6. `health_cache` thundering-herd is already-tracked tech debt

See [TODOS.md "health_cache thundering herd"](../../TODOS.md). Note in plan;
do not bundle.

---

## ⚪ Low-severity smells

### L1. Duplicate `_truncate_preview` definitions

One in [kb_router.py:382-389](../../api/routers/kb_router.py#L382-L389), one in
[llm.py:134-141](../../api/services/llm.py#L134-L141). Both 8-line
`text[:limit] + "…"` helpers. Move the kb_router copy to use llm's, or
extract to `utils/text.py`. Trivial; do as part of H4.

### L2. `_first_sentence` is unused outside `kb_router.py`

[kb_router.py:99-107](../../api/routers/kb_router.py#L99-L107) — fine to leave
co-located with its callers (`_build_profile_summary`,
`_build_employer_summary`). Move with those into the `kb_ingestion_service`.

### L3. `_build_profile_summary` / `_build_employer_summary` are prompt
construction, not router logic

Both build summary blocks for the `analyse` LLM call. They belong next to the
prompt template in `cfg/prompts.yaml` or beside `analyse_kb_input` in `llm.py`,
not in the router.

### L4. `_observation_to_trace_entries` recomputes `nested_observations` twice

[kb_router.py:434, 481](../../api/routers/kb_router.py#L434-L481). Cosmetic.

### L5. `commit_analysis` redefines `_MAX_CHUNKS = 10` and
`_MAX_CHUNK_TEXT = 4000` inside the function body

[kb_router.py:1720-1721](../../api/routers/kb_router.py#L1720-L1721). Should
move to `cfg/kb.yaml` alongside the other thresholds (already loaded as
`kb_cfg`).

---

## Out of scope

These are real issues but belong to different sprints:

- Frontend monoliths (`EmployerFactsTab.tsx` 1,551 lines, `SmartCanvas.tsx`
  877 lines, `AlumniFactsTab.tsx` 851 lines). Same shape of problem; needs its
  own sprint with a frontend-aware reviewer.
- The 1,615-line `tests/test_kb_router.py` will need to be sliced when the
  router splits — track as M-level item once the router split lands.
- The `terraform/main.tf` split (RS-06 in Sprint 3) — still 156 lines, still
  not worth it.
