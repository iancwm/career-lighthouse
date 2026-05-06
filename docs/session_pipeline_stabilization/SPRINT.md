---
status: active
created: 2026-05-05
last_updated: 2026-05-05
---

# Sprint: Session Pipeline Stabilization

**Duration:** ~1 week  
**Goal:** Restore trust in the Staging Area publishing loop by making session creation feel immediate, tightening malformed-JSON recovery, exposing the missing workflow evidence in Langfuse/admin debug surfaces, removing unnecessary SmartCanvas scrolling, and closing the alumni-card reliability gap.  
**Branch convention:** one PR per block; `api/pytest` and `web/npm test` green before merge.

**Why this sprint exists:**
- `SessionInbox.tsx` currently shows `Creating…` with no immediate new row in `Analyzing now`, which makes the app feel frozen.
- Session analysis only auto-starts after opening the session in `SmartCanvas.tsx`, so queue state and analysis kickoff are coupled to the detail view.
- Malformed JSON is still occurring regularly in the session-card pipeline, but the current workflow detail does not surface enough repair/debug evidence to explain why the run degraded.
- `SmartCanvas.tsx` still forces too much vertical scrolling: the clustered-uncertainty banner is large and not dismissible, and the commit loop can require repeated scroll-down/scroll-up cycles.
- Alumni extraction still has reliability gaps, including real runs where alumni signals do not surface into actionable alumni cards.

**Blocks:**
- A — Session creation trust and live queue state
- B — JSON hardening and workflow-debug evidence
- C — SmartCanvas zero-scroll review loop
- D — Alumni extraction reliability

**Explicitly out of scope:**
- Remaining code-quality cleanup from `docs/archived/code_quality_finish/SPRINT.md`
- Alumni tab migration onto SmartCanvas
- Broad non-session observability work outside the session-card workflow
- New end-user product language experiments unrelated to these failures

---

## Block A — Session Creation Trust And Live Queue State

### A1 · Immediate `Analyzing now` row on session creation

**What:** As soon as `Create Session` succeeds, inject the newly created session into the `SessionInbox.tsx` local session list with a visible `analyzing`/`in-progress` state instead of waiting for the next poll.

**Why:** The current `Creating…` button state gives no durable confirmation that work has started. The user needs immediate proof that the note has entered the pipeline.

**Files:**
- `web/components/admin/SessionInbox.tsx`
- `web/components/admin/__tests__/SessionInbox.test.tsx`

**Acceptance criteria:**
- A newly created session appears in `Analyzing now` immediately after creation.
- The textarea clears only after the row is visible.
- The UI no longer relies on the 30-second poll cycle to show the newly created session.

---

### A2 · Kick off analysis from the creation path, not only from SmartCanvas

**What:** Move session-analysis kickoff out of the “open session detail” path. Either the create flow should trigger `/api/sessions/{id}/analyze` immediately, or the backend should expose a create-and-start path that returns a session already marked as running.

**Why:** Today the queue and backend work are decoupled in a misleading way: a session can be “created” without analysis actually starting until the detail view loads.

**Files:**
- `web/components/admin/SessionInbox.tsx`
- `web/components/admin/SmartCanvas.tsx`
- `api/routers/session_router.py`
- `api/tests/test_session_router.py`

**Acceptance criteria:**
- Creating a session from the inbox starts analysis without requiring the operator to open the session detail.
- `SmartCanvas.tsx` no longer owns the only auto-start path for fresh sessions.
- Duplicate analyze attempts are idempotent and do not create double runs.

---

### A3 · Dynamic queue-state feedback while analysis is running

**What:** Tighten status freshness for in-flight sessions. The queue should update quickly enough to show status transitions, failure states, and promotion into `Ready to review` without looking stalled.

**Why:** Once the row appears, the next trust problem is stale status. The operator should be able to see that the system is still working.

**Files:**
- `web/components/admin/SessionInbox.tsx`
- `web/components/admin/__tests__/SessionInbox.test.tsx`

**Acceptance criteria:**
- In-flight sessions visibly refresh while analysis is running.
- Promotion from `Analyzing now` to `Ready to review` happens without a manual refresh.
- Failure/cancelled states surface in `Recent sessions` with actionable retry messaging.

