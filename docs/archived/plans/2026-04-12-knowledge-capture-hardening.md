# Sprint: Knowledge Capture Hardening

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure that real-world counsellor memos (DOCX with structured tables, multi-entity content, rich compensation ladders) are fully extracted, correctly structured, and surfaced to students without silent data loss.

**Trigger:** Analysis of five AI-generated demo memos in `demo-data/sample-career-notes/` revealed three concrete blockers and two structural gaps. This sprint closes them.

**Scope:** Extraction logic, schema expansion, intake routing, and two `Now`-priority security/validation items from `TODOS.md`.

**Tech Stack:** FastAPI, Pydantic, python-docx, Anthropic Claude, Next.js/React, file-based YAML storage

**Out of scope this sprint:** Auth/RBAC, session cleanup, health endpoint performance, thundering herd.

---

## Task 1: Fix DOCX table extraction

**Why:** `parse_file()` in `api/services/ingestion.py` reads only `doc.paragraphs`. DOCX tables live in `doc.tables` — not `doc.paragraphs` — so every structured table in a counsellor memo is silently dropped. Career progression ladders, compensation tables, and hiring statistics are all affected. These memos are ~30-40% tables by information density.

**Files:**
- Modify: `api/services/ingestion.py`

- [ ] **Step 1: Rewrite DOCX extraction to walk the document body in order**

Replace the DOCX branch of `parse_file()`:

```python
elif filename.lower().endswith(".docx"):
    import io
    from docx import Document
    from docx.oxml.ns import qn
    doc = Document(io.BytesIO(content))
    parts = []
    for block in doc.element.body:
        if block.tag == qn('w:p'):
            # Paragraph — collect run text
            text = "".join(
                run.text for run in block.iter(qn('w:t'))
                if run.text
            )
            if text.strip():
                parts.append(text)
        elif block.tag == qn('w:tbl'):
            # Table — format as pipe-delimited rows
            rows = []
            for row in block.iter(qn('w:tr')):
                cells = []
                for cell in row.iter(qn('w:tc')):
                    cell_text = "".join(
                        t.text for t in cell.iter(qn('w:t')) if t.text
                    ).strip()
                    cells.append(cell_text)
                if any(cells):
                    rows.append(" | ".join(cells))
            if rows:
                parts.append("\n".join(rows))
    return "\n".join(parts)
```

- [ ] **Step 2: Add a test covering table extraction**

Add to the existing ingestion tests (or `tests/test_ingestion.py`):
- Build a minimal DOCX in memory with one paragraph and one 2×3 table using `python-docx`
- Assert that `parse_file()` output contains both the paragraph text and the pipe-delimited table rows
- Assert no content is silently dropped (row count matches)

**Edge case note:** Synthetic 2×3 tables won't catch merged cells or multi-paragraph cells (common in
real counsellor memos). Add a second test that builds a DOCX with a merged-cell header row and assert
the merged cell text appears exactly once (not duplicated by the iteration).

- [ ] **Step 3: Verify against demo memos manually (optional, dev only)**

Run `parse_file()` against the five memos in `demo-data/sample-career-notes/` and confirm compensation tables and career progression tables appear in the output text.

---

## Task 2: Expand the track schema for career progression and salary ladders

**Why:** All five demo memos carry per-level salary tables (Junior → Senior → Manager → Head, each with base + variable). The current `salary_range_2024: str` field flattens this into one string. Students asking "what can I earn as a junior?" and "what's the senior ceiling?" get the same compressed answer.

Similarly, the GGV memo's visa pathway detail (EP → Tech.Pass → PR timeline, partnership eligibility conditions) is too rich to compress into `ep_sponsorship: str` alone.

**Files:**
- Modify: `api/models.py` (DraftTrackDetail)
- Modify: `api/services/llm.py` (generate_track_draft prompt)
- Modify: `api/routers/kb_router.py` (_draft_ready_for_publish, commit flow)
- Modify: relevant YAML profile files if fields are being backfilled

- [ ] **Step 1: Add typed sub-model and two optional fields to `DraftTrackDetail`**

In `api/models.py`, add before `DraftTrackDetail`:

```python
class SalaryLevel(BaseModel):
    stage: str        # e.g. "Junior Analyst"
    range_sgd: str    # e.g. "80–110K"
    notes: str = ""   # e.g. "Base + 15-20% bonus"
```

