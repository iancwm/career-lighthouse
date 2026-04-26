# Cleanup Sprint Implementation Plan

## Sprint 1 — Frontend Shell Cleanup ✓ Done (2026-04-24)

All three frontend lanes shipped in the `refactor: split admin shell and harden session auth` commit.

| Lane | Outcome |
|---|---|
| `admin-workspace-shell.md` | `AdminWorkspace.tsx` reduced to 42 lines; `AdminWorkspaceContent.tsx`, `AdminWorkspaceHeader.tsx`, and `useAdminWorkspace.ts` extracted |
| `student-page-shell.md` | `page.tsx` reduced to 64 lines; `useStudentPage.ts` extracted with all storage and flow logic |
| `admin-e2e-fixtures.md` | Fixtures moved to `web/e2e/fixtures/admin-workspace.fixtures.ts`; E2E spec imports from shared builders |

---

## Sprint 2 — Backend Shared Utility Consolidation ✓ Done (2026-04-25)

**Focus:** eliminate copy-paste across service files by consolidating to `shared_yaml.py` and a new coercion helper. Each item is a narrow, safe change — no router or endpoint logic is touched.

### Items

#### S2-1 · Consolidate `_atomic_yaml_write` (CS-01)
Five files (`employer_store.py`, `source_ledger.py`, `track_drafts.py`, `session_store.py`, and any new stores) reimplement write-to-`.tmp`-then-rename. `shared_yaml.py` already exports `atomic_yaml_write`. Replace all local copies with the shared import.

**Files:** `api/services/employer_store.py`, `source_ledger.py`, `track_drafts.py`, `session_store.py`
**Risk:** low — pure mechanical swap, no behavior change.

#### S2-2 · Consolidate `_slug_is_safe` (CS-04)
`kb_router.py`, `alumni_router.py`, `alumni_store.py`, and `track_drafts.py` each define their own slug allowlist. Add a single `safe_slug_is_valid(slug: str) -> bool` to `shared_yaml.py` and replace all copies.

**Files:** `api/routers/kb_router.py`, `alumni_router.py`, `api/services/alumni_store.py`, `track_drafts.py`
**Risk:** low — consolidation only; test all four call sites.

#### S2-3 · Consolidate `_version_stamp` (CS-05)
`employer_store.py`, `source_ledger.py`, and `track_drafts.py` each define `_version_stamp()`. `shared_yaml.py` already exports `version_stamp` (imported only in `alumni_store.py`). Delete the private copies and add the shared import.

**Files:** `api/services/employer_store.py`, `source_ledger.py`, `track_drafts.py`
**Risk:** low.

#### S2-4 · Centralize `_safe_int` / `_safe_float` type coercions (CS-10)
`kb_router.py` defines `_safe_int` and `_safe_float`; `alumni_store.py` and `fact_store.py` use inline `try/except` casts. Add `safe_int` and `safe_float` to `shared_yaml.py` (or a new `api/services/type_coerce.py`) and replace all ad-hoc casts.

**Files:** `api/routers/kb_router.py`, `api/services/alumni_store.py`, `fact_store.py`
**Risk:** low — pure utility consolidation.

#### S2-5 · Delete duplicate `_normalize_profile_payload` from alumni router (CS-06)
`alumni_router.py` has a router-layer normalizer that duplicates the fuller version in `alumni_store.py`. Delete the router copy; call the service version directly before passing data to the store.

**Files:** `api/routers/alumni_router.py`, `api/services/alumni_store.py`
**Risk:** low-medium — verify the router version wasn't stripping fields the service version keeps.

#### S2-6 · Move `_latest_query_hits` to module-level (CS-12)
`SourceLedgerStore._latest_query_hits` is a pure function with no `self` access. Move it to module level in `source_ledger.py` so it is testable without constructing the singleton.

**Files:** `api/services/source_ledger.py`
**Risk:** low.

#### S2-7 · Fix `validate_profiles.py` sys.path hack (RS-04)
Remove the `sys.path.insert(...)` in `scripts/validate_profiles.py`. Export a stable `profile_to_context_block` helper from `api/services/career_profiles.py` as a module-level import, and invoke the script via `python -m api.services.career_profiles` or a `pyproject.toml` console-script entry so it works without path surgery.

