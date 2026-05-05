---
status: active
created: 2026-05-04
last_updated: 2026-05-04
---

# Sprint: Code Quality Finish & Backlog Close-out

**Duration:** ~1 week  
**Goal:** Clear all unblocked "Now" items from the backlog, complete Code Quality Phase 1 (which unblocks Phase 2), and run Code Quality Phase 3 in parallel. Ship the Langfuse eval dataset sync as a lightweight follow-up to the observability sprint.  
**Branch convention:** one PR per block; `api/pytest` and `web/npm test` green before merge.

**Progress snapshot (2026-05-04):**
- A1 is already shipped in the current `SmartCanvas.tsx` implementation, even though it was still carried into this sprint from `TODOS.md`.
- The Langfuse observability prerequisite for Block D is merged on `main` (`f318569` / `7efbd83`).
- Still open in the repo: A2, A3, Blocks B and C, and the actual D1 dataset-sync script.

**Blocks:**
- A — Backlog close-out (Now items: B3, E1, F3)
- B — Code Quality Phase 1 finish (P1-4, P1-5, P1-6)
- C — Code Quality Phase 3 (P3-1 through P3-4, parallel with B)
- D — Langfuse eval dataset sync (follow-up from observability sprint)

**Explicitly out of scope:**
- Code Quality Phase 2 (router split) — depends on Phase 1 landing; own sprint.
- Counsellor RBAC — blocked on broader auth/user model design.
- Basic multi-user edit protection — blocked on revision metadata shipping first.
- AlumniDetail career-trajectory fields — waiting on ≥3 counsellor sessions.
- Alumni tab SmartCanvas migration — waiting on ≥2 weeks counsellor usage.

---

## Block A — Backlog Close-out

### ~~A1 · SmartCanvas 409 silent success~~ ✓ Shipped before sprint start *(B3 UX polish)*

**Source:** TODOS.md "Next" block B3; carried from the launch-readiness sprint.

**What shipped:** `SmartCanvas.tsx` now treats `409` responses from commit, discard, and cancel flows as an idempotent reload path instead of a user-facing failure.

**Why it mattered:** Counsellors who refresh mid-review should not get a false error for a card that was already finished elsewhere.

**Files:**
- `web/components/admin/SmartCanvas.tsx`

**Status note:** No new code work remains for this item.

**Acceptance criteria now satisfied by code:**
- Repeated commit/discard/cancel of an already-finished card/session does not raise a false error toast.
- Genuine failures still surface as errors.

---

### A2 · LLM extraction accuracy testing *(E1 accuracy artifact)*

**Source:** TODOS.md "Now" block E1; carried from the launch-readiness sprint.

**What:** Run the fact extraction pipeline end-to-end on 3 real Stripe employer notes (or close substitutes already in `knowledge/`). Manually score field accuracy (target ≥ 80%). Refine the extraction prompt in `api/services/llm.py` if accuracy falls short. Write 3–5 sample facts through the FactEditor UI to validate the write path.

**Why:** Extraction accuracy is the gate before Phase 3 (querying structured facts in live chat context). Without this artifact, there is no evidence the pipeline is trustworthy.

**Files:**
- `api/services/llm.py` — `extract_facts_from_prose` prompt; adjust if needed.
- `docs/sprint_cq_finish/E1_accuracy_report.md` — short report recording score, prompt changes, and sample facts used.

**Acceptance criteria:**
- Report exists with field-by-field accuracy score for ≥ 3 test runs.
- If accuracy < 80%: at least one documented prompt iteration recorded in the report.
- 3–5 facts written manually via FactEditor confirmed present in the YAML.
- No regressions in `api/tests/` covering extraction.

---

### A3 · Alumni cards end-to-end verification *(F3 manual pass)*

**Source:** TODOS.md "Now" block F3; carried from the alumni cards sprint.

**What:** Verify (or add tests covering) the four failure modes from the alumni cards sprint:
1. Hallucinated `matched_slug` → downgraded to `is_update=false` + `matched_slug=None`.
2. Malformed `company_links` discrepancy → `company_links_attempted` vs `company_links_written` in commit response rendered correctly in SmartCanvas toast.
3. Slug collision for new alumni → appends local date before card creation.
4. Unknown LLM fields in alumni diff → rejected with clear error, no partial YAML write.

**Why:** Backend tests cover modes 1, 3, 4. Mode 2 is wired server-side but the UI rendering of the discrepancy has not been manually verified.

