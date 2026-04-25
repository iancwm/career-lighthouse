# Code Smell Cleanup Specs

This folder contains the sprint specs for the repo-wide cleanup pass.

## Sprint Status

| Sprint | Status | Focus |
|---|---|---|
| Sprint 1 — Frontend shell | ✓ Done (2026-04-24) | Admin workspace shell, student page shell, E2E fixtures |
| Sprint 2 — Backend shared utilities | proposed | Consolidate copy-paste helpers into `shared_yaml.py` |
| Sprint 3 — Router/service decomposition | follow-up | Split `kb_router.py`, extract `analyze_session`, models split |

See `implementation_plan.md` for the ordered work breakdown.

## Lane Specs

### Sprint 1 (done)
- `admin-workspace-shell.md` — ✓ `AdminWorkspace.tsx` split into shell + content + header + hook
- `student-page-shell.md` — ✓ `page.tsx` thinned; `useStudentPage.ts` extracted
- `admin-e2e-fixtures.md` — ✓ Playwright fixtures moved to `web/e2e/fixtures/`

### Sprint 2 (proposed)
Eight narrow backend consolidations — all safe swaps, no router or endpoint logic changed:

1. **S2-1** · `_atomic_yaml_write` → `shared_yaml.atomic_yaml_write` (5 callers)
2. **S2-2** · `_slug_is_safe` → `shared_yaml.safe_slug_is_valid` (4 callers)
3. **S2-3** · `_version_stamp` → `shared_yaml.version_stamp` (3 callers)
4. **S2-4** · `_safe_int`/`_safe_float` → `shared_yaml` coercion helpers (3 files)
5. **S2-5** · Delete duplicate `_normalize_profile_payload` from `alumni_router.py`
6. **S2-6** · Move `_latest_query_hits` to module-level in `source_ledger.py`
7. **S2-7** · Remove `sys.path` surgery from `scripts/validate_profiles.py`
8. **S2-8** · Consolidate `_fact_payload`/`_fact_lifecycle` into `fact_store.py`

Detailed specs in `validate-profiles-cli.md` and `implementation_plan.md`.

### Sprint 3 (follow-up)
Larger structural refactors — each should be a separate PR after Sprint 2 ships:
- `api-models-split.md` — split `models.py` (634 lines, 57 classes) by domain
- `terraform-module-split.md` — low priority; `main.tf` is only 156 lines today
- `kb_router.py` sub-split (CS-07) — extract `trace_router.py`, `employer_router.py`, `track_router.py`
- `analyze_session` service extract (CS-09)
- Singleton base class (CS-03)
- LLM repair circuit-breaker (CS-13)