Then add to `DraftTrackDetail`:

```python
# Optional: per-stage salary breakdown extracted from counsellor research.
salary_levels: list[SalaryLevel] | None = None

# Optional: visa and international pathway notes beyond the ep_sponsorship headline.
# Captures EP→Tech.Pass→PR progression, partnership eligibility requirements, etc.
visa_pathway_notes: str | None = None
```

Both are optional so existing drafts and published profiles are not broken.

**Backwards compat note:** `get_draft()` calls `DraftTrackDetail(**payload)`. Old draft YAMLs without
`salary_levels` or `visa_pathway_notes` will deserialise cleanly because both fields default to `None`.
Add a backwards compat test to confirm (Step 2).

- [ ] **Step 2: Update `generate_track_draft` prompt to populate these fields**

In `api/services/llm.py`, add to the system prompt schema block:

```
"salary_levels": [
  {"stage": "<career stage>", "range_sgd": "<SGD range>", "notes": "<bonus/equity context>"}
],
"visa_pathway_notes": "<multi-step visa path if relevant, empty string otherwise>",
```

Add to the rules block:
```
- salary_levels: extract per-stage compensation if the input has level-by-level data. Leave as [] if not present.
- visa_pathway_notes: include EP/Tech.Pass/PR timeline and any partnership eligibility conditions if the track has significant international complexity. Empty string if not relevant.
```

- [ ] **Step 3: Wire new fields through `publish_draft()` and `TrackReferenceDetail`**

`TrackDraftStore.publish_draft()` (in `api/services/track_drafts.py`) builds `published_payload` as
a **hardcoded dict** (lines 279-301). `model_dump()` is not called on the payload — fields not
explicitly listed are silently dropped. You must add the new fields explicitly:

```python
published_payload = {
    ...existing fields...,
    "salary_levels": [s.model_dump() for s in detail.salary_levels] if detail.salary_levels else [],
    "visa_pathway_notes": detail.visa_pathway_notes or "",
}
```

Also update `TrackReferenceDetail` in `api/models.py` to include both fields (same optional typing),
so the reference summary block shown in Track Builder reflects the published values.

`save_draft()` uses `detail.model_dump()` and will persist the new fields to draft YAML correctly —
no change needed there.

- [ ] **Step 4: Update the chat prompt to inject salary_levels when querying about compensation**

In `api/services/llm.py` `chat_with_context()`, when building `career_context`, include `salary_levels` in the injected block if present — so students asking "how much can I earn as a junior?" get level-specific data rather than the compressed range.

The career profile `to_context_block()` method (in `api/services/career_profiles.py`) should be updated to serialize `salary_levels` as a small table and `visa_pathway_notes` as a paragraph.

- [ ] **Step 5: Add backwards compat and round-trip tests**

In the track draft tests:

- **Backwards compat:** Load a draft YAML dict that does NOT contain `salary_levels` or
  `visa_pathway_notes`. Call `DraftTrackDetail(**payload)`. Assert it deserialises without error
  and both fields are `None`.

- **publish_draft round-trip:** Build a `DraftTrackDetail` with `salary_levels=[SalaryLevel(...)]`
  and `visa_pathway_notes="EP → Tech.Pass in 3y"`. Call `publish_draft()`. Read the output YAML.
  Assert `salary_levels` and `visa_pathway_notes` are present in the published file and values match.

- **LLM eval smoke test** (mark `@pytest.mark.integration` — skipped in CI by default):
  Run `generate_track_draft` against the UOB memo fixture. Assert `salary_levels` has at least 2
  entries. Assert `visa_pathway_notes` is non-empty for the GGV memo fixture. These are not
  assertions on exact strings — just non-empty presence checks.

---

## Task 3: Intake routing — guide counsellors to the right path for memo-level intake

**Why:** `POST /api/kb/analyse` caps `new_chunks` at 3 per call. This is correct for targeted corrections (a single fact update). But a full counsellor memo generates 8-12 meaningful chunks. The cap is invisible — counsellors submitting a full memo lose ~70% of the intelligence without any warning.

The right fix is two-part: (a) preserve the cap for targeted use, (b) surface routing guidance in the admin UI so counsellors choose Track Builder for memo-level intake.

**Files:**
- Modify: `api/services/llm.py` (analyse_kb_input prompt)
- Modify: `web/` (KnowledgeUpdateTab — add routing note to the UI)

