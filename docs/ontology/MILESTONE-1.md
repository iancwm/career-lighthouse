# Ontology & Metadata Layer — Milestone 1

Status: scope definition only, no production code changed. Restates and consolidates the "first milestone" and "acceptance criteria" sections of the initial spec into an executable, file-level plan, cross-referenced against `ONTOLOGY-DESIGN.md` and `MIGRATION-PLAN.md`.

## 1. Scope (in)

1. **Entity model** — `Entity` Pydantic model (`ONTOLOGY-DESIGN.md` §1.1) + `EntityStore` service (`api/services/entity_store.py`), file-backed under `knowledge/entities/{entity_type}/{entity_id}.yaml`, following the `EmployerEntityStore`/`AlumniEntityStore` singleton pattern (`Singleton` base from `services/shared_yaml.py`).
2. **Source metadata extension** — `SourceMetadata` fields added to `SourceLedgerStore._normalize_record()` (`ONTOLOGY-DESIGN.md` §1.2, `MIGRATION-PLAN.md` §2). No new store; extends the existing one.
3. **Evidence model** — `Evidence`/`EvidenceLocator` Pydantic models + `EvidenceStore` service, file-backed under `knowledge/evidence/{evidence_id}.yaml`.
4. **Claim envelope** — `Claim`/`ClaimScope`/`ClaimValidTime`/`ClaimObservationTime`/`ClaimConfidence` Pydantic models + `ClaimStore` service, file-backed under `knowledge/claims/{claim_id}.yaml`.
5. **Two typed claim payloads** — `ApplicationWindowPayload`, `RecruitmentStagePayload` (`ONTOLOGY-DESIGN.md` §1.5), wired into `ClaimPayload` as a Pydantic discriminated union.
6. **Validation tests** — `test_models_ontology.py`, `test_entity_store.py`, `test_claim_store.py`, `test_evidence_store.py` (`ONTOLOGY-DESIGN.md` §9).
7. **One extraction prompt path** — the Stage 1→4 pipeline (`api/services/ontology_extraction.py`) for exactly the two Milestone-1 claim types, exposed via `POST /api/kb/employers/{slug}/extract-claims`, feature-flagged off by default (`ontology.extraction_enabled` in `kb.yaml`).
8. **Stage 5 wiring** — `IntentCard.domain` gains a `"claim"` value; one new card-type renderer in `SmartCanvas.tsx` so a counsellor can actually approve/reject a proposed claim through the existing review surface.
9. **Fixture demonstrating the full path** — one demo-data source document, run through extraction → review → commit, checked into `api/tests/fixtures/` and exercised by an integration test.

## 2. Scope (out) — restates spec Non-Goals, see `ONTOLOGY-DESIGN.md` §12 for the complete list

No historical `structured.facts` migration; no automatic claim approval; no ontology management UI beyond the one card renderer in #8 above; no graph database or OpenMetadata; no remaining six claim payload types; no `entity_types.yaml`/`claim_types.yaml` runtime wiring (files may be created per `ONTOLOGY-DESIGN.md` §2 but are not read by code).

## 3. File-level deliverable checklist