---

## Block B — JSON Hardening And Workflow-Debug Evidence

### B1 · Reduce recurring malformed JSON in session analysis

**What:** Harden `generate_session_intents()` and `generate_alumni_extraction()` against the malformed-output cases still hitting production. Review prompt contract, repair path, schema hinting, and chunk-merge behavior; then add regression fixtures for the failing patterns.

**Why:** Repair is a fallback, not the normal path. Frequent malformed JSON means the extraction contract is still too brittle.

**Files:**
- `api/services/llm.py`
- `api/tests/test_session_intents.py`
- `api/tests/test_llm_hardening.py`
- `api/tests/test_llm_observability.py`

**Acceptance criteria:**
- At least one new regression fixture covers a real malformed-JSON failure shape from recent session-card runs.
- Repeated malformed JSON becomes measurably rarer in local verification / fixture-backed tests.
- Repair-attempt failures are preserved as structured evidence instead of collapsing into an opaque empty result.

---

### B2 · Surface the missing repair and drop-point evidence in workflow detail

**What:** Expand the workflow summary/detail contract so the admin debug view exposes more than the current high-level summary: repair input/output previews, repair-attempt counts, validation rejection reasons, append/write outcomes, and alumni-path decisions.

**Why:** The current Langfuse-first workflow view exists, but it still does not answer the concrete debugging question: “Why did this run produce malformed JSON or no useful cards?”

**Files:**
- `api/services/trace_adapter.py`
- `api/models_kb.py`
- `api/routers/kb_router.py`
- `web/types/llm-observability.ts`
- `web/components/admin/TraceExplorerTab.tsx`
- `web/components/admin/LLMObservabilityTab.tsx`
- `api/tests/test_llm_observability.py`
- `web/components/admin/__tests__/TraceExplorerTab.test.tsx`
- `web/components/admin/__tests__/LLMObservabilityTab.test.tsx`

**Acceptance criteria:**
- Workflow detail shows repair attempts, validation result, append result, and alumni-path result for a run without needing raw log spelunking.
- A zero-card alumni run can be diagnosed from the UI alone.
- The plain-English summary remains intact; the extra detail appears in the technical evidence layer.

---

### B3 · Add a session-analysis reliability scorecard for this sprint

**What:** Produce a short artifact that records the concrete failure cases this sprint is fixing: stuck-feeling session creation, malformed JSON, missing alumni cards, and no-detail workflow runs. Use it as the sprint verification checklist.

**Why:** The team needs a visible definition of “performing to spec” for this loop, not just scattered bug fixes.

**Files:**
- `docs/session_pipeline_stabilization/reliability_scorecard.md` (new)

**Acceptance criteria:**
- The scorecard lists each reproduced failure, the expected post-fix behavior, and the verification method.
- The sprint can close only when every listed failure has a pass/fail note.

---

## Block C — SmartCanvas Zero-Scroll Review Loop

### C1 · Keep commit/discard actions accessible without page hunting

**What:** Rework the SmartCanvas review pane so the primary actions stay accessible while reviewing long cards. Prefer a sticky in-pane action bar or equivalent layout that prevents the repeated scroll-to-commit cycle.

**Why:** The current bottom-only action area breaks the review loop and makes each card feel slower than it is.

**Files:**
- `web/components/admin/SmartCanvas.tsx`
- `web/components/admin/__tests__/SmartCanvas.test.tsx`
- `web/e2e/admin-workspace.e2e.ts`

**Acceptance criteria:**
- The operator can commit/discard the current card without scrolling back to find the action area.
- Moving to the next card does not bounce the whole page into a disorienting position.
- The commit flow is measurably shorter in the UI: review, act, next card.

---

### C2 · Make clustered-uncertainty guidance collapsible or dismissible

**What:** Reduce the vertical footprint of the track-guidance banner and give operators control over it during card review. The message can remain available without permanently occupying prime screen space.

**Why:** The current banner is useful but too expensive in layout terms, especially when paired with long card forms.