- [ ] **Step 1: Raise the new_chunks cap from 3 to 6 in the analyse prompt**

In `api/services/llm.py` line ~125, change:
```python
"        - new_chunks: self-contained facts not present in existing excerpts.\n"
'          Maximum 3 chunks. Prefer fewer, denser chunks. Leave chunk_id as "".\n'
```
to:
```python
"        - new_chunks: self-contained facts not present in existing excerpts.\n"
'          Maximum 6 chunks. Prefer dense, self-contained chunks. Leave chunk_id as "".\n'
'          If the input is a full counsellor memo covering multiple topics, note that\n'
'          Session Editor is the better intake path for memo-level ingestion.\n'
```

Do **not** change `_MAX_CHUNKS` in `commit_analysis` — the current value of 10 is sufficient headroom.

- [ ] **Step 2: Add intake routing note to KnowledgeUpdateTab**

In `web/components/admin/KnowledgeUpdateTab.tsx`, insert the routing note as a **full-width
block between the description paragraph and the two-panel layout** (after the `<p className="text-sm text-gray-500 mb-4 ...">` line and before the `<div className="flex gap-6">`).

**Placement rationale:** Full-width ensures it's seen before the counsellor selects an
input mode. Placing it inside the left column (above the toggle) would hide it from
counsellors who already switched to file mode.

**Visual treatment (DESIGN.md tokens):**

The component must accept an `onNavigateToSession?: () => void` prop from the parent admin shell.
Wire it so clicking "Session Editor" switches the admin tab.

```tsx
<div className="mb-4 rounded-lg bg-[#F6F1E8] border border-[#D8D0C4] px-4 py-3 text-sm text-[#5F6B76]">
  <span className="font-medium text-[#1F2937]">For full memos:</span>{" "}
  if your note covers multiple employers or tracks,{" "}
  {onNavigateToSession ? (
    <button
      onClick={onNavigateToSession}
      className="font-medium text-[#0F766E] underline-offset-2 hover:underline focus:outline-none focus:ring-2 focus:ring-[#0F766E] rounded"
    >
      use Session Editor
    </button>
  ) : (
    <span className="font-medium text-[#0F766E]">use Session Editor</span>
  )}{" "}
  to extract per-entity update cards. Use this tab for targeted fact
  corrections and employer updates.
</div>
```

The prop is optional (`?`) so existing callers without routing context don't break.

**Dismissibility decision:** The note is permanently visible (no close button, no localStorage state).
It is visually recessive (muted text on canvas background) so it does not intrude on power users
who know the workflow.

- Background: `#F6F1E8` (canvas) — warm, visually recedes behind the main input
- Border: `#D8D0C4` (line) — quiet separation, not a card silhouette
- Text: `#5F6B76` (muted) — subdued, not competing with the primary action
- Emphasis: `#1F2937` (ink) for the lead word, `#0F766E` (teal) for the destination name
- No icon, no colored border-left, no blue — keeps chrome quiet per DESIGN.md

**Do NOT use Tailwind `blue-*` tokens** — the component currently uses `blue-600` throughout
(pre-existing drift from DESIGN.md). The routing note must use design system tokens directly.
See Task 3 Step 4 (below) for the full component token alignment fix.

- [ ] **Step 3: Verify Session Editor (SessionInbox.tsx) copy is clear for full-memo intake**

`SessionInbox.tsx` (line 85) is the actual full-memo intake path — it calls `POST /api/sessions`
which runs `generate_session_intents` with no chunk cap, handling multi-entity memos and producing
per-entity update cards. Track Builder is single-track only and is not appropriate for full memos.

Verify the Session Editor UI copy explicitly states it accepts full counsellor research notes.
If ambiguous, update to: "Paste full counsellor research notes here — the system will extract
individual update cards for each employer and track mentioned."

- [ ] **Step 4: Align KnowledgeUpdateTab and SessionInbox to design system tokens**

Both components use Tailwind `blue-*` tokens. DESIGN.md specifies `#0F766E` (teal) as the primary
action color. The routing note added in Step 2 uses correct DESIGN.md tokens — the surrounding
component must match or it reads as two conflicting design systems.

Token substitution map (mechanical find-and-replace in both files):

