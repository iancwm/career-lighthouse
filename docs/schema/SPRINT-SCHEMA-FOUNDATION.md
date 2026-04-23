# Sprint: Structured Facts Fact Foundation — Phase 2–3

**Duration:** 1–2 weeks  
**Goal:** Complete the schema foundation design-to-implementation gap. Ship Phase 2 UI and Phase 3 query endpoints. Validate with Stripe pilot.  
**DRI:** Ian Chong  
**Status:** Kickoff (2026-04-20)

---

## Overview

The SCHEMA-FOUNDATION.md design is approved and core infrastructure (models, LLM hardening, Langfuse traces) is in place. **Execution is blocked on Phase 2 UI and the alumni staging handoff** — counselors have no way to enter facts into the system yet, and alumni extraction still stops at a read-only preview. This sprint unblocks that and validates the design before scaling to batch tooling.

**Why now:** KB observability (Sprint 1) is done. Career profiles YAML are structured (Sprint 2). The next bottleneck is facts — counselors need to capture structured knowledge (timelines, alumni, interview stages) from prose without parsing it manually each time, then move alumni notes through staging before they become canonical records.

---

## Phase 2: Admin UI for Fact Capture (Fact-Entry Form + LLM Extraction)

### Current State (2026-04-20 Assessment)

**EmployerFactsTab exists but lacks facts UI:**
- ✓ Two-panel layout (35% left list, 65% right form)
- ✓ Employer list with search, add, delete
- ✓ Full employer detail form (name, tracks, EP requirement, intake seasons, headcount, application process, counselor contact, notes)
- ✗ **ZERO structured facts UI** — no fact type selector, field editors, "New Fact" button, or facts list display

**AlumniFactsTab exists but lacks a staging bridge:**
- ✓ Read/write alumni record surface exists
- ✓ Preview extraction exists for notes
- ✗ Extraction stops at preview, there is no explicit promote-to-record staging step
- ✗ The note intake and record viewing order is not yet specified for the top of the page

**Recommended architecture: Tabbed approach (Option A)**
```
Employer: Stripe Singapore
├─ [Details tab] — current form fields (name, tracks, EP, notes, etc.)
└─ [Facts tab] 
    ├─ Facts list (read-only with delete buttons)
    ├─ "Extract from notes" button → modal with extracted facts
    └─ "New Fact" button → accordion form with type selector + field editors
```

Benefits: Clean separation, facts are discoverable, extraction is first-class.

### Task 2.1 — Complete EmployerFactsTab fact-entry form
**Ownership:** Ian  
**Estimate:** 3 days  
**Acceptance Criteria:**
- Employer detail splits into two tabs: Details + Facts
- Facts tab shows:
  - List of existing facts from `selected.structured.facts[]` (read-only, with delete on hover)
  - Fact cards display: type badge, slug, key field (name for alumni, phase_name for timelines), confidence, source
- "New Fact" button opens accordion form with:
  - Fact type selector (radio buttons): `timeline_phase`, `alumni`, `interview_stage`, `compensation`, `skill_requirement`
  - Type-specific field editors (see SCHEMA-FOUNDATION.md lines 195–250 for all field specs):
    - **timeline_phase**: phase_name, value/date, role_type, duration_days
    - **alumni**: name, degree, school, graduation_year, current_company, current_title, available_for_mentoring (boolean)
    - **interview_stage**: order (number), name, format dropdown, duration_minutes, focus (chips), typical_advance_rate (%)
    - **compensation**: role_level, currency, base_salary_min/max, bonus_range, equity (boolean)
    - **skill_requirement**: focus (chips), preferred_background (chips)
  - Common fields: `slug` (auto-generated from inputs), `source` dropdown (counselor | inferred | direct_from_alumni), `confidence` slider (1–100)
  - "Add to list" button appends to local fact list
- Facts persist to employer YAML `structured.facts[]` when counselor clicks "Save employer updates"

