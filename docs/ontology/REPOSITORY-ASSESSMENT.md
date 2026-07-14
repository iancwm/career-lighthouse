# Repository Assessment — Ontology & Metadata Layer

Status: assessment only, no production code changed.
Scope: Task 1 of the ontology initial specification. Read-only inspection of the files and directories named in the spec, plus the write paths that feed them.

## 1. Current data models

### 1.1 `Fact` (`api/models_facts.py`)

```
Fact.slug, .type (5-value Literal), .timestamp, .source (3-value Literal),
.confidence (int 1-100), .trace_id, .lifecycle, .deleted, .last_updated,
.source_timestamp, .source_label, .source_type, .superseded_by, .audit_url,
.data: dict[str, Any]
```

- One envelope for five semantically different fact types (`timeline_phase`, `alumni`, `interview_stage`, `compensation`, `skill_requirement`). All type-specific content lives in the untyped `data` dict — exactly the problem the spec names.
- `confidence` is a single 1-100 int. It conflates extraction confidence, evidence strength, and source reliability into one number, per the spec's risk #6.
- `source` is a 3-value enum (`counselor | inferred | direct_from_alumni`) that mixes *how the fact was produced* (inferred vs. direct) with *who reported it* (counselor vs. alumni) — not a clean provenance model.
- There is no `evidence` field and no locator/excerpt. Nothing ties a `Fact` back to the source text it was extracted from beyond the free-text `source_label`/`audit_url`.
- No `scope` concept (geography, role, programme). Facts read as employer-wide or track-wide by construction, because they live inside a single employer's or profile's `structured.facts` list — Singapore-specific vs. global, and role-specific vs. employer-wide, are not distinguishable fields.

### 1.2 `models_kb.py`

Three unrelated model families live here:

- **KB observability** (`DocInfo`, `LLMTraceEntry`, `LLMWorkflowSummary/Detail`, `KBHealthResponse`, `SourceStateSummary`, …) — tracing/health surface, not part of the ontology.
- **Diff-first intent cards** (`IntentCard`, `EmployerCardDiff`, `TrackCardDiff`, `AlumniCardDiff`, `KBAnalysisResult`, `SessionAnalysisResponse`). This is the **existing typed-payload precedent** the ontology spec is asking for: each `*CardDiff` model is a `ConfigDict(extra="forbid")` Pydantic model with an explicit field allowlist, validated in `validate_intent_card_diff()` (`api/models_kb.py:368`) and dispatched by `IntentCard.diff`'s `field_validator`. New claim payloads (Milestone 1) should follow this exact shape: a strict, allowlisted Pydantic model per domain, not a bag of `dict[str, Any]`.
- No entity models (`Organization`, `Person`, `Programme`, etc.) exist anywhere in the codebase today. The closest things are YAML slugs used as ad hoc identifiers (see §3).

### 1.3 `models_employers.py`

- `EmployerDetail.structured: dict[str, Any] = {}` — this is the field that actually holds `structured.facts` on disk. It is **completely unvalidated** on write (see §4).
- `AlumniCompanyLink` (and its input twin `AlumniCompanyLinkInput`) is the **strongest existing precedent for a "claim"** in this codebase: it already has `confidence`, `evidence: list[str]`, `rationale`, `source_type/source_label/source_timestamp`, `lifecycle`, `superseded_by`, and a stable-ish `link_id`. It is subject→object shaped (`alumni_slug` → `company_slug`) with a `relationship`/`role_title`/date-range payload. The Milestone 1 `Claim` envelope should be recognized as a generalization of this model, not an unrelated new concept — reusing its field names (`confidence`, `evidence`, `rationale`, `source_type`, `lifecycle`, `superseded_by`) will minimize churn for reviewers already familiar with alumni links.

### 1.4 `models_tracks.py`

- `DraftTrackDetail`, `TrackRegistryEntry`, `TrackReferenceDetail` — a lightweight `CareerTrack` entity already exists here in embryonic form (`career_tracks.yaml` is a slug/label/status registry). This maps directly to the spec's `CareerTrack` entity type and should be treated as an existing partial implementation, not greenfield.

## 2. Duplicated / drifted fields (observed in production data, not hypothetical)

Two concrete instances found while inspecting `knowledge/employers/stripe_singapore.yaml`:

1. **`singapore_headcount_estimate` appears twice** in the same YAML document — once with a real value (`~150 (ops, eng, data, sales) as of April 2025`), then again a few lines later set to `null`. YAML's last-key-wins means the real value round-trips correctly today, but the file is not internally consistent, and any tool that treats the mapping as ordered (rather than YAML-parsed) will disagree with `yaml.safe_load`.
2. **`counselor_contact` vs. `counsellor_contact`** — `EmployerDetail.counselor_contact` (single "l", `api/models_employers.py:19`) is the model field, but `kb.yaml`'s `employers.allowed_update_fields` (`api/cfg/kb.yaml:24`) lists `counsellor_contact` (double "l"). The employer YAML on disk has both keys, one of which (`counsellor_contact: null`) is dead weight that the allowlist thinks it's writing to but the Pydantic model never reads. This is a live schema-drift bug, not a design risk — it directly demonstrates spec risk #1 ("structurally valid but semantically inconsistent extracted facts") and CLAUDE.md's standing note that "schema drift breaks things quietly."

Recommendation: fix the `counsellor_contact`/`counselor_contact` spelling mismatch as a small, separate PR before or alongside Milestone 1 — it is unrelated to the ontology work but was found during this assessment and is cheap to fix.

## 3. Entity identity today

There is no entity table anywhere. Every "entity" is implicitly identified by a YAML filename stem:

- **Employers**: `knowledge/employers/{slug}.yaml`, slug chosen at creation time by the counsellor/UI (`employers_router.py:59`, `safe_slug_is_valid`). Renames are not supported — the slug *is* the identity and *is* derived from a name choice made once.
- **Alumni**: `knowledge/alumni/{slug}.yaml`, slug derived from `full_name` via `_preferred_profile_slug()` (`api/services/alumni_store.py:547`), with a collision suffix strategy (append `graduation_year`/`current_company`/`current_title`, else a name hash). This is the one place the codebase already tries to solve "stable identifiers must not depend solely on display names" — and it only partially succeeds, since the primary key is still name-derived.
- **Career tracks**: `knowledge/career_tracks.yaml` registry entries + `knowledge/career_profiles/{slug}.yaml`, `knowledge/draft_tracks/{slug}.yaml` — slug again chosen once, no alias tracking.
- **Company links** (`AlumniCompanyLink`): the one place with a deliberately *derived, deterministic* ID — `_link_id_for_payload()` (`api/services/alumni_store.py:450`) hashes `alumni_slug|company_slug|relationship|link_type|start|end` into a slug. This is the closest existing pattern to the spec's "stable identifiers" requirement and is the right template for `evidence_id`/`claim_id` generation (content-derived, not name-derived).

**Implication for identifier strategy**: reuse the `_link_id_for_payload`-style deterministic hash pattern for `entity_id`/`claim_id`/`evidence_id`, but do not reuse "slug = identity" for `Organization`/`Person` entities — see ONTOLOGY-DESIGN.md §3.

## 4. Extraction entry points

| Function | File | Produces | Persists directly? |
|---|---|---|---|
| `extract_facts_from_prose()` | `api/services/llm.py:1850` | List of `Fact`-shaped dicts (ad hoc inline prompt, not in `prompts.yaml`) | **No** — returns preview only |
| `analyse_kb_input()` | `api/services/llm.py:935` | `KBAnalysisResult` (profile/employer field diffs + new KB chunks + already-covered) | No — feeds session review |
| `generate_track_draft()` | `api/services/llm.py:1044` | Draft track YAML fields | No — feeds review |
| `generate_alumni_extraction()` | `api/services/llm.py:1241` | Per-field `confidence`/`evidence`/`rationale` proposals + company-link proposals + candidate matching against `existing_alumni` | No — feeds review |
| `generate_session_intents()` | `api/services/llm.py:1671` | `IntentCard[]` validated against `EmployerCardDiff`/`TrackCardDiff`/`AlumniCardDiff` | No — feeds session review/commit |

Two important asymmetries:

- **`extract_facts_from_prose` is the *least* structured of the five.** It uses a raw f-string prompt (not `prompts.yaml`), has no entity-resolution step, no chunking/merge for long input (unlike `analyse_kb_input`'s `_collect_chunked_results`), and no evidence linkage — the model is simply asked to invent a `slug` per fact. It is also the one whose output shape (`data=f`, i.e. the whole flat fact re-nested under its own `data` key) is the direct cause of the double-nesting defensiveness in `fact_store.py` (`_payload_for_fact`, `api/services/fact_store.py:87`, which explicitly unwraps `payload.get("data")` a second time). This is the extraction path the spec's Stage 1-5 pipeline should replace first — it is both the smallest surface and the buggiest one.
- **`generate_alumni_extraction` is the *most* structured** and is the best existing template for the Stage 1→5 pipeline: it already does candidate-matching against `existing_alumni` (a crude Stage 2 entity-resolution), per-field confidence + evidence + rationale (a crude Stage 3), and returns proposals rather than committing (Stage 5). It does not yet separate mention extraction from resolution from claim generation into distinct outputs, and evidence is a free-text snippet list rather than a located excerpt tied to a `source_id`.

## 5. Review / commit flows

- **Session pipeline** (`session_router.py`, not fully read in this pass but referenced by `generate_session_intents`, `IntentCard`, and TODOS.md's "Card-native alumni staging flow" entry): counsellor notes → `IntentCard[]` (status `pending|committed|discarded`) → counsellor review in `SmartCanvas.tsx` → commit. This is the existing "human-reviewed canonical facts" stage the spec's Stage 5 should plug into. **No extracted claim is auto-approved today** — this matches spec requirement 9 ("No extracted claim should be approved automatically") and should be preserved exactly.
- **Employer facts commit path is different and weaker**: `EmployerFactsTab.tsx` calls `POST /employers/{slug}/extract-facts` (preview only, `employers_router.py:263`), lets the counsellor edit the returned facts client-side, then calls `persistFacts(facts)` and does a **generic `PUT /api/kb/employers/{slug}`** with `structured: {facts: [...]}}` as part of the payload (`EmployerFactsTab.tsx:537-583`, confirmed via `EmployerFactsReplace.test.tsx`). Because `EmployerDetail.structured` is `dict[str, Any]`, **the server does not validate fact shape on write at all** — Pydantic only validates facts when they are *read back* through `fact_store.list_facts()` (which silently drops invalid ones, `fact_store.py:173-183`). This is the biggest concrete gap Milestone 1 needs to close: claims must be validated (and evidence-linked) *before* they can be written, not just filtered on read.

## 6. All locations where facts/claims-adjacent data is persisted

| Store | Path pattern | Format | History mechanism |
|---|---|---|---|
| Employer entity + embedded facts | `knowledge/employers/{slug}.yaml` (`structured.facts[]`) | YAML, whole-file overwrite | `knowledge/employers_history/{slug}/{version}.yaml` snapshot on every write (`employer_store.py:420`, called from `employers_router.py:141`) |
| Career profile + embedded facts | `knowledge/career_profiles/{slug}.yaml` | YAML | `knowledge/career_profiles_history/{slug}/{version}.yaml` |
| Alumni profile | `knowledge/alumni/{slug}.yaml` | YAML | `knowledge/alumni_history/{slug}/{version}.yaml` |
| Alumni company links | `knowledge/alumni_company_links/{slug}/{stamp}-{link_id}.yaml` | YAML, **append-only event log**, not overwrite | Every write is a new file; "current" state = latest active event per `link_id` (`alumni_store.py:717` `list_links`) |
| Source ledger | `knowledge/source_ledger/{safe_filename}.yaml` | YAML, one current record per source | `knowledge/source_ledger_history/{safe_filename}/{record_version}.yaml` |
| Draft/published tracks | `knowledge/draft_tracks/{slug}.yaml`, `knowledge/career_tracks.yaml` | YAML | Journal/log files under `logs/track_publish_*.jsonl` |
| Semantic chunks | Qdrant `knowledge` collection | Vector + payload | No history; lifecycle filtered via `source_ledger` cross-reference at query time (`source_ledger.py:411` `chunk_is_current`) |

**Two storage idioms already coexist**: (a) whole-file overwrite + timestamped history snapshot (employers, profiles, alumni), and (b) append-only per-event files keyed by a deterministic ID (alumni company links). The ontology spec's `knowledge/claims/` and `knowledge/evidence/` stores should use idiom (b) — append-only, one file per claim/evidence record — since claims are inherently event-like (an extraction produces a claim; a review changes its `review_status`/`lifecycle` but a claim is not "the same mutable row" the way an employer profile is). This is elaborated in ONTOLOGY-DESIGN.md §2.

## 7. Backward-compatibility risks

1. **`structured.facts` free-form write path** (§5) means any new validation added to `Fact`/`Claim` models must not break `PUT /api/kb/employers/{slug}` for employers whose `structured` dict does not conform (e.g., legacy or hand-edited entries). Milestone 1 must not change `EmployerDetail.structured`'s type from `dict[str, Any]` — see MIGRATION-PLAN.md.
2. **Double-nesting tolerance**: `fact_store._payload_for_fact` already defends against `data.data` nesting. Any new evidence/claim reader must keep equivalent defensive unwrapping, or existing on-disk `Fact` records (like the Stripe example dumped above, which *is* double-nested) will silently disappear from `list_facts()`.
3. **Fact type Literal is closed** (`Literal["timeline_phase", "alumni", "interview_stage", "compensation", "skill_requirement"]`). New claim types (`application_window`, `recruitment_stage`, …) are additive and do not conflict, but any code that pattern-matches on the existing five values (`employer_store._fact_key_field`, `api/services/employer_store.py:169`) will not recognize new claim types unless explicitly extended — acceptable for Milestone 1 since new claim types are stored separately (see design doc), not appended to `structured.facts`.
4. **Source ledger key is `filename`**, not a durable UUID. Extending it with `authority_tier`/`source_kind`/etc. is additive and safe; nothing currently assumes a fixed field set (`_normalize_record` in `source_ledger.py:78` already coerces unknown/missing keys).
5. **`kb.yaml` allowlists** (`employers.allowed_update_fields`, and implicitly `ALLOWED_ALUMNI_FIELDS`/`ALLOWED_ALUMNI_LINK_FIELDS` referenced in `llm.py` but defined elsewhere — not located in this pass, likely in `models_employers.py` or a constants module) gate what LLM-proposed diffs can touch. Any new claim-type allowlist (`knowledge/ontology/claim_types.yaml`) should follow the same "config file is the single source of truth, code reads it" pattern rather than hardcoding enums in two places (the `counselor_contact`/`counsellor_contact` bug in §2 is exactly what happens when that discipline slips).

## 8. Relevant existing tests

- `api/tests/test_employer_store.py`, `test_alumni_store.py` — entity store CRUD + completeness computation. Pattern to follow for new `EntityStore`/`ClaimStore`/`EvidenceStore` tests.
- `api/tests/test_models_kb.py` — validates `IntentCard`/`*CardDiff` allowlist behavior; direct precedent for testing new typed claim payloads reject malformed input.
- `api/tests/test_kb_analyse.py`, `test_session_intents.py`, `test_alumni_detection.py` — extraction-pipeline behavior tests (prompt → parsed result → validation). Template for the Stage 1-5 extraction pipeline tests.
- `api/tests/test_llm_observability.py` — the only existing test that touches `extract_facts_from_prose` (peripherally, via trace metadata), confirming there is **no dedicated test for `fact_store.py`, `facts_router.py`, or `Fact` model validation today**. This is a gap Milestone 1 should close incidentally by adding tests for the new `Evidence`/`Claim` models next to it.
- `api/tests/conftest.py` — `reset_source_ledger` fixture (`monkeypatch.setenv("SOURCE_LEDGER_DIR", str(tmp_path / "source_ledger"))`) is the established pattern for isolating file-backed stores per test. New `ENTITIES_DIR`/`CLAIMS_DIR`/`EVIDENCE_DIR` env vars should get equivalent autouse fixtures.

## 9. Summary of what already exists vs. what Milestone 1 must add

| Spec requirement | Existing precedent | Gap |
|---|---|---|
| Typed claim payload, allowlisted fields | `EmployerCardDiff`/`TrackCardDiff`/`AlumniCardDiff` (`models_kb.py`) | Not evidence-linked, not scoped, not a generic `Claim` envelope |
| Confidence broken into sub-scores | None — `Fact.confidence` is one int | New `confidence: {extraction, evidence_strength, source_reliability}` |
| Evidence-to-claim linkage | `AlumniCompanyLink.evidence: list[str]` (free text snippets) | No `evidence_id`, no locator, no `source_id` back-reference |
| Stable, non-name-derived entity IDs | `_link_id_for_payload` deterministic hash (alumni links only) | No entity store at all for Organization/Person/Programme/etc. |
| Source authority metadata | `SourceLedgerStore` (lifecycle, chunk_count, history) | No `source_kind`, `authority_tier`, `publisher_*`, `jurisdiction`, `coverage_*` |
| Review-before-commit | `IntentCard` + session pipeline | Already satisfies this; new claims should route through the same pipeline, not around it |
| Scope (geography/role/programme) | None | New `scope` object entirely |