**Files:**
- `web/components/admin/SmartCanvas.tsx`
- `web/components/admin/__tests__/SmartCanvas.test.tsx`

**Acceptance criteria:**
- Clustered-uncertainty guidance can be collapsed or dismissed for the current session view.
- The compact state still preserves enough context to reopen the guidance.
- Card review gets more usable vertical space on typical laptop screens.

---

### C3 · Remove unnecessary full-page scrolling from the session review layout

**What:** Finish the two-pane layout so scrolling is pane-local where appropriate, not page-global. The intent list, review form, and action controls should work inside a bounded workspace on desktop.

**Why:** The current mix of banners, headers, and content sections still creates too much total page height for a task that should feel like an editor.

**Files:**
- `web/components/admin/SmartCanvas.tsx`
- `web/components/admin/__tests__/AdminWorkspace.test.tsx`
- `web/e2e/admin-workspace.e2e.ts`

**Acceptance criteria:**
- On desktop, the SmartCanvas page can be used without avoidable full-page scrolling during normal review.
- The two-pane layout still degrades cleanly on mobile and tablet.
- Existing status, notice, and analysis states remain readable after the layout change.

---

## Block D — Alumni Extraction Reliability

### D1 · Reproduce and fix “alumni signal but no alumni cards” failures

**What:** Create a regression path for the real failure where a session that should have surfaced alumni cards did not. Instrument whether the miss came from `_is_alumni_heavy`, `generate_alumni_extraction()`, `_build_alumni_cards()`, or post-build validation.

**Why:** “No alumni card surfaced” is not one bug; it is a pipeline failure that can happen at multiple stages. The sprint should isolate which stage is failing in the recent runs.

**Files:**
- `api/routers/session_router.py`
- `api/services/llm.py`
- `api/tests/test_session_router.py`
- `api/tests/test_ai_eval.py`
- `api/tests/test_llm_observability.py`

**Acceptance criteria:**
- At least one fixture-backed test reproduces a real alumni miss and locks in the fix.
- Workflow detail clearly records whether the alumni path was skipped, invoked with zero cards, rejected in validation, or appended successfully.
- Sessions with strong alumni signal consistently produce reviewable alumni cards unless the note truly lacks actionable alumni updates.

---

### D2 · Tighten alumni-heavy detection and zero-card handling

**What:** Revisit `_is_alumni_heavy()` and the zero-card outcome path so the system handles borderline notes more honestly. If the alumni extractor runs and produces nothing useful, the operator should see that clearly instead of just “no alumni card”.

**Why:** Silent zero-card outcomes make the pipeline feel random and undermine trust in the card surface.

**Files:**
- `api/routers/session_router.py`
- `api/tests/test_alumni_detection.py`
- `web/components/admin/TraceExplorerTab.tsx`

**Acceptance criteria:**
- Alumni-heavy detection has explicit regression coverage for borderline and clearly-positive notes.
- Zero alumni cards after an invoked extraction produce a specific workflow-detail explanation.
- The UI no longer forces the operator to infer whether the alumni path ran.

---

## Definition of done for this sprint

- Creating a session immediately adds a visible row under `Analyzing now`.
- Session analysis starts from the creation flow, not only after opening SmartCanvas.
- In-flight queue state updates quickly enough that the app no longer feels frozen.
- Session-analysis malformed JSON has new regression coverage and a hardened repair path.
- Workflow detail exposes repair, validation, append, and alumni-path evidence sufficient for debugging real failures.
- SmartCanvas no longer requires repeated full-page scrolling to commit the next card.
- Clustered-uncertainty guidance no longer monopolizes vertical space.
- At least one real alumni-card miss is reproduced in tests and fixed.
- `api/pytest` and `web/npm test` are green at every merge.
- `TODOS.md` points to this sprint as the active plan for the session publishing loop.

## After this sprint

- Fold any leftover structural cleanup items back into `TODOS.md` and the archived code-quality finish sprint notes.
- If malformed JSON remains a common failure mode after prompt/repair hardening, promote JSON-contract work into its own reliability sprint with deeper `services/llm.py` decomposition and eval automation.
