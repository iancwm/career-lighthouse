---
status: mostly_shipped
created: 2026-04-27
last_updated: 2026-05-02
---

# Sprint: Launch Readiness — Security, Reliability & Testing Infrastructure

**Duration:** ~1 week  
**Goal:** Close every unblocked "Now" item from TODOS.md, the highest-risk "Next" items, and ship the frontend test framework before broader counsellor rollout.  
**Branch convention:** one PR per block; all green against `api/pytest` and `web/npm test` before merge.

**Status (2026-05-02):** A1, A2, B1, B2, C1, C2, D1, F1, F2, G1, G2, G3, G4 shipped. Remaining open: B3 UX polish, E1 accuracy testing artifact, F3 manual end-to-end verification.

---

## Already shipped — removed from sprint scope

A git history audit (2026-04-27) found the following items already implemented. TODOS.md updated to match.

| Sprint item | Finding |
|---|---|
| **D1** — Frontend test framework | Vitest fully installed: `web/vitest.config.ts`, `web/package.json` `"test": "vitest"`, 24 test files across `admin/__tests__/` and `student/__tests__/`. Shipped as part of the alumni cards work (commit `6af0290`). |
| **A2** — Sanitize chat prompt injections | `sanitize_for_prompt()` applied to `career_context` and `employer_context` at `api/services/llm.py:957–958`. |
| **G2** — Model name env var override | `api/config.py:24` exposes `anthropic_model: str = ""` read from `ANTHROPIC_MODEL` env var. `api/services/llm.py:91–92` has `get_model_name()` that reads it first, falls back to `model.yaml`. |
| **B3** — Commit idempotency (data safety) | `commit_card()` at `session_router.py:523` checks `card.get("status") != "pending"` and returns HTTP 409 before any write. Prevents duplicate YAML writes. Minor UX polish (200 vs 409 on repeat) is still open. |
| **G1** — PDPA wording | `grep -r "anonymised"` finds no matches outside `TODOS.md` itself. The phrase was never written into active code or UI; item is stale. |
| **A1 scope reduction** — ADMIN_KEY | Backend already enforces `X-Admin-Key` header exclusively (`api/dependencies.py:12`). Remaining work is frontend-only: stop putting the key in the browser URL (`?key=...`). No backend change needed. |

---

---

## Open item inventory

Items drawn from TODOS.md (2026-04-27), the alumni cards sprint doc, and the code quality sprint plan. Blocked items are listed in **§ Deferred** below.

---

## Block A — Security Hardening

### ~~A1 · ADMIN_KEY: remove key from browser URL~~  ✓ Shipped

`web/middleware.ts` accepts `?key=...` once on first hit, validates against `ADMIN_KEY`, sets an HttpOnly session cookie, and redirects to the clean URL so the key is stripped from the address bar after the first navigation. `web/lib/admin-api.ts` no longer reads the URL — it relies on the cookie, and the proxy forwards it as `X-Admin-Key` server-side. `web/middleware.test.ts` covers the redirect-and-cookie-set path.

---

### ~~A2 · Sanitize chat prompt injections~~  ✓ Already shipped

`sanitize_for_prompt()` applied at `api/services/llm.py:957–958`. No work remaining.

---

## Block B — Reliability Guardrails

### ~~B1 · Qdrant timeout cap for student chat insights~~  ✓ Shipped

`api/routers/chat_router.py` now wraps `insight_store.index_message()` in a module-level `ThreadPoolExecutor` (`_INSIGHT_EXECUTOR`) and applies `future.result(timeout=_INSIGHT_WRITE_TIMEOUT_SECS)`. A slow Qdrant no longer blocks the chat response.

---

### ~~B2 · Session-analysis timeout — non-blocking response~~  ✓ Shipped

`api/routers/session_router.py` now uses `_SESSION_INTENTS_EXECUTOR` (a `ThreadPoolExecutor`) and `future.result(timeout=_deadline)` to bound the multi-pass analysis call. Long counsellor notes return inside the deadline instead of hitting a gateway timeout.

---

### B3 · Session card commit idempotency  *(data safety done; UX polish remains)*

`commit_card()` in `session_router.py` already checks `card.get("status") != "pending"` and returns HTTP 409 before any write — duplicate YAML writes cannot happen. SmartCanvas does observe 409 responses at multiple call sites, but the frontend should treat a 409 on a card that was previously committed as a silent success (not an error toast). That is a frontend-only change in the commit handler of `SmartCanvas.tsx`.  
**Estimate:** 1 h (frontend only)

---

## Block C — KB Performance

### ~~C1 · list_docs() scroll ceiling — TTL cache~~  ✓ Shipped

