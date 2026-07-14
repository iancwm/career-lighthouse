# Ontology & Metadata Layer — Design

Status: design only, no production code changed. Builds on `REPOSITORY-ASSESSMENT.md`.
Ontology schema version for everything below: `ontology_version: "1.0"`.

## Guiding constraint

Everything here is additive. Nothing in this document renames, retypes, or removes an existing field on `Fact`, `EmployerDetail`, `AlumniDetail`, `DraftTrackDetail`, or the source ledger record. The new stores (`entities/`, `claims/`, `evidence/`) live alongside the existing YAML stores and are populated by new code paths only. See MIGRATION-PLAN.md for the compatibility contract this implies.

## 1. Proposed Pydantic models

New module: `api/models_ontology.py` (mirrors the existing `models_facts.py` / `models_kb.py` / `models_employers.py` split — one module per bounded concept, consistent with the repo's current layout).

### 1.1 Entity

```python
EntityType = Literal[
    "organization", "organization_unit", "programme", "role",
    "career_track", "person", "institution", "source_document",
]
EntityStatus = Literal["active", "merged", "archived"]

class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ontology_version: str = "1.0"
    entity_id: str                      # stable, content-derived — see §3
    entity_type: EntityType
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    status: EntityStatus = "active"
    parent_entity_id: str | None = None  # e.g. OrganizationUnit -> Organization
    geography: str | None = None         # e.g. "SG", "global"
    external_ids: dict[str, str] = Field(default_factory=dict)  # e.g. existing employer slug
    created_at: datetime
    updated_at: datetime
```

`external_ids` is the bridge field: `{"employer_slug": "stripe_singapore"}` or `{"alumni_slug": "jane_teoh"}` lets a new `Entity` point back at the legacy YAML record it was derived from, without the legacy store needing to know entities exist. This is how Milestone 1 avoids touching `employer_store.py`/`alumni_store.py` at all.

### 1.2 Source metadata extension

`SourceLedgerStore`'s current record (`api/services/source_ledger.py:78` `_normalize_record`) already has `doc_id`, `filename`, `lifecycle`, `uploaded_at`, `chunk_count`, `superseded_by`, `record_version`. Extend it — additively, all new fields optional with safe defaults — rather than replacing it:

```python
SourceKind = Literal[
    "official_employer_page", "institutional_report", "job_posting",
    "counsellor_note", "alumni_interview", "student_report",
    "secondary_article", "unknown",
]
AuthorityTier = Literal[
    "official_primary", "institutional_primary", "direct_participant",
    "internal_counsellor", "secondary_reputable", "anecdotal", "unknown",
]

class SourceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ontology_version: str = "1.0"
    source_id: str                       # == existing `doc_id` / ledger `filename` key
    filename: str
    source_kind: SourceKind = "unknown"
    publisher_name: str | None = None
    publisher_entity_id: str | None = None   # Entity.entity_id, organization type
    published_at: date | None = None
    retrieved_at: datetime
    jurisdiction: str | None = None
    coverage_geographies: list[str] = Field(default_factory=list)
    coverage_entity_ids: list[str] = Field(default_factory=list)
    authority_tier: AuthorityTier = "unknown"
    contains_personal_data: bool = False
    content_hash: str | None = None
    lifecycle: Literal["active", "superseded", "archived"] = "active"
    superseded_by: str | None = None
```

Storage decision: **do not create a new `knowledge/source_metadata/` directory.** Add these fields directly into the existing per-source YAML record under `knowledge/source_ledger/{filename}.yaml`, defaulted at read time by `_normalize_record()` exactly the way `lifecycle`/`chunk_count`/`record_version` are defaulted today. This keeps one ledger, not two competing ones, and `SourceLedgerStore.upsert_record()`/`archive_record()`/history-snapshot behavior is preserved unchanged. `SourceMetadata` becomes a *validation view* over the ledger record (`SourceMetadata.model_validate(ledger.get_record(filename))`), not a separate persisted object.

### 1.3 Evidence

```python
SupportType = Literal["directly_supports", "partially_supports", "contradicts", "context_only"]

class EvidenceLocator(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int | None = None
    paragraph: int | None = None
    section: str | None = None
    character_start: int | None = None
    character_end: int | None = None

class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ontology_version: str = "1.0"
    evidence_id: str                     # deterministic hash — see §3
    source_id: str                       # -> SourceLedger filename / doc_id
    excerpt: str = Field(min_length=1, max_length=2000)
    locator: EvidenceLocator = Field(default_factory=EvidenceLocator)
    support_type: SupportType
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime
    trace_id: str | None = None

    @field_validator("excerpt")
    @classmethod
    def _excerpt_not_a_summary(cls, v: str) -> str:
        # Cheap heuristic guard, not a proof: reject empty/whitespace-only
        # excerpts. True "must be copied, not generated" enforcement happens
        # by construction in the extraction pipeline (Stage 1 emits excerpts
        # from character offsets into the source text, never from the LLM's
        # own words) — see §5.
        if not v.strip():
            raise ValueError("excerpt must be non-empty source text")
        return v
```

### 1.4 Claim envelope

```python
ClaimType = Literal[
    "application_window", "recruitment_stage", "skill_requirement",
    "compensation_observation", "employment_relationship",
    "education_relationship", "programme_offering", "sponsorship_policy",
]
AssertionStatus = Literal[
    "asserted", "inferred", "estimated", "reported", "contradicted", "superseded",
]
ReviewStatus = Literal["proposed", "approved", "rejected"]

class ClaimScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    geography: str | None = None
    organization_unit_id: str | None = None
    programme_id: str | None = None
    role_id: str | None = None
    seniority: str | None = None
    candidate_segment: str | None = None
    academic_year: str | None = None

class ClaimValidTime(BaseModel):
    model_config = ConfigDict(extra="forbid")
    valid_from: date | None = None
    valid_until: date | None = None

class ClaimObservationTime(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observed_at: date | None = None
    recorded_at: datetime

class ClaimConfidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    extraction: float = Field(ge=0.0, le=1.0)
    evidence_strength: float = Field(ge=0.0, le=1.0)
    source_reliability: float = Field(ge=0.0, le=1.0)

class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ontology_version: str = "1.0"
    claim_id: str
    claim_type: ClaimType
    subject_entity_id: str
    object_entity_id: str | None = None
    payload: "ClaimPayload"              # discriminated union — see below
    scope: ClaimScope = Field(default_factory=ClaimScope)
    valid_time: ClaimValidTime = Field(default_factory=ClaimValidTime)
    observation_time: ClaimObservationTime
    assertion_status: AssertionStatus = "inferred"
    confidence: ClaimConfidence
    evidence_ids: list[str] = Field(min_length=1)   # cannot be empty — see acceptance criteria #3
    lifecycle: Literal["active", "superseded", "archived"] = "active"
    superseded_by: str | None = None
    review_status: ReviewStatus = "proposed"
    trace_id: str | None = None

    @field_validator("evidence_ids")
    @classmethod
    def _requires_evidence(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("a claim must cite at least one evidence_id")
        return v
```

`payload` is typed per `claim_type` via a Pydantic discriminated union keyed on `claim_type`, exactly like `IntentCard.diff`'s `field_validator`-based dispatch (`models_kb.py:392`) but using Pydantic v2's native `Discriminator` instead of a manual `if/elif` — cleaner, and the repo already depends on Pydantic v2 (`ConfigDict` usage confirms this).

### 1.5 Milestone-1 typed claim payloads

```python
DatePrecision = Literal["exact_date", "month", "quarter", "approximate"]

class ApplicationWindowPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_type: Literal["application_window"] = "application_window"
    programme_id: str | None = None
    opens_on: date | None = None
    closes_on: date | None = None
    date_precision: DatePrecision = "approximate"
    intake_year: int | None = None

StageType = Literal[
    "application", "online_assessment", "recruiter_screen",
    "technical_interview", "case_interview", "assessment_centre",
    "final_interview", "offer", "other",
]
Modality = Literal["online", "phone", "video", "onsite", "hybrid", "unknown"]

class RecruitmentStagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_type: Literal["recruitment_stage"] = "recruitment_stage"
    process_id: str | None = None
    sequence: int | None = None
    stage_name: str = Field(min_length=1)
    stage_type: StageType
    modality: Modality = "unknown"
    duration_minutes: int | None = None
    assessed_competencies: list[str] = Field(default_factory=list)

ClaimPayload = Annotated[
    Union[ApplicationWindowPayload, RecruitmentStagePayload],
    Field(discriminator="claim_type"),
]
```

The remaining six payload types (`skill_requirement`, `compensation_observation`, `employment_relationship`, `education_relationship`, `programme_offering`, `sponsorship_policy`) are specified in the initial spec's field lists and should be added to the same `ClaimPayload` union in later milestones — the envelope, storage, and review pipeline do not change per payload type, only the union membership grows.

## 2. Storage layout

```
knowledge/
  entities/
    organization/{entity_id}.yaml
    organization_unit/{entity_id}.yaml
    programme/{entity_id}.yaml
    role/{entity_id}.yaml
    career_track/{entity_id}.yaml
    person/{entity_id}.yaml
    institution/{entity_id}.yaml
  claims/
    {claim_id}.yaml
  evidence/
    {evidence_id}.yaml
  ontology/
    entity_types.yaml
    claim_types.yaml
    vocabularies.yaml
```

Rationale, directly answering the spec's "recommend the least disruptive layout, do not split every record into a separate file without evaluating operational complexity":

- **One file per claim and one file per evidence record**, not one big JSONL or one file per subject entity. Reasoning: claims are produced by an LLM extraction pass one at a time, reviewed one at a time (Stage 5 → existing `IntentCard` review UI), and superseded one at a time. The existing **alumni company-links** store already proves this pattern works at the repo's actual scale (a few thousand employer/alumni records, not millions) — `knowledge/alumni_company_links/{slug}/{stamp}-{link_id}.yaml` is one file per link-event, and `AlumniEntityStore.list_links()` just globs the directory. Claims should do the same: `atomic_yaml_write(claims_dir / f"{claim_id}.yaml", claim.model_dump())`, no subdirectory-per-subject needed because `claim_id` is globally unique and every store operation (`list_claims_for_entity`, `list_claims_by_type`) is a directory scan with a filter, matching how `fact_store.list_facts()` already scans-and-filters rather than indexing.
- **One directory per entity type** under `entities/`, not one flat directory. Reasoning: `entity_type` is immutable and known at creation time (unlike claim scope, which varies), so partitioning by type avoids a full-directory scan when the common query is "list all Organizations." This mirrors the existing top-level split between `knowledge/employers/` and `knowledge/career_profiles/` — the codebase already partitions by kind at the directory level, so this is consistent, not novel.
- **No history subdirectory for claims/evidence.** Unlike employer/profile/alumni YAML (which are *mutable* — a PUT overwrites the file, so a `{slug}_history/` snapshot is needed to recover the prior version), claims are **append-only by construction**: superseding a claim means writing a *new* claim file with `lifecycle=active` and setting the old claim's `superseded_by` to the new `claim_id` (a field-level update to the old file, not a full rewrite of meaning). The full history is therefore always present in `knowledge/claims/` itself — no separate history directory needed. This is a deliberate simplification versus the employer/profile/alumni pattern, justified because claims are the one record type in this design that is never truly mutated, only ever added or marked superseded.
- **`knowledge/ontology/*.yaml` are hand-maintained config, not data.** They follow the exact pattern of `api/cfg/kb.yaml`'s `employers.allowed_update_fields` — a YAML list read at import time into a `frozenset`, used both by extraction prompts (to tell the LLM what's allowed) and by validators (to reject anything else). `entity_types.yaml` and `claim_types.yaml` are largely redundant with the `Literal[...]` types in `models_ontology.py` in Milestone 1 (Python is the source of truth while the type set is small and code-reviewed); they earn their keep once claim/entity types need to be extended without a code deploy, which is explicitly out of scope for Milestone 1. Recommendation: **create the three files now with the Milestone-1 values, but do not wire runtime code to read them yet** — keeps the directory layout stable for later milestones without adding a second source of truth to keep in sync on day one.