**Files:** `scripts/validate_profiles.py`, `api/services/career_profiles.py`
**Risk:** low — no user-facing change; verify exit codes and output are unchanged.

#### S2-8 · Consolidate `_fact_payload` / `_fact_lifecycle` helpers (CS-02)
`employer_store.py` and `fact_store.py` both define nearly identical helpers for extracting a fact's data dict and resolving its lifecycle enum. Canonical versions landed in `shared_yaml.py` (not `fact_store.py` — `fact_store.py` imports `_default_employers_dir` from `employer_store.py`, which would create a circular import). `employer_store.py` now imports `fact_payload` and `fact_lifecycle` from `shared_yaml`.

**Files:** `api/services/employer_store.py`, `api/services/shared_yaml.py`
**Risk:** low — same logic, different modules.

### Suggested Order

1. S2-3 (version_stamp) — simplest, already 90% done in `shared_yaml.py`
2. S2-1 (atomic_yaml_write) — same pattern, five files
3. S2-2 (slug_is_safe) — needs one new export to shared_yaml, then four replacements
4. S2-4 (safe_int/safe_float) — needs the export, then three call sites
5. S2-5 (normalize_profile_payload) — needs a quick diff before deleting
6. S2-6 (latest_query_hits) — one-file move
7. S2-8 (fact_payload/fact_lifecycle) — two-file change
8. S2-7 (validate_profiles) — separate from the service changes, do last

### Definition Of Done ✓ All criteria met

- `shared_yaml.py` is the single canonical home for slug safety, atomic writes, version stamps, coercion helpers, and fact dict helpers.
- No private `_atomic_yaml_write`, `_slug_is_safe`, or `_version_stamp` definitions remain outside `shared_yaml.py`.
- `alumni_router.py`'s duplicate normalizer is deleted.
- `_latest_query_hits` is a module-level function.
- `validate_profiles.py` runs without `sys.path` mutation (use `PYTHONPATH=api python scripts/validate_profiles.py`).
- 276 backend tests pass. No public API or CLI behavior changes.

---

## Sprint 3 — Router and Service Decomposition (follow-up)

These are the high-effort, high-value structural changes. Each should be a separate PR.

| Lane | Smell | Scope |
|---|---|---|
| `api-models-split.md` | RS-05: `api/models.py` is 634 lines / 57 classes | ✓ Split into `models_chat.py`, `models_kb.py`, `models_tracks.py`, `models_employers.py`; keep barrel for compat |
| `kb_router` sub-split | CS-07: `kb_router.py` is ~2,000 lines | Extract `trace_router.py`, `employer_router.py`, `track_router.py` as sub-routers |
| `trace_adapter` extract | CS-08: `_observation_to_trace_entries` is ~200 lines | Move to `services/trace_adapter.py` so it is independently testable |
| `analyze_session` extract | CS-09: 150-line endpoint mixes HTTP and business logic | Move core analysis logic to a service function; keep router thin |
| Singleton base class | CS-03: hand-rolled `__new__` in 7+ stores | Add `Singleton` base class or `@singleton` decorator to `shared_yaml.py` |
| LLM repair circuit-breaker | CS-13: no shared deadline across retry attempts | Add a deadline budget shared across all repair attempts in `llm.py` |
| `terraform-module-split.md` | RS-06: `main.tf` is only 156 lines now — lower priority | Defer until the infra surface grows or a resource replacement risk is acceptable |

Sprint 3 should not start until Sprint 2 is done — the shared utility consolidation makes it safer to touch the routers.

### Sprint 3 lane shipped

`api-models-split.md` is now implemented. The monolithic `api/models.py` barrel stays in place for compatibility, but the actual domain models now live in:

- `api/models_chat.py`
- `api/models_kb.py`
- `api/models_tracks.py`
- `api/models_employers.py`
- `api/models_session.py`

The migration also added `api/tests/test_model_split_imports.py` to catch accidental re-monolithing.
