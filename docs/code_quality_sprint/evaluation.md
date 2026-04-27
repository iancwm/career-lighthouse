---
status: draft
created: 2026-04-27
---

# Evaluation of `conductor/refactor-kb-router.md`

## Summary

The conductor plan correctly identifies that `api/routers/kb_router.py` is too
big and that several extractable units exist inside it. As a directional sketch
it holds up. As a sprint plan it is incomplete: it ignores half the duplication
problem, mis-files some helpers, and silently overlaps with already-drafted
Sprint 3 work that was never shipped.

The verdict, lane by lane:

| Conductor proposal | Verdict | Notes |
|---|---|---|
| Extract `services/llm_observability.py` from `_observation_to_trace_entries` etc. | **Keep, rename** | Sprint 3 already named this `services/trace_adapter.py` (CS-08). Use that name to avoid two parallel modules. Also: most callers in `kb_router.py` are `_coerce_*`, `_get_value`, `_format_timestamp`, `_estimate_*` — these are generic SDK shape helpers, not Langfuse-specific. They belong in a separate `utils/sdk_shapes.py`, not in the observability service. |
| Extract `services/kb_ingestion_service.py` for `analyse` and `commit_analysis` | **Keep, expand scope** | This is the highest-value extraction. But `commit_analysis` shares 80% of its body with `_apply_field_updates_to_profile` / `_apply_field_updates_to_employer` / `_apply_field_updates_to_alumni` in [session_router.py:229-372](../../api/routers/session_router.py#L229-L372). Extract a single `kb_writer` service that both routers call — otherwise you ship a refactor that immediately needs another refactor. |
| Extract `services/kb_health.py` for `_compute_overlap_pairs` and `kb_health` | **Keep** | Straightforward. Note the existing TODO at [kb_router.py:1919](../../api/routers/kb_router.py#L1919) about caching `list_docs()` — track separately, do not bundle. |
| Move `_coerce_mapping`, `_coerce_sequence`, `_get_value`, `_format_timestamp` to `services/shared_yaml.py` or `utils/converters.py` | **Reject as written** | These are SDK shape helpers (Langfuse / Anthropic response objects), not YAML helpers. Putting them in `shared_yaml.py` overloads its purpose. Create `api/utils/sdk_shapes.py`. The Sprint 2 retro explicitly called out keeping `shared_yaml` focused. |
| Split `kb_router.py` into 5 sub-routers (`profiles`, `tracks`, `employers`, `facts`, `kb_admin`) | **Keep, with prerequisites** | Right shape. But it must come *after* the service extraction, not before — splitting a router that still contains business logic just spreads the smell across five files. Sprint 3 already named these as `trace_router`, `employer_router`, `track_router`; we add `profile_router` and `facts_router` here. |
| Three-phase order: utilities → routers → services | **Reorder** | The plan's Phase 2 (router split) before Phase 3 (service extraction) is backwards. Routers should be split last, after the underlying services exist. See `implementation_plan.md`. |

## What the conductor plan misses

### 1. `services/llm.py` is a worse offender than `kb_router.py`

`llm.py` is 1,843 lines and combines:

- Anthropic client construction and retry policy ([llm.py:105-132](../../api/services/llm.py#L105-L132))
- Langfuse client lifecycle, PII masking, metadata serialization ([llm.py:143-332](../../api/services/llm.py#L143-L332))
- A 200-line tracing wrapper `_call_with_trace` ([llm.py:688-883](../../api/services/llm.py#L688-L883)) that emits two concurrent observability streams (JSONL + Langfuse) with hand-copied error paths
- JSON parsing, repair, and validation ([llm.py:357-582](../../api/services/llm.py#L357-L582))
- Prompt budgeting (`_trim_to_budget`, `_budget_chunks`, `_join_budgeted_sections`, `_budget_history`)
- Six top-level feature functions (`chat_with_context`, `analyse_kb_input`, `generate_track_draft`, `generate_brief`, `generate_alumni_extraction`, `generate_session_intents`)
- Three near-identical merge routines for chunked extractions (`_merge_intents`, `_merge_analysis_results`, `_merge_track_drafts`)

Refactoring `kb_router.py` while leaving `llm.py` as-is buys very little.
Sprint 3 of the prior plan acknowledged the `_observation_to_trace_entries`
piece (CS-08) but did not touch `llm.py` directly. This plan does.

### 2. The "field-write" pipeline is duplicated three ways

`commit_analysis` ([kb_router.py:1704-1878](../../api/routers/kb_router.py#L1704-L1878))
and the `_apply_field_updates_to_*` trio in
[session_router.py:229-372](../../api/routers/session_router.py#L229-L372)
both implement: *load YAML → snapshot history → validate against allowlist →
merge fields → derive structured fields → atomic write → invalidate store
cache*. Three copies, three slightly different error-handling shapes, three
opportunities for drift. Whichever feature gets a bug fix first will leave the
others stale (this exact failure mode was called out in CLAUDE.md's
"Implementation Learnings": *Schema drift breaks things quietly*).

### 3. The plan does not address inline imports inside router bodies

`session_router.py` has 13 function-local `from services...` imports, several
of which reach into private (underscore-prefixed) names like
`_default_profiles_dir`, `_derive_structured_fields`,
`_normalize_profile_payload`. CLAUDE.md flags this directly:

> Import timing and helper choice matter. Prefer top-level imports and the
> correct client/helper accessor when Python starts failing in surprising ways.

Refactoring without fixing this leaves the brittle layering in place.

### 4. Sprint 3 already proposed a singleton base class

Eight services (`session_store`, `embedder`, `career_profiles`, `alumni_store`,
`track_guidance`, `source_ledger`, `track_drafts`, `employer_store`) all
hand-roll the `_instance / __new__` singleton dance. The conductor plan does
not mention it; Sprint 3 (CS-03) did. We carry it forward.

### 5. The plan has no rollout / verification story

The conductor plan's "Verification & Testing" section says only "run existing
tests." For a 2,000-line refactor that touches 29 endpoints and is consumed by
the admin UI, that is too thin. We add explicit gates: per-PR test coverage,
endpoint contract assertion, and a manual admin-dashboard smoke list.

## What the conductor plan gets right

- The directional unbundling (logic → services, routes → routers) is correct.
- Calling out hardcoded prompts as a code smell is correct — they should move
  to `cfg/prompts.yaml`, which already exists and which `llm.py` already reads
  ([llm.py:54](../../api/services/llm.py#L54)). The
  `auto_complete_profile` prompt at
  [kb_router.py:860-876](../../api/routers/kb_router.py#L860-L876) is the
  obvious offender.
- The phasing instinct (small utilities first, structural changes second) is
  right; only the order of router-split vs service-extract is wrong.