## 3. Identifier strategy

- **`entity_id`**: `{entity_type}-{deterministic_slug}`, e.g. `organization-stripe_singapore`, `person-jane_teoh`. The slug component reuses `services.shared_yaml.safe_slug()` over `canonical_name`, with the same collision-suffix escalation already implemented for alumni (`alumni_store._preferred_profile_slug`, `api/services/alumni_store.py:547`): try `safe_slug(name)` first; if taken by a *different* canonical entity, append a disambiguator (`geography`, then a short hash of `canonical_name`). This is explicitly **not** "must not depend solely on display names" in the strict sense the spec words it — the spec's requirement is that identity not be *fragile* to renames, not that the string can't be name-derived at creation time. Mitigation: `aliases: list[str]` absorbs renames going forward (old name becomes an alias, `entity_id` never changes after creation), and `external_ids` anchors back to the pre-existing employer/alumni slug so a rename in the legacy YAML store does not orphan the entity record.
- **`evidence_id`**: `evidence-{sha1(source_id|character_start|character_end|excerpt)[:16]}`. Deterministic and idempotent — re-running extraction over the same source text produces the same `evidence_id`, so re-extraction does not create duplicate evidence rows. Directly modeled on `alumni_store._event_signature()` (`api/services/alumni_store.py:430`, `hashlib.sha1(...).hexdigest()[:12]`).
- **`claim_id`**: `claim-{claim_type}-{sha1(subject_entity_id|object_entity_id|claim_type|payload_json|scope_json)[:16]}`. Deterministic over the claim's *meaning*, not its metadata (confidence/evidence/timestamps are excluded from the hash) — this makes claim upsert idempotent the same way `_link_id_for_payload()` makes company-link upsert idempotent, and lets Stage 4 (verification) cheaply detect "is this a duplicate of an existing claim" by recomputing the hash before doing any semantic comparison.
- **`source_id`**: unchanged — continues to be the source ledger's `filename` key. No new ID scheme introduced for sources; `SourceMetadata.source_id == filename`.

