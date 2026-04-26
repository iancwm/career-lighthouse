# Sprint: Alumni Cards — Card-Native Alumni Integration

**Duration:** ~1 week (reduced scope)
**Goal:** Counsellors upload one document and both the main KB and the alumni KB get populated through the same SmartCanvas card review interface. No forced KB-vs-alumni choice. No new modal flows.
**DRI:** Ian Chong
**Status:** Core implementation landed 2026-04-26. Analyze plus review path is working end to end; remaining follow-up items are narrowed to commit-response polish and deferred sprint scope.

**Source design:** `~/.gstack/projects/iancwm-career-lighthouse/iancwm-main-design-20260426-130438.md`
**Review log:** `/plan-eng-review` 2026-04-26, `mode: SCOPE_REDUCED`, 11 issues / 12 decisions taken / 0 unresolved.

---

## Implementation Snapshot

What is now live in code:
- `IntentCard(domain="alumni")` is wired through the Staging Area session pipeline.
- `generate_alumni_extraction()` runs for alumni-heavy notes and can emit `is_update`, `matched_slug`, `source_excerpt`, and multi-alumnus payloads.
- `SmartCanvas` has an alumni variant with confidence badges, evidence disclosure, trajectory preview, and chronological company history.
- `AlumniEntityStore.sync_company_links()` owns link reconciliation, and alumni commits validate against `AlumniDetail` before YAML write.
- `_call_with_trace()` now records `error` trace rows for unexpected client exceptions, which closed the observability hole found during QA.

What was verified:
- Backend regression ring passed after implementation (`55 passed` across alumni router/store/session/observability coverage).
- Playwright QA verified that an alumni-heavy Staging Area session renders an actual alumni card in SmartCanvas instead of silently finishing with `0` intents.

Still open from this sprint doc:
- Commit response should report `company_links_attempted` vs `company_links_written` when malformed links are dropped.
- The deferred schema-field and tab-migration work below is still deferred.

---

## Wedge

The single behavior change: when a counsellor uploads a document on the Staging Area and analyze runs, **alumni-heavy content produces alumni cards alongside the existing track and employer cards**. Counsellors edit and commit alumni cards through the same SmartCanvas they already use. Alumni records land in `knowledge/alumni/{slug}.yaml`.

**Implementation difference from older `SPRINT-SCHEMA-FOUNDATION`:**
- Older plan: add a separate Facts tab/editor workflow, extraction modal, and manual promote-to-record path on employer/alumni admin pages.
- This plan: make alumni extraction a first-class `IntentCard(domain="alumni")` in the existing Staging Area/SmartCanvas commit pipeline.
- Reused concepts from the older plan: deterministic slug collision handling, source-based confidence defaults, strict server-side validation, and explicit extraction error states.

What's deferred (TODOS.md `Next`):
- 5 schema fields (`career_trajectory_pattern`, `seniority_level`, `salary_band_estimate`, `profile_tier`, `experience_diversity`) — ship `career_trajectory_summary` + `home_country` only
- `AlumniFactsTab` migration to card-shaped data + new `/api/kb/alumni/extract` endpoint
- `AlumniDetectionModal` removal from SessionInbox

What's deferred (TODOS.md `Now`):
- Frontend test framework (vitest + react-testing-library)

---

## What already exists (don't rebuild)

| Asset | Location |
|-------|----------|
| `ALLOWED_ALUMNI_FIELDS`, `ALLOWED_ALUMNI_LINK_FIELDS` | `api/constants/profile_fields.py:45-95` |
| `_sync_company_links()` reconciliation | `api/routers/alumni_router.py:151` (will move) |
| `AlumniDetail`, `AlumniExtractionPreview`, `AlumniFieldProposal`, `AlumniCompanyLinkInput` | `api/models_employers.py` |
| `alumni_extraction` prompt | `api/cfg/prompts.yaml:180` |
| `extract-preview` endpoint | `api/routers/alumni_router.py:242` (stays during migration) |
| `preview_from_notes()` LLM call | `api/services/alumni_store.py:849` (will delegate to llm.py) |

---

## Contracts (the 12 decisions)

### Schema

**Extend `AlumniDetail`** at `api/models_employers.py:90`:
```python
career_trajectory_summary: str | None = None  # full narrative
home_country: str | None = None               # for student background matching
```