`api/routers/kb_router.py` now wraps `VectorStore.list_docs()` in a 60 s module-level TTL cache (`_docs_cache`, `_docs_cache_expires`, `_DOCS_CACHE_TTL`) protected by `_docs_cache_lock`. The cache is invalidated on every ingest via `health_cache.invalidate_overlap_cache`, and `_get_cached_docs(store)` is the single read entry point.

---

### ~~C2 · health_cache thundering herd — check-lock-check~~  ✓ Shipped

`api/services/health_cache.py` now uses a check-lock-check pattern with a `_computing` sentinel so only one thread runs the 5-second `_compute_overlap_pairs` scan; concurrent callers wait for the in-flight computation rather than triggering parallel scans.

---

## ~~Block D — Frontend Testing Infrastructure~~  ✓ Already shipped

Vitest is fully installed: `web/vitest.config.ts`, `"test": "vitest"` in `web/package.json`, `@testing-library/react` v16, `@testing-library/user-event`, and 24 test files already written across `web/components/admin/__tests__/` and `web/components/student/__tests__/`. Shipped with commit `6af0290` (alumni cards). No work remaining for this block.

---

## Block E — LLM Accuracy Gate

### E1 · Structured Facts Phase 2 — extraction accuracy testing  *(Now)*

**What:** Run the extraction endpoint end-to-end on 3 real Stripe employer notes. Score field accuracy manually (target ≥ 80%). Refine the extraction prompt in `api/services/llm.py` if accuracy falls short. Write 3–5 sample facts manually through the FactEditor UI to validate the write path.  
**Why:** The extraction endpoint is fully functional; accuracy is the gate before Phase 3 (querying structured facts in live chat context).  
**Files:** `api/services/llm.py` (extraction prompt), `api/routers/kb_router.py` (extract-facts endpoint).  
**Deliverable:** A short accuracy report (can be a code comment or a doc entry) recording the score and any prompt changes made.  
**Estimate:** 2–4 h (depends on prompt iteration)

---

## Block F — Alumni Cards Sprint: Remaining Checklist

Three items from `docs/alumni_schema/SPRINT-ALUMNI-CARDS.md` are still open. They belong in this sprint since the underlying code has shipped.

### ~~F1 · T3 eval cases in test_ai_eval.py~~  ✓ Shipped

`api/tests/test_ai_eval.py` now exercises the three required eval cases against `real_llm_client` using the alumni fixture corpus:
1. `test_career_trajectory_summary_populated` — full narrative populated.  
2. `test_is_update_and_matched_slug_for_existing_alumnus` — `is_update=true` and `matched_slug` matches.  
3. `source_excerpt` coverage paired with the same fixtures.

---

### ~~F2 · Commit response: company_links_attempted vs company_links_written~~  ✓ Shipped

`api/routers/session_router.py` now returns `company_links_attempted` and `company_links_written` from `_apply_field_updates_to_alumni`, and the commit response sets both keys on the response body when present (`session_router.py:598-599`). SmartCanvas can render the discrepancy from those fields.

---

### F3 · Four failure modes — end-to-end verification  *(Alumni sprint)*

Manually verify (or add tests for) all four failure modes from the alumni cards spec:

| # | Failure mode | Handling |
|---|---|---|
| 1 | Hallucinated `matched_slug` | Downgraded to `is_update=false` + `matched_slug=None` |
| 2 | Malformed `company_links` | Discrepancy reported in commit response (F2) |
| 3 | Slug collision for new alumni | Append local date before card creation |
| 4 | Unknown LLM fields in alumni diff | Rejected with clear error; no partial YAML write |

Unit tests for cases 1, 3, 4 should already exist or be added in this sprint.

---

## Block G — Quick Wins

### ~~G1 · PDPA wording~~  ✓ Stale — phrase never written into code

`grep -r "anonymised"` finds no matches in any active code or UI file. The item was written anticipating copy that was never added. No work needed; remove from TODOS.md.

---

### ~~G2 · Model name env var override~~  ✓ Already shipped

`api/config.py:24` exposes `anthropic_model: str = ""` (from `ANTHROPIC_MODEL` env var). `api/services/llm.py:91–92` has `get_model_name()` that reads it and falls back to `model.yaml`. No work remaining.

---

### ~~G3 · SessionInbox empty state copy~~  ✓ Shipped

`web/components/admin/SessionInbox.tsx` now renders a "No sessions yet" empty state with explanatory copy ("Paste your meeting notes or upload a document above to get started. The system will extract individual update cards…") instead of the bare prior wording.

---

### ~~G4 · Unsaved changes warning — KnowledgeUpdateTab~~  ✓ Shipped

`web/components/admin/KnowledgeUpdateTab.tsx` now installs a `beforeunload` listener while a diff is loaded and removes it after commit or discard.

---

## Code Quality Sprint — Remaining Phases