| Tailwind token | DESIGN.md replacement |
|----------------|-----------------------|
| `bg-blue-600` | `bg-[#0F766E]` |
| `hover:bg-blue-700` | `hover:bg-[#0A5C57]` (10% darker) |
| `focus:ring-blue-400` | `focus:ring-[#0F766E]` |
| `border-blue-200 bg-blue-50` (diff fields) | `border-[#D8D0C4] bg-[#F0E7DB]` |
| `bg-blue-100 text-blue-700` (career type tag) | `bg-[#CCEBE8] text-[#0F766E]` |
| `text-blue-400` (bullets) | `text-[#0F766E]` |
| `border-blue-100 bg-blue-50/60` (SessionInbox form) | `border-[#D8D0C4] bg-[#F6F1E8]` |

Files: `web/components/admin/KnowledgeUpdateTab.tsx`, `web/components/admin/SessionInbox.tsx`

**Note:** This is a visual-only change. No logic or API calls are affected.

- [ ] **Step 5: Fix mobile stacking and touch target on the routing note button**

In `KnowledgeUpdateTab.tsx`, change the two-panel container from fixed percentage widths to a
responsive flex layout:

```tsx
// Before:
<div className="flex gap-6">
  <div className="w-2/5 flex flex-col gap-4">   {/* left */}
  <div className="w-3/5">                         {/* right */}

// After:
<div className="flex flex-col sm:flex-row gap-6">
  <div className="sm:w-2/5 flex flex-col gap-4"> {/* left */}
  <div className="sm:w-3/5">                      {/* right */}
```

For the `onNavigateToSession` button inside the routing note: since it sits inline in a sentence,
it cannot be 44px tall without breaking text flow. Compensate with generous horizontal padding and
ensure the focus ring is visible:
```tsx
className="font-medium text-[#0F766E] underline-offset-2 hover:underline focus:outline-none focus:ring-2 focus:ring-[#0F766E] focus:ring-offset-1 rounded px-0.5"
```
This is acceptable for a desktop-primary admin tool where touch targets are advisory, not required.
Document this tradeoff with a code comment.

---

## Task 4: Filename allowlist — add parentheses

**Why:** `Career_Services_Meeting_Memo (1).docx` (one of the five demo memos) fails upload with HTTP 400 because `(` and `)` are not in the allowlist regex `^[A-Za-z0-9._\- ]+$`. Easy, low-risk fix.

**Files:**
- Modify: `api/routers/ingest_router.py`

- [ ] **Step 1: Add parentheses to the allowlist**

In `api/routers/ingest_router.py` line 19, change:
```python
_FILENAME_ALLOWLIST = re.compile(r"^[A-Za-z0-9._\- ]+$")
```
to:
```python
_FILENAME_ALLOWLIST = re.compile(r"^[A-Za-z0-9._\-()\[\] ]+$")
```

Square brackets included for symmetry. The security intent (no path traversal, no shell metacharacters) is preserved — these characters are safe in filenames.

- [ ] **Step 2: Add parametrized test cases**

Add to the existing `_sanitize_filename` test suite:
- `"Career_Services_Meeting_Memo (1).docx"` → passes
- `"report [final].pdf"` → passes
- `"file; rm -rf /"` → still rejected
- `"file$(cmd).txt"` → still rejected

---

## Task 5: Validate profile field names in commit-analysis (from TODOS.md Now)

**Why:** The `ALLOWED_PROFILE_FIELDS` frozenset exists in `kb_router.py` but `commit_analysis` doesn't enforce it. An LLM echo or a crafted client request can write arbitrary YAML keys into profile files, corrupting structured data.

**Files:**
- Modify: `api/routers/kb_router.py`

- [ ] **Step 1: Add field-name validation in `commit_analysis` before writing profile updates**

In `commit_analysis()` (around line 960+), before the YAML write loop, add:

```python
# Validate profile field names against allowlist
for slug, field_map in req.profile_updates.items():
    invalid_fields = set(field_map.keys()) - ALLOWED_PROFILE_FIELDS
    if invalid_fields:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown profile fields for '{slug}': {sorted(invalid_fields)}. "
                   f"Allowed: {sorted(ALLOWED_PROFILE_FIELDS)}"
        )
```

Similarly, validate `employer_updates` field names against `ALLOWED_EMPLOYER_FIELDS` (already imported from `employer_store`).

- [ ] **Step 2: Inspect and validate `session_router.py` write path**

