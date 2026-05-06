# Sprint: Code Quality Finish & Backlog Close-out Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the remaining items in the sprint including codebase refactoring, accuracy testing, and Langfuse sync.

**Architecture:** Refactor `kb_router.py` and `llm.py` by extracting logic into specialized service modules. Implement automated testing and reporting for fact extraction. Sync fixtures to Langfuse.

**Tech Stack:** Python (FastAPI, Pytest), React (Next.js), Langfuse SDK.

**Progress (2026-05-06):**
- Block B was already shipped earlier on 2026-05-06 and archived in `docs/archived/code_quality_finish/SPRINT.md`; the Phase 1 checkboxes below are now historical only.
- Block C implementation is now in the working tree: `api/services/llm_tracing.py`, `api/services/llm_json.py`, and `api/services/llm_budgets.py` exist; `api/services/llm.py` now delegates to them; `MergeSpec` plus `merge_chunked_results(...)` consolidate the three chunk-merge paths; and `auto_complete_profile_fields(...)` now calls the shared structured-JSON gateway correctly.
- Focused verification passed in the repo `uv` environment:
  - `cd api && uv run python -m py_compile services/llm.py services/llm_budgets.py services/llm_json.py services/llm_tracing.py tests/test_llm_hardening.py`
  - `cd api && uv run pytest tests/test_llm_hardening.py tests/test_llm_observability.py tests/test_session_intents.py tests/test_kb_analyse.py -q` → `41 passed`
- Remaining unshipped work is still Block A (accuracy + alumni verification), Block D (Langfuse eval sync), and any commit/PR bookkeeping.

---

### Task 1: Block B - Code Quality Phase 1 Finish (B1, B2, B3)

**Files:**
- Create: `api/services/kb_health.py`
- Modify: `api/routers/kb_router.py`
- Modify: `api/routers/session_router.py`
- Modify: `api/services/llm.py`
- Modify: `api/cfg/prompts.yaml`
- Modify: `api/services/career_profiles.py`
- Modify: `api/services/employer_store.py`
- Modify: `api/services/alumni_store.py`

- [x] **Step 1: Extract `kb_health` logic (B1)**
    - Create `api/services/kb_health.py`.
    - Move `_compute_overlap_pairs`, `_read_query_log`, and health assembly from `kb_router.py`.
    - Update `kb_router.py` to use `kb_health.py`.
- [x] **Step 2: Move `auto_complete_profile` prompt (B2)**
    - Add `auto_complete_profile` to `api/cfg/prompts.yaml`.
    - Add `llm.auto_complete_profile_fields()` to `api/services/llm.py`.
    - Update `kb_router.py` to use the new helper.
- [x] **Step 3: Lift inline imports and promote names (B3)**
    - Rename underscored items in `career_profiles.py`, `employer_store.py`, `alumni_store.py`.
    - Move all inline imports in `kb_router.py` and `session_router.py` to the top.
- [x] **Step 4: Run tests**
    - Run: `pytest api/tests/test_kb_router.py api/tests/test_session_router.py`
- [x] **Step 5: Commit Block B**

### Task 2: Block C - Code Quality Phase 3 (C1, C2, C3, C4)

**Files:**
- Create: `api/services/llm_tracing.py`
- Create: `api/services/llm_json.py`
- Create: `api/services/llm_budgets.py`
- Modify: `api/services/llm.py`

- [x] **Step 1: Extract `llm_tracing.py` (C1)**
    - Implement `LLMTraceRecorder` and move tracing logic.
- [x] **Step 2: Extract `llm_json.py` (C2)**
    - Move JSON repair and structured call logic.
- [x] **Step 3: Extract `llm_budgets.py` (C3)**
    - Move budget and config reading logic.
- [x] **Step 4: Generalize merge routines (C4)**
    - Implement `MergeSpec` and `merge_chunked_results`.
    - Refactor existing merge functions to use it.
- [x] **Step 5: Run tests**
    - Run: `pytest api/tests/test_llm_observability.py api/tests/test_llm_hardening.py api/tests/test_session_intents.py api/tests/test_kb_analyse.py`
- [ ] **Step 6: Commit Block C**

### Task 3: Block A - Backlog Close-out (A2, A3)

**Files:**
- Create: `docs/archived/sprint_cq_finish/E1_accuracy_report.md`
- Modify: `api/services/llm.py` (if needed for accuracy)
- Modify: `api/tests/test_session_router.py`
- Modify: `api/tests/test_session_intents.py`

- [ ] **Step 1: LLM extraction accuracy testing (A2)**
    - Run extraction on real employer notes.
    - Score accuracy and write report.
- [ ] **Step 2: Alumni cards end-to-end verification (A3)**
    - Verify failure modes in `SmartCanvas.tsx`.
    - Add/confirm test coverage in `api/tests/`.
- [ ] **Step 3: Commit Block A**

### Task 4: Block D - Langfuse Eval Dataset Sync (D1)

**Files:**
- Create: `scripts/sync_langfuse_eval_dataset.py`
- Create: `docs/archived/sprint_cq_finish/langfuse_eval_sync.md`

- [ ] **Step 1: Implement sync script**
    - Read fixtures from `api/tests/fixtures/`.
    - Upsert to Langfuse using SDK.
- [ ] **Step 2: Add documentation**
- [ ] **Step 3: Verify and Commit Block D**