All IDs are plain strings, filesystem-safe (`safe_slug`-compatible), and stable across process restarts without a central counter or database sequence — consistent with the file-backed, no-new-infrastructure constraint.

## 4. Schema migration strategy

Summarized here; full detail (including rollback) is in `MIGRATION-PLAN.md`. The short version:

1. New models and stores are added; nothing existing is touched.
2. `ontology_version: "1.0"` is stamped on every new record. Future breaking changes to `Entity`/`Claim`/`Evidence` bump this field and ship a converter, following the same "stamp + converter" idea the repo already uses informally via `record_version` timestamps in the source ledger.
3. No backfill of `structured.facts` into `claims/` in Milestone 1 (spec non-goal: "full migration of all structured facts"). A later milestone can write a one-off script (`scripts/backfill_claims_from_facts.py`, mirroring the existing `scripts/validate_profiles.py` / `AlumniEntityStore.backfill_legacy_alumni()` precedent) once the claim-type coverage is broad enough to represent what `structured.facts` currently holds.

## 5. Extraction pipeline changes

Implement the spec's five stages as a new module, `api/services/ontology_extraction.py`, called from a **new, narrow entry point** rather than by modifying `extract_facts_from_prose`. Rationale: `extract_facts_from_prose` is wired into `employers_router.py`'s `/extract-facts` endpoint and the `EmployerFactsTab.tsx` UI today; changing its output shape would break that UI without a coordinated frontend change, which is out of scope for "no broad migration" per the spec. Milestone 1 instead adds `POST /api/kb/employers/{slug}/extract-claims` (new endpoint, additive) that runs the new pipeline over the same input (`notes` + `source_documents`) and returns `Claim`/`Evidence` proposals without touching the existing endpoint.