**Extend `ALLOWED_ALUMNI_FIELDS`** at `api/constants/profile_fields.py:45`:
```python
"career_trajectory_summary",
"home_country",
```

**Extend `IntentCard`** at `api/models_kb.py:224`:
```python
class IntentCard(BaseModel):
    card_id: str
    domain: Literal["employer", "track", "alumni"]   # ← add "alumni"
    summary: str
    diff: dict[str, Any]
    raw_input_ref: str
    status: Literal["pending", "committed", "discarded"] = "pending"
    proposals: dict[str, dict[str, Any]] = Field(default_factory=dict)  # ← new (CQ3)
    is_update: bool = False                                              # ← new (A3)
    matched_slug: str | None = None                                      # ← new (A3)
```

**Add `AlumniCardDiff`** at `api/models_kb.py`:
```python
class AlumniCardDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str
    full_name: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    graduation_year: str | int | None = None
    graduation_program: str | None = None
    home_country: str | None = None
    career_trajectory_summary: str | None = None
    notes: str | None = None
    can_refer: Literal["yes", "maybe", "no"] | None = None
    available_for_mentoring: bool | None = None
    company_links: list[dict] | None = None  # passes through to sync_company_links
```

**Extend `validate_intent_card_diff`** at `api/models_kb.py:213`:
```python
elif domain == "alumni":
    validated = _model_validate(AlumniCardDiff, diff)
```

### Helpers

**Move `_sync_company_links` → `AlumniEntityStore.sync_company_links`** (A1).
- Add public method on `AlumniEntityStore` at `api/services/alumni_store.py`.
- Keep alumni_router's import working: replace the in-router `_sync_company_links` body with a thin wrapper that calls `store.sync_company_links(slug, links)`.
- Same logic: upsert desired links, archive missing ones.

**Extract `generate_alumni_extraction` → `api/services/llm.py`** (CQ1, A3, A4, P1):
```python
def generate_alumni_extraction(
    text: str,
    existing_alumni: list[dict],     # minimal shape: [{"slug", "full_name", "current_company"}]
    session_id: str | None = None,
) -> dict:
    """Returns AlumniExtractionPreview-shaped dict augmented with:
       - is_update: bool per alumnus
       - matched_slug: str | None per alumnus  
       - source_excerpt: str per alumnus (the 1-2 sentences that triggered extraction)
    """
```

**Update `alumni_store.preview_from_notes`** to delegate to `llm.generate_alumni_extraction()`. Same return shape (no breaking change to `extract-preview`).

**Update prompt** at `api/cfg/prompts.yaml:180` — replace hard-coded field lists at `alumni_store.py:864-894` with:
```python
allowed_alumni_fields=", ".join(sorted(ALLOWED_ALUMNI_FIELDS)),
allowed_alumni_link_fields=", ".join(sorted(ALLOWED_ALUMNI_LINK_FIELDS)),
```
Extend the prompt to instruct the LLM to populate `is_update`, `matched_slug`, and `source_excerpt` for each alumnus.

### Session router

**Add `_is_alumni_heavy(text) -> bool`** — lightweight heuristic, no LLM call.
- Threshold: ≥3 career keywords (`graduated`, `worked at`, `joined`, `promoted`, `company`, `role`, `current`, `MD`, `VP`, `analyst`, etc.) AND ≥1 capitalized name pattern (e.g., `[A-Z][a-z]+ [A-Z][a-z]+`).
- Compile regexes once at module load.
- Returns False on empty/whitespace.
- **Ships only after T1 fixture corpus is in place.**

**Add `_build_alumni_cards(extraction, session_id) -> list[dict]`**:
- Maps each alumnus's `profile_proposals` → flat `diff` (just `.value` for each field).
- Carries `proposals: {field: {confidence, evidence, rationale}}` separately on the card.
- `slug` comes from extraction when present; otherwise generate from `full_name`, then resolve collisions by appending the current local date (`aditya-mehta-20260426`) before building the card. If this is an update, use `matched_slug`.
- `card_id = f"alumni-{slug}-{uuid4().hex[:8]}"`.
- `raw_input_ref` = `extraction.source_excerpt` (A4).
- `is_update`, `matched_slug` from extraction.
- Apply confidence defaults when the LLM omits confidence:
  - `source="direct_from_alumni"` → 95
  - `source="counselor"` → 85
  - `source="inferred"` or missing → 75
