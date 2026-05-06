---
created: 2026-05-06
status: verified
---

# F3: Alumni Cards — Four Failure Mode Verification

Closure artifact for Block C (F3) of the unified session + quality sprint.

## Overview

Four failure modes were identified during the alumni cards sprint. This document records their backend coverage and where UI-side verification is needed.

---

## Mode 1 — Hallucinated `matched_slug` downgraded

**Scenario:** LLM claims an alumni card is an update (`is_update=True`, `matched_slug="ghost-slug"`) but the slug doesn't exist in the existing alumni list.

**Backend behaviour:** `_build_alumni_cards()` in `session_router.py` checks the proposed `matched_slug` against `existing_alumni`. If not found, it resets `is_update=False` and `matched_slug=None`, converting the card to a new-card operation.

**Test:** `api/tests/test_alumni_detection.py::test_build_alumni_cards_downgrades_hallucinated_update`
- Asserts `cards[0]["is_update"] is False`
- Asserts `cards[0]["matched_slug"] is None`

**Status: ✅ Covered by unit test**

---

## Mode 2 — `company_links` discrepancy surfaced in commit response

**Scenario:** LLM proposes N company links but only M < N survive validation (e.g. missing required `linkedin_url` field).

**Backend behaviour:** `commit_card()` in `session_router.py` reads `links_attempted` and `links_written` from `_apply_field_updates_to_alumni()`. When `links_attempted > links_written`, the response includes:
- `company_links_attempted: N`
- `company_links_written: M`
- `company_links_warning: "N-M of N company link(s) were dropped due to missing required fields."`

**UI behaviour:** `web/components/admin/SmartCanvas.tsx` reads `data?.company_links_warning` from the commit response and renders it in the notice toast (line 437–438).

**Test:** `api/tests/test_session_router.py::TestAlumniCardCommit::test_commit_alumni_card_surfaces_company_links_discrepancy` (added 2026-05-06)
- Asserts `company_links_attempted == 2`
- Asserts `company_links_written == 1`
- Asserts `company_links_warning` contains "1 of 2"

**Status: ✅ Backend covered by unit test. UI rendering confirmed by code inspection (`SmartCanvas.tsx:437`).**

---

## Mode 3 — Slug collision appends local date

**Scenario:** A new alumni card's inferred slug (e.g. `maya_lim`) already exists in the alumni store.

**Backend behaviour:** `_build_alumni_cards()` detects the collision and appends the session date prefix: e.g. `maya_lim-20260506`.

**Test:** `api/tests/test_alumni_detection.py::test_build_alumni_cards_applies_slug_collision_suffix_and_confidence_defaults`
- Asserts `cards[0]["diff"]["slug"].startswith("maya_lim-")`

**Status: ✅ Covered by unit test**

---

## Mode 4 — Unknown LLM fields in alumni diff rejected, no partial write

**Scenario:** LLM includes unexpected fields (e.g. `unexpected_field`) in an alumni card diff.

**Backend behaviour:**
1. `validate_intent_card_diff()` in `models_kb.py` rejects unknown alumni fields, raising a `ValidationError`.
2. `_apply_field_updates_to_alumni()` in `services/kb_writer.py` checks incoming fields against `ALLOWED_ALUMNI_FIELDS` and skips any not in the allowlist before writing to YAML.

**Tests:**
- `api/tests/test_models_kb.py::test_validate_intent_card_diff_rejects_unknown_alumni_field` — validates that `validate_intent_card_diff` raises ValidationError for `is_update` field not in diff schema.
- `api/tests/test_models_kb.py::test_intent_card_rejects_extra_alumni_diff_fields` — validates that `IntentCard` rejects unexpected diff fields.

**Status: ✅ Covered by unit tests**

---

## Summary

| Mode | Scenario | Backend test | UI verified |
|---|---|---|---|
| 1 | Hallucinated matched_slug → downgraded to new card | ✅ `test_alumni_detection.py` | N/A (backend-only) |
| 2 | company_links discrepancy in commit toast | ✅ `test_session_router.py` (new 2026-05-06) | ✅ `SmartCanvas.tsx:437` |
| 3 | Slug collision → date suffix | ✅ `test_alumni_detection.py` | N/A (backend-only) |
| 4 | Unknown LLM fields rejected, no partial write | ✅ `test_models_kb.py` | N/A (backend-only) |