Stage-by-stage:

- **Stage 1 (mention extraction)**: one LLM call, prompt requires the model to return `character_start`/`character_end` offsets into the *exact* input text it was given. The server then slices `excerpt = notes[character_start:character_end]` itself — the excerpt is never taken verbatim from the LLM's JSON output, only the offsets are. This is what makes `Evidence.excerpt` "copied from source material, not generated" enforceable in practice, not just an aspiration in the prompt.
- **Stage 2 (entity resolution)**: for each mention, look up candidates by exact/fuzzy name match against existing `Entity` records of the mention's inferred type (reusing `alumni_store._normalise_name_key()`-style normalization). If exactly one high-confidence match, `resolution_status="matched"`. If zero matches, `resolution_status="proposed_new"` and a *draft* `Entity` is included in the response (not written). If multiple plausible matches, `resolution_status="ambiguous"` and the claim-extraction stage **skips** that mention rather than guessing — directly satisfying "do not silently create entities when multiple plausible matches exist."
- **Stage 3 (claim extraction)**: a second LLM call, given only the resolved entities + evidence excerpts (not the full source text), producing typed `ClaimPayload` objects. Scope fields are populated from what Stage 1/2 already know (e.g., a mention tagged as coming from a Singapore job posting gets `scope.geography="SG"` from the source's `coverage_geographies`, not from the LLM guessing) wherever possible, so scope-narrowing is a server-side default rather than solely an LLM instruction — this is the concrete mechanism behind "an alumni interview should not automatically become an employer-wide claim."
- **Stage 4 (verification)**: deterministic, non-LLM checks first (evidence_ids non-empty, subject/object entity_ids resolve, claim_id hash doesn't already exist as an *active* claim with different payload → flag as `contradicted` candidate rather than silently duplicating), then one LLM call for the softer checks (does the evidence text plausibly support this claim). Verification failures downgrade `assertion_status` (never delete) and are surfaced to the reviewer, not silently dropped.
- **Stage 5 (review proposal)**: reuse the existing `IntentCard` machinery. Add `"claim"` as a fourth `IntentCard.domain` value alongside `"employer" | "track" | "alumni"`, with `diff` validated by a new `validate_intent_card_diff` branch that accepts a `Claim` (Milestone 1: `review_status` starts at `"proposed"`; approving the card in the existing SmartCanvas review flow sets `review_status="approved"` and writes the claim file — rejecting sets `review_status="rejected"` and the claim is written for audit but excluded from all read paths). This reuses the exact commit discipline already enforced for employer/track/alumni cards instead of inventing a parallel review UI.

## 6. Prompt changes

- `api/cfg/prompts.yaml` gets three new prompt keys: `ontology_mention_extraction`, `ontology_claim_extraction`, `ontology_claim_verification` — following the existing naming and `.format(...)`-templated style (see `alumni_extraction`'s use of `{allowed_alumni_fields}` for the precedent of injecting an allowlist into the prompt text).
- Every prompt in this family is given the source's `authority_tier` and `source_kind` (from the now-extended source ledger record) as part of its user-turn context, mirroring how `analyse_kb_input` already injects `CURRENT EMPLOYER FACTS` — this is what satisfies spec/acceptance-criterion 5 ("source authority metadata is available to extraction prompts"). Concretely: `f"SOURCE AUTHORITY: {source_kind}, tier={authority_tier} (see rubric below — weight anecdotal/internal_counsellor sources conservatively)"`.
- `extract_facts_from_prose`'s existing raw f-string prompt (`api/services/llm.py:1868`, not currently in `prompts.yaml`) is left untouched in Milestone 1 (see §5 rationale) but is flagged in TODOS.md as a follow-up to migrate into `prompts.yaml` for consistency once the new pipeline has proven itself — not a Milestone 1 requirement, listed here only so it isn't lost.

## 7. API changes

All new endpoints go under the existing `/api/kb` prefix with the existing `Depends(require_admin_key)` pattern (`api/dependencies.py:11`), consistent with `facts_router.py`/`employers_router.py`. New router: `api/routers/ontology_router.py`.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/kb/entities` | List entities, filterable by `entity_type`, `status` |
| `GET` | `/api/kb/entities/{entity_id}` | Single entity |
| `GET` | `/api/kb/claims` | List claims, filterable by `claim_type`, `subject_entity_id`, `review_status`, `lifecycle` (mirrors `facts_router.list_facts_endpoint`'s filter-param style) |
| `GET` | `/api/kb/claims/{claim_id}` | Single claim, with resolved evidence inlined |
| `GET` | `/api/kb/evidence/{evidence_id}` | Single evidence record |
| `POST` | `/api/kb/employers/{slug}/extract-claims` | New Stage 1-4 pipeline entry point (§5); returns proposed `IntentCard`s, does not persist |
| `POST` | `/api/kb/session/{session_id}/claims/{card_id}/commit` | Reuses the session commit path; sets `review_status="approved"|"rejected"` and writes the claim file |

No existing endpoint's request/response shape changes. `facts_router.py` and `employers_router.py` are untouched.

## 8. Admin UI implications

Deliberately deferred beyond a minimal read-only surface, consistent with the spec's non-goal "ontology management UI":

- `SmartCanvas.tsx`'s existing card-review surface needs one new card-type renderer for `domain="claim"` (analogous to the existing alumni-card renderer added for the alumni pipeline per CHANGELOG's "Card-native alumni staging flow" entry) — this is required for Stage 5 to actually be usable by a counsellor, not optional polish.
- A **read-only** "Claims" tab/table (list + filter, no create/edit UI) is useful for verifying Milestone 1 end-to-end but is not required for the acceptance criteria and can be a thin wrapper over `GET /api/kb/claims` if built at all. No entity-merge UI, no claim-editing UI, no bulk-approve UI in this phase.

## 9. Test strategy

Follow the existing per-store test file convention (`test_employer_store.py`, `test_alumni_store.py`):

- `api/tests/test_models_ontology.py` — Pydantic validation: reject missing `evidence_ids`, reject unknown `claim_type`, reject payload/claim_type mismatch (discriminator failure), reject out-of-range confidence floats, accept minimal valid records. Modeled on `test_models_kb.py`'s allowlist-rejection tests.
- `api/tests/test_entity_store.py`, `test_claim_store.py`, `test_evidence_store.py` — CRUD + identifier-determinism tests (same `entity_id`/`claim_id` computed twice from equivalent input → equal; different input → different). Uses the `reset_source_ledger`-style autouse `tmp_path` env-var fixture pattern from `conftest.py`.
- `api/tests/test_ontology_extraction.py` — the Stage 1-5 pipeline against a fixture (see MILESTONE-1.md §"fixture"), asserting: mentions have valid offsets into the source text; ambiguous resolutions do not produce a claim; every produced claim has ≥1 evidence_id whose excerpt is a substring of the fixture source text (this is the automatable half of "evidence excerpts must be copied from source material, not generated" — verified by direct substring containment, not just schema shape).
- `api/tests/test_ontology_router.py` — endpoint-level tests via FastAPI `TestClient`, modeled on `test_kb_router.py`, covering admin-key enforcement, filter params, and the extract-claims → review → commit round trip.
- Existing test suites (`test_employer_store.py`, `test_alumni_store.py`, `test_kb_analyse.py`, full suite) must continue to pass unmodified — this is acceptance criterion 1 and is mechanically checked by running `pytest api/tests/` before/after with no new failures.

## 10. Rollout sequence

1. Land `api/models_ontology.py` + validation tests (no runtime wiring). Zero risk — pure addition, unused by any router.
2. Land `EntityStore`/`ClaimStore`/`EvidenceStore` services + their tests. Still zero runtime risk — nothing calls them yet.
3. Extend `SourceLedgerStore`'s normalize/upsert to accept (optionally) the new `SourceMetadata` fields, defaulted when absent. Existing ledger records continue to load unchanged (all new fields optional).
4. Land the extraction pipeline (§5) behind the new `/extract-claims` endpoint. Feature-flaggable via a `kb.yaml` toggle (`ontology.extraction_enabled: false` by default) so it can ship dark and be exercised in staging before counsellors see it.
5. Wire the `SmartCanvas.tsx` claim-card renderer and flip the feature flag for one pilot employer/track.
6. Expand claim-type coverage (`skill_requirement`, `compensation_observation`, etc.) and evaluate against `EVALUATION-PLAN.md`'s gold dataset before wider rollout.

## 11. Risks and trade-offs

- **Two "facts" systems running in parallel** (`structured.facts` and `knowledge/claims/`) for an unknown duration. Mitigated by treating `structured.facts` as strictly legacy/read-only-going-forward from the moment `/extract-claims` ships for a given employer, communicated via `TODOS.md`, but this is a process discipline risk, not a code-enforced one — nothing stops a counsellor from continuing to use `EmployerFactsTab.tsx`'s old flow. Explicitly deferring the UI decision of "hide the old facts tab" is a trade-off Milestone 1 accepts.
- **One-file-per-claim at scale**: fine at hundreds-to-low-thousands of claims (matches current employer/alumni counts, ~125 employers observed in `knowledge/employers/`), but directory-scan-based `list_claims()` will degrade linearly. Acceptable for Milestone 1's scope (two claim types, one pilot); an index file (`knowledge/claims/_index.yaml`, updated on write) is the natural next step if/when scan latency becomes visible, not built preemptively.
- **Discriminated-union payload adds Pydantic-v2-specific complexity** (`Annotated[Union[...], Field(discriminator=...)]`) that the rest of the codebase's `dict[str, Any]`-heavy models don't use. Justified because it is the actual mechanism the spec asks for ("must use a typed Pydantic payload... do not retain unrestricted dict[str, Any]"), and Pydantic v2 is already a hard dependency.
- **Server-computed excerpt offsets (§5) assume the LLM is given exactly the text it's asked to offset into.** If a future chunking pass (like `analyse_kb_input`'s `_collect_chunked_results`) splits long input before this pipeline sees it, offsets must be rebased to the *original* document, not the chunk — a real bug class if not handled carefully. Milestone 1's fixture is short enough to avoid chunking; this must be revisited before claim extraction is applied to long source documents.

## 12. Features explicitly deferred (mirrors spec's Non-Goals, restated for traceability)

OpenMetadata; RDF/OWL/SPARQL; graph database; full historical-facts migration; automatic claim approval; automated narrative-field deletion; ontology management UI; claim-level public student search; institution-wide governance; `entity_types.yaml`/`claim_types.yaml` runtime wiring (files created, not read by code yet); remaining six claim payload types beyond `application_window`/`recruitment_stage`; migrating `extract_facts_from_prose`'s prompt into `prompts.yaml`.