**Files:**
- `web/components/admin/SmartCanvas.tsx` — verify mode 2 toast renders `company_links_attempted` vs `company_links_written`.
- `api/tests/test_session_router.py` and `api/tests/test_session_intents.py` — add or confirm coverage for all four modes.

**Acceptance criteria:**
- All four modes either have a passing automated test or have been manually verified with a documented note in this sprint doc.
- Mode 2 UI path: toast visibly distinguishes attempted vs written count when they differ.

**Current repo state:** backend handling for modes 1, 3, and 4 is in place, and `SmartCanvas.tsx` already renders `company_links_warning` when the write count is lower than the attempted count. The remaining gap is the explicit verification artifact, not the server/client plumbing.

---

## Block B — Code Quality Phase 1 Finish

These three items close out Phase 1 so the router split (Phase 2) can land as its own sprint. Each is its own PR per `docs/archived/code_quality_sprint/implementation_plan.md`.

### B1 · Extract `services/kb_health.py` *(P1-4)*

**What:** Move `_compute_overlap_pairs`, `_read_query_log`, and the KB health assembly logic from `api/routers/kb_router.py` into a new `api/services/kb_health.py`. The `/api/kb/health` endpoint becomes a 5-line caller.

**Files:**
- `api/services/kb_health.py` (new)
- `api/routers/kb_router.py` — delete extracted bodies; import from `kb_health`

**Risk:** Low. Existing `kb_health` tests in `test_kb_router.py` cover the behaviour.

**Acceptance criteria:**
- `api/services/kb_health.py` exists and owns the health assembly logic.
- `api/pytest` green.
- No functional change to the `/api/kb/health` response.

---

### B2 · Move `auto_complete_profile` prompt to `cfg/prompts.yaml` *(P1-5)*

**What:** Add an `auto_complete_profile` key to `api/cfg/prompts.yaml`. Add an `llm.auto_complete_profile_fields(...)` helper in `api/services/llm.py` that mirrors the shape of `analyse_kb_input`. The `kb_router.py` endpoint becomes a router-thin caller.

**Files:**
- `api/cfg/prompts.yaml` — new `auto_complete_profile` entry
- `api/services/llm.py` — new `auto_complete_profile_fields(...)` helper
- `api/routers/kb_router.py` — replace inline prompt with the helper

**Risk:** Low. Single endpoint; isolated tests.

**Acceptance criteria:**
- Prompt text lives exclusively in `prompts.yaml`.
- `llm.auto_complete_profile_fields()` has at least one unit test.
- `api/pytest` green.

---

### B3 · Lift inline imports out of routers *(P1-6)*

**What:** Promote `_default_profiles_dir`, `_default_employers_dir`, `_derive_structured_fields`, `_normalize_profile_payload` to public names (drop leading underscore) in their home modules. Lift all inline `from cfg`/`from services` imports to module-level in `api/routers/session_router.py` and `api/routers/kb_router.py`.

**Files:**
- `api/routers/session_router.py`
- `api/routers/kb_router.py`
- `api/services/career_profiles.py`, `employer_store.py`, `alumni_store.py` — name promotions

**Risk:** Low-medium. Pure rename; no behavioural change. One-line underscore aliases can stay for one PR cycle.

**Acceptance criteria:**
- `api/pytest` green.
- `python -m compileall api` passes (no import cycles).
- No function-local `from services...` imports remain in either router.

---

## Block C — Code Quality Phase 3 (parallel with B)

These four items can be worked in parallel with Block B after P0-2 (already shipped). Each is its own PR.

### C1 · Extract `services/llm_tracing.py` *(P3-1)*

**What:** Introduce `LLMTraceRecorder` as a context manager that owns the started/ok/error state machine and the dual-emit (JSONL + Langfuse) behaviour. Move `_append_llm_trace`, `_langfuse_*` helpers, and `_call_with_trace` infrastructure from `api/services/llm.py` to `api/services/llm_tracing.py`. `_call_with_trace` collapses to ~40 lines calling the recorder.

**Files:**
- `api/services/llm_tracing.py` (new)
- `api/services/llm.py` — remove extracted bodies; import `LLMTraceRecorder`

**Risk:** Medium-high. Most-exercised path in the system. Requires careful verification.

**Acceptance criteria:**
- `tests/test_llm_observability.py` (655 lines) green.
- `tests/test_llm_hardening.py` green.
- Manual: one analyse + one chat turn in admin and student UIs; Langfuse session shows both with started + terminal entries.

---

### C2 · Extract `services/llm_json.py` *(P3-2)*