- **Server-side guard:** if `matched_slug` not in `existing_alumni`, downgrade `is_update=False` (failure mode 1).

**Add `_apply_field_updates_to_alumni(slug, diff) -> tuple[list[str], bool]`**:
- Strip `company_links` from diff before allowlist check.
- Call `alumni_store.get_alumni(slug)` — if None, create new.
- Apply diff fields against `ALLOWED_ALUMNI_FIELDS`; reject unknown fields with a clear commit error instead of silently dropping them.
- Validate the final `AlumniDetail` Pydantic shape before writing YAML.
- Call `store.sync_company_links(slug, company_links)` if present.
- Return `(changed_fields, is_new)`.

**Modify `analyze_session()`** at `api/routers/session_router.py:267`:
- After `generate_session_intents()` returns, gate on `_is_alumni_heavy(session.raw_input)`.
- If True, call `generate_alumni_extraction()` with minimal `existing_alumni` from `alumni_store.list_alumni()`.
- Run sequentially after track guidance. Wrap in try/except — non-fatal.
- Extraction errors are non-fatal but observable:
  - empty/whitespace source → skip alumni extraction
  - timeout → log warning and continue with track/employer cards
  - JSON/validation parse error → log sanitized parse context and continue
- Append alumni cards to `cards` list.
- Log timing: `logger.info("analyze: alumni extraction took %dms", ...)`.

**Extend `commit_card()`** dispatch:
```python
elif domain == "alumni":
    changed_fields, is_new = _apply_field_updates_to_alumni(target_slug, effective_diff)
```

### Frontend

**SmartCanvas alumni variant** at `web/components/admin/SmartCanvas.tsx`:
- Header: name + current title @ current_company
- "Updating existing X" banner when `card.is_update === true`
- Per-field confidence value (read from `card.proposals[field].confidence`)
- Per-field evidence snippet (hover or expand)
- `career_trajectory_summary` block (expandable text)
- `company_links` rendered as chronological list
- Edit mode: same inline-edit pattern as track cards
- "Alumni" badge to distinguish from track/employer
- Commit / Discard buttons (existing)

---

## Test strategy

### T1 — `_is_alumni_heavy` fixture corpus (BLOCKING)
Add `api/tests/fixtures/alumni_heavy_notes/`:
- 3 real anonymized counsellor notes that should trigger detection (`alumni_*.txt`)
- 2 KB-only notes that should NOT (`non_alumni_*.txt`)

`api/tests/test_session_intents.py` (or new `test_alumni_detection.py`):
- Parametrized test: each fixture → expected boolean.
- 3+ pass and 2+ fail required to merge.

### T3 — LLM eval cases (BLOCKING for prompt change)
Add 3 cases to `api/tests/test_ai_eval.py`:
1. Alumni note → `career_trajectory_summary` populated with full narrative
2. Note about existing alumnus → `is_update=true` and `matched_slug` matches
3. Note → `source_excerpt` populated with the 1-2 sentence trigger

Reuse the same 3 alumni fixtures from T1.

### Unit tests
| Test file | Coverage |
|-----------|----------|
| `test_models_kb.py` (new) | `IntentCard(domain="alumni")`, `validate_intent_card_diff("alumni", ...)`, `AlumniCardDiff` extra="forbid" rejection, `proposals` defaults to {} |
| `test_session_router.py` | alumni domain in `commit_card`, `_apply_field_updates_to_alumni` create/update paths, company_links stripping, strict unknown-field rejection, final `AlumniDetail` validation, slug safety |
| `test_session_intents.py` | `_is_alumni_heavy` parametrized fixtures, `_build_alumni_cards` proposals→diff transform, hallucinated matched_slug downgrade, generated slug collision date suffix, confidence defaults |
| `test_alumni_store.py` | `AlumniEntityStore.sync_company_links` upsert + archive (regression after move) |
| `test_alumni_router.py` | `_sync_company_links` wrapper still works, `extract-preview` returns same shape (regression) |
| `test_llm_observability.py` | `generate_alumni_extraction` trace logged with `feature="generate_alumni_extraction"` |