Codex identified `session_router.py` line 247 as a second YAML write path that may lack allowlist
validation. Inspect this path: if it writes profile keys, apply the same `ALLOWED_PROFILE_FIELDS`
guard before writing. If it writes session-only fields (intents, metadata), document why it is out
of scope and leave a comment.

- [ ] **Step 3: Add test coverage**

In the kb_router tests:
- Commit with a valid field set → 200
- Commit with an unknown field name (`"hallucinated_field"`) → 422 with clear message
- Commit with an empty field map → 200 (no-op, not an error)

**Note on existing behavior:** The current `commit_analysis` loop already checks `ALLOWED_PROFILE_FIELDS`
with skip+warn (not 422). The behavior is already safe. This task closes the TODO and adds test coverage
to lock in the guarantee.

Mark this item Done in `TODOS.md` once shipped.

---

## Task 6: File upload size limit (from TODOS.md Next)

**Why:** A large PDF (50MB academic report) would block a FastAPI worker for minutes while parsing and embedding. No size guard exists on either `/api/ingest` or `/api/kb/analyse`.

**Files:**
- Modify: `api/routers/ingest_router.py`
- Modify: `api/routers/kb_router.py`

- [ ] **Step 1: Add `Content-Length` guard to `/api/ingest` before reading**

`await file.read()` buffers the entire body into memory before any post-read check can fire, so a
post-read `len()` check does not protect worker memory. Guard via the `Content-Length` header before
reading:

In `ingest_router.py`, before `content = await file.read()`:
```python
from starlette.requests import Request

_MAX_UPLOAD_BYTES = settings.max_upload_bytes  # defined in config.py

content_length = request.headers.get("content-length")
if content_length and int(content_length) > _MAX_UPLOAD_BYTES:
    raise HTTPException(
        status_code=413,
        detail=f"File exceeds maximum upload size ({_MAX_UPLOAD_BYTES // (1024*1024)}MB)."
    )
content = await file.read()
```

Add `request: Request` as a parameter to the endpoint. Add `max_upload_bytes: int = 10 * 1024 * 1024`
to `config.py` settings so both routers share one constant.

- [ ] **Step 2: Add `Content-Length` guard to `/api/kb/analyse` before reading**

Apply the same pattern in `kb_router.py` `analyse()` endpoint:
```python
content_length = request.headers.get("content-length")
if content_length and int(content_length) > settings.max_upload_bytes:
    raise HTTPException(status_code=413, detail="File exceeds maximum upload size (10MB).")
raw_bytes = await file.read()
```

Note: `Content-Length` can be absent (chunked transfer encoding). The guard only fires when the
header is present — this is acceptable for an internal admin tool where uploads go through the
browser or curl (both send Content-Length for file uploads).

- [ ] **Step 3: Add tests**

Test that uploading a mock file with content length > 10MB returns 413 from both endpoints.

Mark this item Done in `TODOS.md` once shipped.

---

## Task 7: structured: field sync after prose edits (from TODOS.md Next)

**Why:** A counsellor editing `salary_range_2024` in the profile editor does not update `structured.salary_min_sgd` / `structured.salary_max_sgd`. These fields diverge silently. Once the `structured:` block is used for filtering or sorting (planned), stale values will produce wrong results.

**Files:**
- Modify: `api/services/career_profiles.py` (or the save path in `kb_router.py`)
- Modify: `api/services/llm.py` (optionally, derive structured fields from prose)

- [ ] **Step 1: Add a `_derive_structured_from_prose` helper**

In `api/services/career_profiles.py`, add:

```python
import re

def _derive_structured_fields(profile: dict) -> dict:
    """Attempt to extract structured numeric fields from prose, without overwriting
    manually set values that are already valid.

    Returns a partial dict of structured fields to merge."""
    structured = dict(profile.get("structured") or {})

    # Parse salary_range_2024: "SGD 80–160K" or "SGD 80K–160K base"
    salary_prose = str(profile.get("salary_range_2024") or "")
    match = re.search(r"(\d[\d,]+)\s*[K–-]+\s*(\d[\d,]+)\s*[Kk]?", salary_prose)
    if match:
        lo = int(match.group(1).replace(",", ""))
        hi = int(match.group(2).replace(",", ""))
        # Normalize K suffix: if values < 1000, multiply by 1000
        if lo < 10000:
            lo *= 1000
        if hi < 10000:
            hi *= 1000
        if lo > 0 and hi >= lo:
            structured.setdefault("salary_min_sgd", lo)
            structured.setdefault("salary_max_sgd", hi)

    return structured
```