**Files to edit:**
- `web/components/admin/EmployerFactsTab.tsx` — add Details/Facts tabs, integrate fact form
- `web/components/admin/forms/FactEditor.tsx` — **new** sub-component for type-specific field editors (reusable)
- `web/components/admin/forms/FactCard.tsx` — **new** fact display card with delete button

**Schema decisions (locked in, see detailed decisions below):**
1. **Slug generation:** auto-generate from `employer_slug + fact_type + key_field`, append `YYYYMMDD` on collision
2. **Confidence defaults by source:** YES — 95 for direct alumni, 85 for counselor, 75 for inferred
3. **Fact deletion:** soft delete with `deleted: true` flag (preserves audit trail)
4. **Schema strictness:** validate all facts against Pydantic model, reject if invalid
5. **Fact ordering:** sort by `timestamp DESC` (newest first) in YAML output

**Reference:** See sample facts at SCHEMA-FOUNDATION.md lines 427–471.

### Task 2.2 — Add LLM extraction trigger in fact form
**Ownership:** Ian  
**Estimate:** 2 days  
**Acceptance Criteria:**
- Facts tab has "Extract from notes" button (next to "New Fact")
- Button reads counselor `notes` field and calls extraction endpoint
- Modal shows extracted facts as JSON with fields:
  - side-by-side: **Extracted** (left) vs **Already in list** (right)
  - each fact shows: type badge, slug, key fields, confidence
  - checkboxes to select which facts to add
  - "Add selected" button appends checked facts to local list
- Confidence defaults based on `source: "inferred"` (70–80)
- Error handling: 
  - Empty notes → show toast "Add counselor notes first"
  - Timeout → show "Extraction took too long, try again"
  - Parse error → show raw JSON for debugging

**UX flow:**
1. Counselor clicks "Extract from notes"
2. Frontend shows spinner while LLM processes
3. Modal appears with extracted facts grid
4. Counselor uncheck facts already in the list (manual dedup)
5. Click "Add selected" → facts move to local Facts list
6. Counselor edits/refines as needed
7. Click "Save employer updates" → persists to YAML

**Files to edit:**
- `web/components/admin/EmployerFactsTab.tsx` — add extraction button + modal
- `web/components/admin/modals/ExtractedFactsModal.tsx` — **new** facts grid + selection UI
- `api/routers/kb_router.py` — new endpoint `POST /api/kb/employers/{slug}/extract-facts`

**API endpoint spec:**
```python
@router.post("/api/kb/employers/{slug}/extract-facts")
async def extract_facts_from_employer_notes(slug: str, request: ExtractFactsRequest):
    """
    Extract structured facts from employer notes using LLM.
    Returns: { facts: [ { type, slug, ...fields }, ... ], confidence_distribution: {...} }
    """
```

### Task 2.3 — Fact extraction prompt refinement
**Ownership:** Ian  
**Estimate:** 1 day  
**Acceptance Criteria:**
- Prompt accepts employer notes + track context
- Outputs valid JSON facts array with schema shell fields:
  ```json
  [
    {
      "slug": "stripe-internship-timeline",
      "type": "timeline_phase",
      "phase_name": "Internship Application",
      "value": "March 1 – May 31",
      "role_type": "summer_internship",
      "source": "inferred",
      "confidence": 75,
      "timestamp": "2026-04-20T..."
    },
    {
      "slug": "stripe-aditya-mehta",
      "type": "alumni",
      "name": "Aditya Mehta",
      "degree": "LLM",
      "school": "NUS",
      "graduation_year": 2018,
      "current_company": "Stripe Singapore",
      "current_title": "Head of Compliance Program APAC",
      "joined_year": 2020,
      "available_for_mentoring": true,
      "source": "inferred",
      "confidence": 90
    }
  ]
  ```