**What:** Move `_extract_json_block`, `_parse_json_payload`, `_json_dumps_safe`, `_repair_json_output`, `_validate_or_repair`, and `call_structured_json` from `api/services/llm.py` to `api/services/llm_json.py`. `llm.py` imports the public `call_structured_json`.

**Files:**
- `api/services/llm_json.py` (new)
- `api/services/llm.py` — remove extracted bodies; import from `llm_json`

**Risk:** Medium. JSON repair runs on every non-trivial LLM call.

**Acceptance criteria:**
- `tests/test_llm_hardening.py` green (covers repair paths).
- `api/pytest` green.

---

### C3 · Extract `services/llm_budgets.py` *(P3-3)*

**What:** Move `_trim_to_budget`, `_budget_chunks`, `_join_budgeted_sections`, `_budget_history`, the `_llm_setting`/`_llm_int`/`_llm_bool` config readers, and `_effective_session_multi_pass_setting` from `api/services/llm.py` to `api/services/llm_budgets.py`.

**Files:**
- `api/services/llm_budgets.py` (new)
- `api/services/llm.py` — remove extracted bodies; import from `llm_budgets`

**Risk:** Low. Pure functions.

**Acceptance criteria:**
- `api/pytest` green.

---

### C4 · Generalize merge routines *(P3-4)*

**What:** Introduce `merge_chunked_results(results, spec=MergeSpec(...))` in `api/services/llm.py` that accepts a declarative spec describing which fields are list-merged (with which dedupe key), dict-merged, or scalar-overwritten. Replace `_merge_intents`, `_merge_analysis_results`, and `_merge_track_drafts` with one-liners that delegate to the new function.

**Files:**
- `api/services/llm.py` — add `MergeSpec` dataclass and `merge_chunked_results()`; collapse the three merge functions

**Risk:** Low-medium. Each variant has its own tests today.

**Acceptance criteria:**
- `tests/test_session_intents.py` and `tests/test_kb_analyse.py` green.
- `api/pytest` green.
- `MergeSpec` and `merge_chunked_results` have dedicated unit tests.

---

## Block D — Langfuse Eval Dataset Sync

### D1 · Sync canonical card-debug fixtures into Langfuse eval dataset *(P2 follow-up)*

**Source:** TODOS.md "Next" block, priority P2. Follow-up from the Langfuse observability sprint that merged 2026-05-04.

**What:** Add a script or admin-safe workflow that syncs the canonical repo truth set for session-card debugging into the Langfuse dataset used for prompt and workflow evals. The initial implementation is a lightweight wedge: a script that reads fixtures from `api/tests/fixtures/` (or wherever the canonical cases live), formats them as Langfuse dataset items, and upserts them via the Langfuse SDK. A small CI check or README note establishes the cadence for keeping them in sync.

**Why:** The Langfuse sprint defined a dual-source eval corpus (repo fixtures + Langfuse dataset). Without a sync path, the two sources will drift as prompt or logic changes are made, making regression scores untrustworthy.

**Prerequisite status:** satisfied. The workflow-summary/detail implementation from the observability sprint is already merged; this block remains open because the sync script and operating note are not yet in the repo.

**Files:**
- `scripts/sync_langfuse_eval_dataset.py` (new) — reads canonical fixtures, upserts to Langfuse dataset
- `docs/sprint_cq_finish/langfuse_eval_sync.md` (optional) — brief note on how to run and when

**Estimate:** M (~4 h)

**Acceptance criteria:**
- Script runs without error against a local Langfuse instance (or skips gracefully if `LANGFUSE_*` env vars absent).
- At least 5 canonical session-card cases present in the target dataset after one run.
- Script is idempotent (re-running does not create duplicate entries).

---

## Definition of done for this sprint

- All four "Now" backlog items resolved (A1, A2, A3).
- `api/services/kb_health.py` exists; router endpoint is a thin caller (B1).
- `auto_complete_profile` prompt lives in `cfg/prompts.yaml` with a helper in `llm.py` (B2).
- No function-local `from services...` imports remain in `kb_router.py` or `session_router.py` (B3).
- `llm_tracing.py`, `llm_json.py`, and `llm_budgets.py` extracted; `llm.py` is under 1 000 lines (C1–C3).
- `merge_chunked_results` consolidates the three merge routines (C4).
- Langfuse eval sync script ships and runs idempotently (D1).
- `api/pytest` and `web/npm test` green at every merge.
- TODOS.md updated to mark completed items ✓ Done and point to this sprint doc.

## After this sprint

Phase 2 (router split, P2-1 + P2-2) is unblocked and can land as its own 1-day sprint. No other work in this sprint depends on it.