Use `setdefault` so manually entered values are not overwritten.

- [ ] **Step 2: Call `_derive_structured_fields` at both profile write paths**

There is no standalone profile editor write path — `GET /api/kb/career-profiles` is read-only.
The two write paths that produce or update live profile YAML are:

1. **`publish_draft()`** in `api/services/track_drafts.py` — call `_derive_structured_fields` on
   `published_payload` before writing the YAML file, merging derived structured values in.

2. **`commit_analysis()` profile update loop** in `api/routers/kb_router.py` — after applying
   `profile_updates` field changes, call `_derive_structured_fields(profile)` and merge the result
   before writing.

Use `setdefault` in both paths so manually set `salary_min_sgd`/`salary_max_sgd` values are
never overwritten by prose parse.

- [ ] **Step 3: Add tests**

- `"SGD 80–160K"` → min=80000, max=160000
- `"SGD 80K–160K base"` → same
- `"TBD"` → no numeric fields extracted, existing structured values unchanged
- Manually set `salary_min_sgd=99999` → not overwritten by prose parse

Mark this item Done in `TODOS.md` once shipped.

---

## Acceptance criteria for the sprint

| # | Item | Done when |
|---|------|-----------|
| 1 | DOCX table extraction | `parse_file()` on any of the five demo memos returns text containing pipe-delimited career progression rows and compensation rows |
| 2 | Salary levels + visa notes schema | `generate_track_draft` on the UOB memo populates `salary_levels` with at least 2 entries; GGV memo populates `visa_pathway_notes` with Tech.Pass/PR detail |
| 3 | Intake routing | KnowledgeUpdateTab shows intake guidance note; Session Editor copy explicitly says "paste full research notes" |
| 4 | Filename allowlist | `Career_Services_Meeting_Memo (1).docx` uploads without error |
| 5 | Commit-analysis validation | `POST /api/kb/commit-analysis` with unknown field name returns skip+warn (existing) AND test locks in the guarantee; session_router.py write path inspected and either guarded or documented |
| 6 | Upload size limit | File with `Content-Length > 10MB` returns 413 from both `/api/ingest` and `/api/kb/analyse` before body is buffered |
| 7 | Structured field sync | Editing `salary_range_2024` in a profile and saving updates `structured.salary_min_sgd`/`salary_max_sgd` |

## TODOS.md updates on completion

When this sprint ships, mark Done in `TODOS.md`:
- `Validate profile field names in commit-analysis` (Task 5)
- `File upload size limit — /api/ingest and /api/kb/analyse` (Task 6)
- `structured: values diverge from prose field edits after profile editor write` (Task 7)

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | DONE_WITH_CONCERNS | 4 issues: Task 6 post-read check ineffective, Task 7 write path missing, Task 3 wrong component, Task 5 session_router gap |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR (PLAN) | 10 issues found, all resolved; 9 amendments applied |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | CLEAR (FULL) | score: 3/10 → 9/10, 5 decisions made |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**LATEST REVIEW SNAPSHOT (2026-04-12, HEAD `a0c5bba`):**
- `plan-eng-review`: DONE. Architecture notes were the `SalaryLevel` typed model, explicit `publish_draft()` field wiring, and `TrackReferenceDetail` update. Code-quality notes were `settings.max_upload_bytes` in `config.py`, `_derive_structured_fields` at both write paths, and no `_MAX_CHUNKS` change. Test notes were backwards compat, `publish_draft` round-trip, and integration smoke.
- `plan-design-review`: clean. Score 3/10 → 9/10, 5 decisions made.
- Codex tensions to keep aligned with implementation: Task 6 should use a pre-read `Content-Length` guard, Task 7 should target the real profile write paths, Task 3 should route to `SessionInbox.tsx`, and Task 5 should extend `session_router.py`.

**CODEX:** Task 6 pre-read Content-Length guard, Task 7 write path reframed, Task 3 routing to SessionInbox.tsx, Task 5 session_router.py extension.

**DESIGN:** Routing note placement (full-width, between header and panels), DESIGN.md token alignment for KnowledgeUpdateTab + SessionInbox (blue-600 → teal), clickable "Session Editor" button prop, mobile stacking (flex-col sm:flex-row), dismissibility resolved as permanent.

**VERDICT:** ENG + DESIGN REVIEWS CLEARED — ready to implement.