The code quality sprint (`docs/code_quality_sprint/implementation_plan.md`) still has Phases 1–3 items open. These are **not** in scope for this sprint (they are structural-only and carry their own reviewer profile), but they should follow immediately after:

| Item | Phase |
|------|-------|
| P1-4 · Extract `services/kb_health.py` | Phase 1 |
| P1-5 · Move `auto_complete_profile` prompt to `prompts.yaml` | Phase 1 |
| P1-6 · Lift inline imports out of routers | Phase 1 |
| P2-1 · Split `kb_router.py` into 5 sub-routers | Phase 2 |
| P2-2 · Split `test_kb_router.py` to mirror new routers | Phase 2 |
| P3-1 · Extract `services/llm_tracing.py` | Phase 3 |
| P3-2 · Extract `services/llm_json.py` | Phase 3 |
| P3-3 · Extract `services/llm_budgets.py` | Phase 3 |
| P3-4 · Generalize three merge routines | Phase 3 |

---

## Execution order

All blocks in this sprint were independent. Original recommended sequence (preserved for context — most are now ✓):

```
A1 (auth — breaking, needs co-ordination) ──────── first        ✓
A2 (sanitize)                             ──────── alongside A1 ✓
B1 (Qdrant timeout)                       ──────── quick win    ✓
B2 (session timeout)                      ──────── medium       ✓
B3 (commit idempotency)                   ──────── medium       ◐ data safety done; UX polish open
C1 + C2 (KB perf)                         ──────── self-contained ✓
D1 (vitest)                               ──────── do early     ✓
E1 (accuracy testing)                     ──────── time-boxed   ◯ open
F1–F3 (alumni checklist)                  ──────── close alumni F1 ✓ · F2 ✓ · F3 ◯
G1–G4 (quick wins)                        ──────── fill gaps    ✓
```

Remaining work to close the sprint: B3 UX polish in SmartCanvas, E1 extraction-accuracy artifact on Stripe notes, F3 manual end-to-end verification of the four alumni failure modes.

---

## Deferred (explicitly out of scope)

| TODOS.md item | Reason deferred |
|---|---|
| Counsellor RBAC | Needs broader auth/user model |
| Basic multi-user edit protection | Needs revision metadata on structured facts |
| Stale chunk deprecation on employer entity update | Complex; own focused sprint |
| Restore path for disabled employer entities | Own sprint alongside stale-chunk work |
| Path to multi-instance scaling | Infrastructure decision required first |
| Extend AlumniDetail (5 deferred fields) | Blocked on ≥ 3 real counsellor sessions |
| Migrate alumni tab + remove AlumniDetectionModal | Blocked on ≥ 2 weeks of usage |
| Fill in counselor_contact YAML fields | Data dependency (SMU career centre) |
| Re-ingest documents with improved chunking | Operational task; not a code change |
| Employer context token budget per-career-type | Blocked on career-type filtered injection |
| Missing Terraform production resources | Large infrastructure sprint; own track |
| Replace cosine career type switching | Deferred — no active regression |

---

## Definition of done

- [x] `cd web && npm test` passes — vitest installed and 24 tests passing (D1 done)
- [x] Career context and employer facts sanitized before LLM injection (A2 done)
- [x] `ANTHROPIC_MODEL` env var overrides model.yaml (G2 done)
- [x] Double-commit of a card cannot write YAML twice — 409 guard in place (B3 data safety done)
- [x] ADMIN_KEY no longer appears in browser URL bar or history — middleware redirects after first hit and sets HttpOnly cookie (A1 done)
- [x] Chat endpoint returns in < 1 s even when Qdrant is unresponsive — `_INSIGHT_EXECUTOR` + timeout (B1 done)
- [x] Session analysis returns a structured response before gateway timeout on long notes — `_SESSION_INTENTS_EXECUTOR` + deadline (B2 done)
- [x] `GET /api/kb/health` is served from cache within TTL — 60 s `_docs_cache` in `kb_router.py` (C1 done)
- [x] `_compute_overlap_pairs` executes at most once under concurrent requests — check-lock-check with `_computing` sentinel (C2 done)
- [x] 3 T3 eval cases pass in `test_ai_eval.py` (F1 done)
- [x] `company_links_attempted` vs `company_links_written` surfaced in commit response (F2 done)
- [x] SessionInbox empty state has helpful copy (G3 done)
- [x] `KnowledgeUpdateTab` has a `beforeunload` guard while a diff is loaded (G4 done)
- [ ] 409 on already-committed card is treated as silent success in SmartCanvas (B3 UX)
- [ ] Extraction accuracy ≥ 80% on 3 real Stripe notes, result documented (E1)
- [ ] All 4 alumni failure modes verified end-to-end (F3)
- [ ] `cd api && pytest` passes with no regressions after every PR
- [ ] CHANGELOG.md updated