- Extraction test on **Stripe notes** (existing prose in stripe.yaml):
  - Should extract: timeline, alumni (Aditya), interview stage hints, compensation signal
  - Accuracy check: manually compare against sample facts (SCHEMA-FOUNDATION.md lines 427–471)
  - Target: 80%+ facts recovered with correct field values

**Prompt guidance:**
```
You are extracting structured facts from employer notes for a student career platform.

Notes text:
{notes}

Career track: {track_name}

Extract ALL facts matching these types:
1. timeline_phase — when do applications open/close for which roles?
2. alumni — any student names, schools, years, companies mentioned?
3. interview_stage — steps in the process, format, duration?
4. compensation — salary ranges, equity, benefits?
5. skill_requirement — what background/skills do they look for?

For each fact:
- Use lowercase slug naming: "company-type-keyfield"
- Set confidence: 100 if directly stated, 80 if strongly inferred, 50 if guessed
- timestamp: today's date
- source: "inferred"

Output ONLY valid JSON. No prose.
```

**Files to edit:**
- `api/prompts/fact_extraction.yaml` — **new** extraction-specific prompt
- `api/services/llm.py` — add `extract_facts_from_prose()` helper (returns validated list or error)
- `api/tests/test_fact_extraction.py` — **new** test suite with Stripe notes example

### Task 2.4 — Alumni record staging and page layout
**Ownership:** Ian  
**Estimate:** 2 days  
**Acceptance Criteria:**
- Alumni Records page starts with a note-extraction composer at the top, before the persisted record list.
- The record viewer sits below the document upload / parsed-text block, so the source note is visible before the canonical record.
- Extraction results land in a staging state first, not as an immediate save.
- Staging shows candidate alumni fields, suggested company links, confidence, and source text, with explicit promote / discard controls.
- `Save alumni` only writes to canonical alumni YAML after the staged review is accepted.
- Alumni extraction can also be surfaced from the existing staging area so counsellors can review alumni facts alongside employer/profile updates.

**Files to edit:**
- `web/components/admin/AlumniFactsTab.tsx` — top-of-page extraction composer and record viewer placement
- `web/components/admin/KnowledgeUpdateTab.tsx` — surface alumni staging alongside existing diff review
- `web/components/admin/SessionInbox.tsx` — pass alumni-only notes into the staging flow when appropriate
- `web/components/admin/modals/AlumniExtractionModal.tsx` — **new** staging review modal for alumni drafts
- `api/routers/alumni_router.py` — add explicit staging/promote actions if the preview needs a write-through step
- `api/services/alumni_store.py` — helper(s) for staged draft normalization and promotion

**UX flow:**
1. Counselor pastes or uploads a note.
2. Alumni extraction appears at the top of the page.
3. The draft alumni record is shown in staging, below the upload / parsed-note area.
4. Counselor reviews the candidate profile and company links.
5. Counselor promotes the staged draft into the alumni record or discards it.
6. The saved alumni record then appears in the canonical record list below.

**Design note:** This keeps the staged note preview and the saved record separate. No silent auto-save. The page has one job at each vertical band, which fits the existing admin workspace and avoids a second hidden save path.

---

## Phase 3: Student Query Surface (`/api/kb/facts` Endpoint)

### Task 3.1 — Build `/api/kb/facts` list and filter endpoint
**Ownership:** Ian  
**Estimate:** 2 days  
**Acceptance Criteria:**
- `GET /api/kb/facts` returns all facts from all career profiles + employers
- Query filters work:
  - `?type=alumni` — only alumni facts
  - `?type=interview_stage&employer=stripe` — interview stages for Stripe
  - `?school=NUS&graduation_year=2018` — filter on alumni school + year
  - `?confidence__gte=80` — confidence >= 80
  - `?source=direct_from_alumni` — filter by source
- Response includes fact metadata (slug, timestamp, trace_id, source URL for counselor edits)
- Tests pass (filtering, edge cases, auth)

**Files to create:**
- New endpoint in `api/routers/kb_router.py` — `@router.get("/facts")`