| File | New/Modified | Purpose |
|---|---|---|
| `api/models_ontology.py` | New | `Entity`, `SourceMetadata`, `Evidence`, `EvidenceLocator`, `Claim`, `ClaimScope`, `ClaimValidTime`, `ClaimObservationTime`, `ClaimConfidence`, `ApplicationWindowPayload`, `RecruitmentStagePayload`, `ClaimPayload` union |
| `api/services/entity_store.py` | New | `EntityStore` singleton — list/get/create by `entity_type`; resolution-candidate lookup by normalized name |
| `api/services/evidence_store.py` | New | `EvidenceStore` singleton — list/get/create; deterministic `evidence_id` computation |
| `api/services/claim_store.py` | New | `ClaimStore` singleton — list/get/create/supersede; deterministic `claim_id` computation; enforces evidence_ids non-empty at write time as a second guard beyond Pydantic |
| `api/services/source_ledger.py` | Modified (additive) | `_normalize_record()` gains the new optional `SourceMetadata` fields with safe defaults |
| `api/services/ontology_extraction.py` | New | Stage 1 (mentions + offsets), Stage 2 (resolution), Stage 3 (claim extraction), Stage 4 (verification). Each LLM call carries an explicit `timeout_seconds` and a defined non-fatal fallback on timeout (§6) — not left to the underlying client's default |
| `api/cfg/prompts.yaml` | Modified (additive) | `ontology_mention_extraction`, `ontology_claim_extraction`, `ontology_claim_verification` prompt keys |
| `api/cfg/kb.yaml` | Modified (additive) | `ontology.extraction_enabled`, `ontology.pilot_employer_slugs` config keys |
| `api/routers/ontology_router.py` | New | `GET /api/kb/entities[/{id}]`, `GET /api/kb/claims[/{id}]`, `GET /api/kb/evidence/{id}`, `POST /api/kb/employers/{slug}/extract-claims` |
| `api/models_kb.py` | Modified (additive) | `IntentCard.domain` literal gains `"claim"`; `validate_intent_card_diff()` gains a `"claim"` branch |
| `api/services/runtime_paths.py` | Modified (additive) | `ONTOLOGY_ENTITIES_DIR`/`ONTOLOGY_CLAIMS_DIR`/`ONTOLOGY_EVIDENCE_DIR` added to `runtime_storage_targets()` |
| `knowledge/ontology/entity_types.yaml`, `claim_types.yaml`, `vocabularies.yaml` | New | Config files, created but not runtime-wired (per scope-out) |
| `web/components/admin/SmartCanvas.tsx` | Modified | New card-type renderer for `domain="claim"` |
| `api/tests/test_models_ontology.py`, `test_entity_store.py`, `test_claim_store.py`, `test_evidence_store.py`, `test_ontology_extraction.py`, `test_ontology_router.py` | New | Per `ONTOLOGY-DESIGN.md` §9 |
| `api/tests/fixtures/ontology_gold_claims.jsonl` | New | Per `EVALUATION-PLAN.md` §2 (a minimal slice — 2-3 items — is sufficient for Milestone 1's fixture demonstration; the full 10-15 item gold set is an evaluation-phase deliverable, not a Milestone-1 blocker) |

## 4. Acceptance criteria — mapped to verification method

| # | Criterion (from spec) | Verification |
|---|---|---|
| 1 | Existing tests continue to pass | `pytest api/tests/` green, zero modified assertions in pre-existing test files |
| 2 | New ontology models reject malformed payloads | `test_models_ontology.py`: unknown `claim_type`, payload/type mismatch, out-of-range confidence, missing required fields all raise `ValidationError` |
| 3 | Claims cannot be created without evidence | `Claim.evidence_ids: list[str] = Field(min_length=1)` + `field_validator` (`ONTOLOGY-DESIGN.md` §1.4) rejects at the Pydantic layer; `ClaimStore.create_claim()` re-checks at the store layer as defense-in-depth; both paths covered in `test_models_ontology.py` and `test_claim_store.py` |
| 4 | Scope fields are preserved through extraction and review | `test_ontology_extraction.py` asserts `Claim.scope` on the Stage 3 output matches the fixture's expected scope; `test_ontology_router.py` asserts the same `scope` object round-trips unchanged through the `IntentCard` commit path (no field silently dropped by `validate_intent_card_diff`'s `"claim"` branch) |
| 5 | Source authority metadata is available to extraction prompts | `ontology_claim_extraction` prompt's user-turn includes `authority_tier`/`source_kind` (`ONTOLOGY-DESIGN.md` §6); asserted by inspecting the constructed prompt text in a unit test (mock the LLM call, assert the string is present) |
| 6 | Application-window and recruitment-stage claims use typed payloads | `ApplicationWindowPayload`/`RecruitmentStagePayload` are the only two members of `ClaimPayload` in Milestone 1; `test_models_ontology.py` asserts a claim with `claim_type="application_window"` and a `RecruitmentStagePayload`-shaped `payload` (i.e., mismatched) fails validation |
| 7 | Existing YAML records remain readable | `test_employer_store.py`, `test_alumni_store.py`, `test_career_profiles.py` (all pre-existing) pass unmodified — see `MIGRATION-PLAN.md` §1; additionally, a regression test loads the actual `knowledge/employers/stripe_singapore.yaml` (double-nested `data.data` fact included) through `fact_store.list_facts()` and asserts the known facts still parse, guarding against any accidental coupling introduced while building the new stores |
| 8 | A fixture demonstrates extraction from source text through reviewed claim proposal | `test_ontology_extraction.py` (or a dedicated `test_ontology_e2e_fixture.py`) runs one demo-data document (e.g. `demo-data/goldman-singapore-guide.txt`'s "September deadline for summer analyst" line) through Stage 1→4, produces an `IntentCard(domain="claim")`, and asserts committing it writes a `Claim` file with `review_status="approved"` and a resolvable `evidence_id`. A second fixture case, over a mention of "Deloitte," asserts Stage 2 returns `resolution_status="ambiguous"` against the real `deloitte.yaml`/`deloitte_singapore.yaml` pair rather than proceeding to a claim (§6) |
| 9 | Implementation includes migration and rollback instructions | `MIGRATION-PLAN.md` (this deliverable set) |
| 10 | No OpenMetadata, graph database, or large infrastructure dependency added | Verified by inspection: no new entries in `api/pyproject.toml` beyond what Milestone 1 needs (none are anticipated — Pydantic, PyYAML, and the existing Anthropic client cover everything in this design) |

## 5. Definition of done

Milestone 1 is complete when every row in §4 has a passing, checked-in test (not just a manual verification), `ontology.extraction_enabled` defaults to `false` in checked-in config, and this document's file-level checklist (§3) is fully implemented. Enabling the pilot flag for a real employer (`MIGRATION-PLAN.md` §3, Phase 3) is a deliberate follow-up decision made after Milestone 1 ships and its checklist (`MIGRATION-PLAN.md` §6) is satisfied — it is not itself part of "done" for this milestone.

## 6. Known risks not resolved by this milestone

These are named in full in `ONTOLOGY-DESIGN.md` §11 and `MIGRATION-PLAN.md` §6; restated here because they affect what "done" means for Milestone 1 specifically:

- **Entity-resolution quality is untested against real ambiguity within Milestone 1's own scope.** `knowledge/employers/deloitte.yaml` vs. `deloitte_singapore.yaml` is a live unreconciled pair (`REPOSITORY-ASSESSMENT.md` §2). Milestone 1's `EntityStore`/Stage 2 resolution logic should be exercised against this pair specifically (via the gold fixture in `EVALUATION-PLAN.md` §2.1) and must return `resolution_status="ambiguous"`, not a confident merge or a silent duplicate. This is now folded into acceptance criterion 8's fixture requirement (§4) rather than left as a general aspiration.
- **Per-stage LLM timeout/fallback behavior is a design gap, not just a deferred nice-to-have** (`ONTOLOGY-DESIGN.md` §5). It must be implemented, not just specified, before Phase 3 (pilot) per `MIGRATION-PLAN.md` §6 — but it is reasonable to land it as part of Milestone 1's `ontology_extraction.py` itself, since untimed LLM calls in a new pipeline are a correctness gap (CLAUDE.md's own pre-flight checklist item), not only an operational one.
- **JSON-repair-vs-discriminator interaction** (`ONTOLOGY-DESIGN.md` §5) needs a concrete decision during implementation of Stage 3, not left to fall out of reusing `_repair_json_output` unchanged.
- **Config flag is not hot-reloadable** (`REPOSITORY-ASSESSMENT.md` §3a) — `ontology.extraction_enabled` takes effect on next restart, not on save. This affects Phase 3 timing (`MIGRATION-PLAN.md` §1) but not Milestone 1 itself, since the flag defaults to off and nothing in Milestone 1 requires fast toggling.
- **Inherited governance debt** (no counsellor auth, no write concurrency protection, open Langfuse egress audit, decorative `contains_personal_data` field) is explicitly **not** Milestone 1's responsibility to fix — the spec's own non-goals exclude "institution-wide data governance" — but per `MIGRATION-PLAN.md` §6 it must be explicitly signed off, not silently assumed acceptable, before Phase 3 enables real counsellor-facing review traffic. Milestone 1 (Phases 0-2: models, stores, source-ledger extension) does not touch any of these risks, since nothing in that scope is reachable by a counsellor or writes claim data from real sources.

## 7. Immediate next step after this document

This spec's own instruction is to stop after producing the five design documents. The concrete next step — not started in this pass — is implementing row 1 of the rollout sequence in `ONTOLOGY-DESIGN.md` §10: land `api/models_ontology.py` and its validation tests only, with no router or service wiring, as the smallest possible first PR.