### Regressions
| Risk | Mitigation |
|------|-----------|
| `preview_from_notes()` API surface | `test_alumni_router.py::test_extract_preview_*` must pass after delegation refactor |
| Existing alumni YAML files load | Add `test_storage_hardening.py` case loading a YAML written before schema bump |
| Track/employer commit pipeline | Existing `test_session_router.py` track + employer commit tests must pass |
| `_sync_company_links` callers | `test_alumni_router.py` create/update tests must pass |
| Track guidance still built | `test_session_track_guidance.py` must pass |
| AlumniDetectionModal still works | Manual QA — modal opens, calls `extract-preview`, renders preview |

### Frontend
Manual QA only (no test framework — see TODOS.md). Per the test plan artifact at `~/.gstack/projects/iancwm-career-lighthouse/iancwm-main-eng-review-test-plan-20260426-135604.md`.

---

## Failure modes (must handle)

1. **Hallucinated `matched_slug`** — LLM returns `is_update=true` with a slug not in `existing_alumni`. `_build_alumni_cards` must downgrade to `is_update=false` and `matched_slug=None`. Counsellor sees "New alumnus" header, not "Updating existing X". Add unit test.
2. **Silent malformed `company_links`** — when `_normalize_company_link` filters out malformed entries, the commit response must report `company_links_attempted` vs `company_links_written`. SmartCanvas surfaces the discrepancy in the commit-result toast.
3. **Slug collision for new alumni** — if the generated slug already exists and this is not a confirmed update, append the current local date before card creation and YAML write. Add unit test.
4. **LLM output has unknown alumni fields** — reject during card validation/commit with a clear error; do not write partial YAML.

---

## Worktree parallelization

| Lane | Steps | Depends on |
|------|-------|-----------|
| **A** | Schema (models_employers + models_kb + constants) → session-router wiring | — / Schema |
| **B** | Move `_sync_company_links` → `AlumniEntityStore.sync_company_links` | — |
| **C** | Extract `generate_alumni_extraction` → `llm.py` + prompt update | Schema (uses ALLOWED_ALUMNI_FIELDS) |
| **D** | `_is_alumni_heavy` heuristic + fixture corpus | — |
| **E** | SmartCanvas alumni variant | Schema |

**Execution:** Lanes B + D in parallel worktrees first. Schema in Lane A (small, fast). Then C + E in parallel. Finish with session-router wiring in Lane A. Land everything together.

---

## Definition of Done

- [x] All 12 decisions implemented per contracts above, except the explicit `company_links_attempted` vs `company_links_written` commit-response polish
- [x] T1 fixture corpus in place (3 alumni + 2 non-alumni); pytest parametrized passes
- [ ] T3 eval cases in `test_ai_eval.py` pass against the new prompt
- [x] Unit tests cover the implemented backend code paths in this plan
- [x] All implemented regression tests pass (preview-shape, track/employer commit, track guidance, alumni router)
- [ ] Manual QA: counsellor uploads alumni-heavy doc → cards appear → commit → `knowledge/alumni/{slug}.yaml` exists with `career_trajectory_summary` populated
- [ ] Manual QA: existing alumnus session → "Updating existing X" header → commit merges, doesn't overwrite
- [ ] Manual QA: track + employer commits still work end-to-end
- [x] `test_alumni_router.py::extract_preview` shape is unchanged
- [ ] Four failure modes handled end to end (hallucinated matched_slug, malformed company_links discrepancy, slug collision, unknown LLM fields)
- [x] CHANGELOG.md updated
- [ ] TODOS.md three new entries land alongside (vitest + 5-fields + tab-migration)

---

## Out of scope (do not build)

- 5 deferred schema fields → TODOS.md `Next`
- `AlumniFactsTab` card-shape migration → TODOS.md `Next`
- `AlumniDetectionModal` removal → TODOS.md `Next`
- Frontend test framework → TODOS.md `Now`
- Async / parallel LLM calls → sequential accepted
- Combined intents+alumni single prompt → defer until both prompts mature

---

## References

- Source design: `~/.gstack/projects/iancwm-career-lighthouse/iancwm-main-design-20260426-130438.md`
- Test plan: `~/.gstack/projects/iancwm-career-lighthouse/iancwm-main-eng-review-test-plan-20260426-135604.md`
- Office-hours session: 2026-04-26 (Card-Native Alumni Integration approach)
- Eng review: 2026-04-26 commit `07ae4c0`, mode SCOPE_REDUCED