**Files to edit:**
- `api/models.py` — add `FactQueryResponse` pydantic model
- `api/services/career_profiles.py` or new `fact_store.py` — fact reading + filtering

### Task 3.2 — Grouped facts view (`/api/kb/facts/grouped`)
**Ownership:** Ian  
**Estimate:** 1 day  
**Acceptance Criteria:**
- `GET /api/kb/facts/grouped?by=employer` groups facts by employer slug
- `GET /api/kb/facts/grouped?by=type` groups by fact type
- Used by counselor dashboard (Task 4.1)

---

## Phase 1 Validation: Pilot Test (Stripe + fintech_compliance)

### Task 1.1 — Write 3–5 sample facts manually for Stripe
**Ownership:** Ian  
**Estimate:** 1 day  
**Acceptance Criteria:**
- Add `structured.facts[]` section to `knowledge/employers/stripe.yaml`
- Include facts:
  1. `timeline_phase` (Summer internship application window June–August)
  2. `alumni` (Aditya Mehta, LLM NUS '18, Head of Compliance)
  3. `interview_stage` (Round 1: HR screening, 20–30 min phone call)
  4. `skill_requirement` (AML/KYC, financial crime experience)
  5. `compensation` (equity as key differentiator vs banks)
- Round-trip: write YAML, read via API, confirm structure is preserved
- Commit with message: "test: add sample structured facts to Stripe employer"

**Reference:** SCHEMA-FOUNDATION.md lines 427–471 (Stripe sample facts).

### Task 1.2 — Test LLM extraction on real counselor note
**Ownership:** Ian  
**Estimate:** 1 day  
**Acceptance Criteria:**
- Pick 1 real counselor note (e.g., interview feedback, employer feedback)
- Run extraction prompt end-to-end (note → Claude → structured facts)
- Measure accuracy: compare extracted facts against manually-written ground truth
  - Target: 80%+ of facts extracted with correct field values
  - Flag: facts with confidence < 70 as "requires review"
- Document results in commit message or SPRINT-SCHEMA-FOUNDATION-RESULTS.md

---

## Schema Integration: Decisions Locked In ✓ (2026-04-20)

All five schema concerns have been decided. Implementation can proceed.

### 1. Slug collision handling → **Option A + date suffix** ✓
Use full name disambiguation first: `stripe-aditya-mehta`. If collision persists (unlikely), append date: `stripe-aditya-mehta-20260420`.
- Clear, readable, auditable
- Implementation: `slug = slugify(key_fields) if unique else f"{slug}-{YYYYMMDD}"`

### 2. Confidence defaults by source → **YES** ✓
- `source: "direct_from_alumni"` → default confidence 95 (counselor can adjust)
- `source: "counselor"` → default confidence 85
- `source: "inferred"` → default confidence 75

Slider remains editable; defaults are just starting points.

### 3. Fact deletion semantics → **Soft delete (Option B)** ✓
Mark deleted facts as `deleted: true` in YAML (don't remove array element).
- Preserves audit trail: git diff shows `deleted: true` line
- Allows un-deletion if needed (phase 2+)
- Queries filter out `deleted: true` facts by default

**Implementation:** 
- Facts tab delete button → sets `deleted: true` (not removed from array)
- Facts list display → filters `fact.deleted !== true`
- API endpoint `GET /api/kb/facts` → default filter `?include_deleted=false`
- Add `deleted: bool = False` field to `Fact` Pydantic model

### 4. Schema strictness on save → **Option A (strict)** ✓
Validate all facts against Pydantic `Fact` model on save.
- Reject facts missing required fields: `type`, `slug`, `source`, `confidence`, `timestamp`
- Show error banner: `"Fact validation failed: 'stripe-timeline-1' missing confidence"`
- Counselor cannot save until all facts are valid

### 5. Fact ordering in YAML → **Timestamp descending (Option B)** ✓
Sort facts by `timestamp DESC` (newest first) when writing to YAML.
- Makes diffs readable: new facts appear at top
- Easy to spot recently-added facts in code review
- Implementation: `sorted(facts, key=lambda f: f.timestamp, reverse=True)` before YAML dump

---

## Unblocking Dependencies

| Task | Blocker | Status |
|------|---------|--------|
| All Phase 2 | `EmployerFactsTab` form scaffold | ✓ Exists (684 lines); extend with fact-entry UI |
| Task 2.2 | `/api/kb/analyse` endpoint | ✓ Exists; reuse or create new extraction endpoint |
| Task 3.1 | Career profile + employer reading | ✓ Already in `CareerProfileStore` and `EmployerEntityStore` |
| Task 1.2 | Real counselor notes | ✓ Use existing Stripe notes (SCHEMA-FOUNDATION.md lines 14–19) |

---

## Architecture Decisions

### Storage: YAML in-file vs database
**Decision:** YAML in-file (in-repo).  
**Why:** Git-trackable, easy merge resolution, counselor-editable, backward compatible.  
**Downside:** Slower at >1000 facts per file; requires careful slug deduplication.  
**Future:** Migrate to Postgres if dedup and querying become bottlenecks (not phase 1).

### Deduplication
**Decision:** Slug uniqueness; second fact with same slug updates (timestamp updated).  
**Why:** Simple, no separate metadata table, works in YAML.  
**How:** On write, check if fact slug exists in file; if yes, replace; if no, append.

### Versioning
**Decision:** Per-file git history (no per-fact version field).  
**Why:** Simpler, leverages existing git infrastructure.  
**Trade-off:** Audit trail is file-level, not per-fact. Acceptable for phase 1.

### Confidence semantics
**Decision:** 1–100 = certainty ("how sure are we this is true?").  
**Why:** Aligns with existing usage; LLM can output confidence naturally.  
**Future:** May add separate "completeness" field if needed (e.g., interview process is 80% described).

---

## Rollout & Validation

**Phase 2 completion → Phase 2 demo to Ian** (counselor workflow)
- Manual entry works
- Extraction works (80%+ accuracy test pass)

**Phase 1 validation → Merge to main, tag v0.1.6**
- Stripe facts written and committed
- `/api/kb/facts` endpoint tested
- Ready for broader counselor adoption

**Phase 3 deployment → Monitor adoption**
- Counselors using EmployerFactsTab to capture facts
- Track velocity: facts/week captured

**Gate to Phase 4 (counselor dashboard):** 50+ facts captured from 5+ employers.

---

## Success Criteria

1. ✓ **EmployerFactsTab fact-entry form shipped** — counselors can add facts manually
2. ✓ **LLM extraction integrated** — counselors can extract facts from prose with 80%+ accuracy
3. ✓ **`/api/kb/facts` query endpoint shipped** — facts are queryable by type, employer, school, source
4. ✓ **Stripe pilot completed** — 5 sample facts written; extraction test passes
5. ✓ **Schema design validated** — no showstoppers; structure feels natural

---

## Risks & Mitigation

| Risk | Mitigation |
|------|-----------|
| LLM extraction accuracy < 80% | Refine extraction prompt; add human review gate |
| Slug collisions during pilot | Manual review on write; add uniqueness test |
| EmployerFactsTab form too complex | Start with 2 fact types (timeline, alumni); expand later |
| Phase 3 API filtering too slow (many facts) | Index facts by employer at read-time; cache `/facts/grouped` |

---

## Implementation Guidance

### Task 2.1: Step-by-step breakdown

**Step 1: Add Details/Facts tabs to employer detail** (1 hr)
- In EmployerFactsTab right panel, add tab buttons: "Details" | "Facts"
- Move current form fields into Details tab
- Create Facts tab skeleton (empty for now)

**Step 2: Build FactEditor component** (2 hrs)
- Input component library: reuse existing TextField, TextArea, ChipInput, PillToggleGroup
- Create type-specific editor configs (map fact type → field schema):
  ```typescript
  const fieldSchemas: Record<FactType, Field[]> = {
    timeline_phase: [
      { name: "phase_name", type: "text", label: "Phase name" },
      { name: "value", type: "text", label: "Date/Window" },
      { name: "role_type", type: "select", label: "Role type", options: [...] },
      { name: "duration_days", type: "number", label: "Duration (days)" },
    ],
    alumni: [...],
    // ...
  }
  ```
- Render fields dynamically based on selected type

**Step 3: Build FactCard component** (30 min)
- Display: `[type badge] slug | key_field_value | confidence% | source`
- Delete button on hover
- Used in Facts list

**Step 4: Wire Facts tab UI** (2 hrs)
- State: `facts: Fact[]` (local list)
- Read from `selected.structured.facts` on employer load
- Display facts list with FactCard
- Add "New Fact" button → opens FactEditor accordion
- Add "New Fact" → creates local fact, append to list
- Delete fact → remove from local list
- Save button in sticky footer persists entire list to YAML

**Step 5: Test round-trip** (1 hr)
- Manually add 3 facts to Stripe via UI
- Click Save
- Reload page
- Verify facts reappear in Facts tab

### Task 2.2: Step-by-step breakdown

**Step 1: Create ExtractedFactsModal component** (1.5 hrs)
- Input: `extracted: Fact[]`, `existing: Fact[]`
- Show two-column layout:
  - **Left (Extracted)**: facts with checkboxes, grouped by type
  - **Right (Already in list)**: de-duped against extracted (by slug)
  - Highlights: facts already captured (grayed out, unchecked)
- "Add selected" button returns checked facts

**Step 2: Add "Extract from notes" button + trigger** (1 hr)
- Add button next to "New Fact" in Facts tab
- On click: check if notes are empty → show toast if so
- Show spinner overlay
- Call `POST /api/kb/employers/{slug}/extract-facts`

**Step 3: Implement backend endpoint** (1.5 hrs)
- `POST /api/kb/employers/{slug}/extract-facts`
- Read employer notes from disk
- Call `extract_facts_from_prose(notes)` (from llm.py)
- Return JSON array of facts

**Step 4: Test end-to-end** (1 hr)
- Click "Extract from notes" on Stripe
- Verify modal appears with extracted facts
- Select some facts, click "Add selected"
- Verify facts appear in Facts tab

### Task 2.3: Step-by-step breakdown

**Step 1: Write extraction prompt** (1 hr)
- Use the guidance above as template
- Test manually with Stripe notes:
  ```bash
  curl -X POST http://localhost:8000/api/kb/employers/stripe/extract-facts
  ```

**Step 2: Implement `extract_facts_from_prose()` in llm.py** (1 hr)
- Call Claude with fact extraction prompt
- Parse response JSON (use existing JSON repair path)
- Validate against Pydantic `Fact` model
- Return list or raise error

**Step 3: Accuracy test on Stripe notes** (1 hr)
- Extract facts from stripe.yaml notes
- Manually compare to sample facts (SCHEMA-FOUNDATION.md lines 427–471)
- Count: how many facts extracted? how many correct?
- Document: "Extracted 5/5 facts, 90% field accuracy"
- If < 80%, refine prompt and retry

## Estimated Timeline

| Task | Effort | Start | End |
|------|--------|-------|-----|
| 2.1 EmployerFactsTab form | 3d | W1 Mon | W1 Wed |
| 2.2 Extraction trigger | 2d | W1 Thu | W2 Fri |
| 2.3 Prompt refinement | 1d | W2 Mon | W2 Tue |
| 2.4 Alumni staging integration | 2d | W2 Tue | W2 Wed |
| 3.1 `/api/kb/facts` endpoint | 2d | W2 Wed | W2 Fri |
| 3.2 Grouped view | 1d | W3 Mon | W3 Mon |
| 1.1 Stripe sample facts | 1d | W3 Tue | W3 Tue |
| 1.2 LLM extraction test | 1d | W3 Wed | W3 Wed |
| **Total** | **13d** | W1 Mon | W3 Wed |

---

## Getting Started Checklist

**BEFORE you start coding Task 2.1:**
- [ ] Lock in schema integration decisions (see section above)
- [ ] Decide on tab layout (recommended: Details + Facts tabs)
- [ ] Sketch out FactEditor component field schema for each type
- [ ] Check api/models.py for existing `Fact` Pydantic model (should exist from earlier work)
- [ ] Verify `EmployerFactsTab.tsx` loads correctly with Stripe employer

**Day 1 (Task 2.1 start):**
- [ ] Create web/components/admin/forms/FactEditor.tsx (type-specific field schemas)
- [ ] Create web/components/admin/forms/FactCard.tsx (read-only fact display)
- [ ] Add Details/Facts tabs to EmployerFactsTab
- [ ] Wire Facts tab to show existing facts + "New Fact" button
- [ ] Test: manually add 1 fact via UI, save, reload, verify it persists

**Day 1–2 (Task 2.2 start):**
- [ ] Create web/components/admin/modals/ExtractedFactsModal.tsx
- [ ] Add "Extract from notes" button to Facts tab
- [ ] Implement `POST /api/kb/employers/{slug}/extract-facts` endpoint (stub: returns empty for now)
- [ ] Wire button to show modal (even if extraction is fake)

**Day 2–3 (Task 2.3 start):**
- [ ] Write fact extraction prompt in api/prompts/fact_extraction.yaml
- [ ] Implement `extract_facts_from_prose()` in api/services/llm.py
- [ ] Test manually with Stripe notes: extract 3–5 facts, verify accuracy
- [ ] Wire up backend endpoint to call extraction
- [ ] End-to-end test: click "Extract from notes", see results in modal

**Day 3–4 (Task 2.4 start):**
- [ ] Add top-of-page alumni extraction composer to AlumniFactsTab
- [ ] Add staging review modal for alumni drafts
- [ ] Wire alumni drafts into KnowledgeUpdateTab / staging flow
- [ ] Verify promoted alumni facts land in the canonical record list below the intake block

**Day 3 (Phase 1 validation):**
- [ ] Write 5 sample facts manually to stripe.yaml (or via UI)
- [ ] Run extraction test on Stripe notes, measure accuracy
- [ ] Commit both manual facts and extraction test results

---

## Current Assessment (2026-04-20)

**EmployerFactsTab status:** 
- ✓ Employer list + CRUD (create, read, update, delete) functional
- ✓ Two-panel layout established
- ✓ Form fields for employer metadata complete
- ✗ **NO facts UI** — needs Details/Facts tabs and entire fact workflow

**Recommended starting point:**
Don't refactor existing employer form. Keep Details tab as-is. Add Facts tab alongside. This keeps risk low and change surface small.

---

## Definition of Done

- All tests pass locally and in CI
- Fact entry + retrieval round-trip validated (write YAML via UI → read API → verify structure persists)
- Facts can be added manually and persist to YAML
- LLM extraction works with 80%+ accuracy on real counselor notes
- Extraction test results documented (accuracy %, fact count, confidence distribution)
- Code review approved (design fit, security, error handling)
- Merged to main; tagged v0.1.6.0 or later
- SCHEMA-FOUNDATION.md updated with any schema adjustments discovered during implementation
- Team demo showing: manual fact entry + extraction workflow on Stripe

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 2 | CLEAN (PLAN) | 6 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 2 | CLEAN (FULL) | score: 6/10 → 8/10, 1 decision |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**CODEX:** none on this branch yet.
**CROSS-MODEL:** staging-first alumni extraction now matches the existing knowledge-review pattern, so the plan avoids a second direct-write flow.
**UNRESOLVED:** 0
**VERDICT:** ENG + DESIGN CLEARED, ready to implement.
