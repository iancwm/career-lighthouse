# Ontology & Metadata Layer — Milestone 1

Status: SHIPPED on 2026-07-16. This document is the implementation and acceptance record for Milestone 1; the extraction flag remains off by default pending pilot readiness checks in `MIGRATION-PLAN.md`.

## 1. Scope (in)

1. **Entity model** — `Entity` Pydantic model (`ONTOLOGY-DESIGN.md` §1.1) + `EntityStore` service (`api/services/entity_store.py`), file-backed under `knowledge/entities/{entity_type}/{entity_id}.yaml`, following the `EmployerEntityStore`/`AlumniEntityStore` singleton pattern (`Singleton` base from `services/shared_yaml.py`).
2. **Source metadata extension** — `SourceMetadata` fields added to `SourceLedgerStore._normalize_record()` (`ONTOLOGY-DESIGN.md` §1.2, `MIGRATION-PLAN.md` §2). No new store; extends the existing one.
3. **Evidence model** — `Evidence`/`EvidenceLocator` Pydantic models + `EvidenceStore` service, file-backed under `knowledge/evidence/{evidence_id}.yaml`.
4. **Claim envelope** — `Claim`/`ClaimScope`/`ClaimValidTime`/`ClaimObservationTime`/`ClaimConfidence` Pydantic models + `ClaimStore` service, file-backed under `knowledge/claims/{claim_id}.yaml`.
5. **Two typed claim payloads** — `ApplicationWindowPayload`, `RecruitmentStagePayload` (`ONTOLOGY-DESIGN.md` §1.5), wired into `ClaimPayload` as a Pydantic discriminated union.
6. **Validation tests** — `test_models_ontology.py`, `test_entity_store.py`, `test_claim_store.py`, `test_evidence_store.py` (`ONTOLOGY-DESIGN.md` §9).
7. **One extraction prompt path** — the Stage 1→4 pipeline (`api/services/ontology_extraction.py`) for exactly the two Milestone-1 claim types, exposed via `POST /api/kb/employers/{slug}/extract-claims`, feature-flagged off by default (`ontology.extraction_enabled` in `kb.yaml`). It returns claim proposals, persists idempotent evidence and known-employer entities as needed, and never writes a claim before review approval.
8. **Stage 5 wiring** — `IntentCard.domain` gains a `"claim"` value; one new card-type renderer in `SmartCanvas.tsx` lets a counsellor review a proposed claim. Approval uses the dedicated `POST /api/kb/session/{session_id}/claims/{card_id}/commit` route; rejection uses the existing generic discard route and writes no claim.
9. **Fixture demonstrating the full path** — one demo-data source document, run through extraction → review → commit, checked into `api/tests/fixtures/` and exercised by an integration test.

## 2. Scope (out) — restates spec Non-Goals, see `ONTOLOGY-DESIGN.md` §12 for the complete list

No historical `structured.facts` migration; no automatic claim approval; no ontology management UI beyond the one card renderer in #8 above; no graph database or OpenMetadata; no remaining six claim payload types; no `entity_types.yaml`/`claim_types.yaml` runtime wiring (files may be created per `ONTOLOGY-DESIGN.md` §2 but are not read by code).

## 3. File-level deliverable checklist

| File | New/Modified | Purpose |
|---|---|---|
| `api/models_ontology.py` | New | `Entity`, `SourceMetadata`, `Evidence`, `EvidenceLocator`, `Claim`, `ClaimScope`, `ClaimValidTime`, `ClaimObservationTime`, `ClaimConfidence`, `ApplicationWindowPayload`, `RecruitmentStagePayload`, `ClaimPayload` union |
| `api/services/entity_store.py` | New | `EntityStore` singleton — list/get/create by `entity_type`; resolution-candidate lookup by normalized name |
| `api/services/evidence_store.py` | New | `EvidenceStore` singleton — list/get/create; deterministic `evidence_id` computation |
| `api/services/claim_store.py` | New | `ClaimStore` singleton — list/get/create_claim/supersede; deterministic `claim_id` computation; enforces evidence_ids non-empty at write time as a second guard beyond Pydantic |
| `api/services/source_ledger.py` | Modified (additive) | `_normalize_record()` gains the new optional `SourceMetadata` fields with safe defaults |
| `api/services/ontology_extraction.py` | New | Stage 1 (mentions + offsets), Stage 2 (resolution), Stage 3 (claim extraction), Stage 4 (verification). Each LLM call carries an explicit `timeout_seconds` and a defined non-fatal fallback on timeout (§6) — not left to the underlying client's default |
| `api/cfg/prompts.yaml` | Modified (additive) | `ontology_mention_extraction`, `ontology_claim_extraction`, `ontology_claim_verification` prompt keys |
| `api/cfg/kb.yaml` | Modified (additive) | `ontology.extraction_enabled` global dark-ship flag and reserved `ontology.pilot_employer_slugs` rollout field (the current router does not enforce per-employer gating) |
| `api/routers/ontology_router.py` | New | `GET /api/kb/entities[/{id}]`, `GET /api/kb/claims[/{id}]`, `GET /api/kb/evidence/{id}`, `POST /api/kb/employers/{slug}/extract-claims`, and the dedicated claim-card commit route |
| `api/models_kb.py` | Modified (additive) | `IntentCard.domain` literal gains `"claim"`; `validate_intent_card_diff()` gains a `"claim"` branch |
| `api/services/runtime_paths.py` | Modified (additive) | `ONTOLOGY_ENTITIES_DIR`/`ONTOLOGY_CLAIMS_DIR`/`ONTOLOGY_EVIDENCE_DIR` added to `runtime_storage_targets()` |
| `knowledge/ontology/entity_types.yaml`, `claim_types.yaml`, `vocabularies.yaml` | New | Config files, created but not runtime-wired (per scope-out) |
| `web/components/admin/SmartCanvas.tsx` | Modified | New card-type renderer for `domain="claim"` |
| `api/tests/test_models_ontology.py`, `test_entity_store.py`, `test_claim_store.py`, `test_evidence_store.py`, `test_ontology_extraction.py`, `test_ontology_e2e_fixture.py`, `test_ontology_router.py`, `test_source_ledger_ontology_extension.py` | New | Model, store, extraction, end-to-end, router, and source-ledger coverage described in `ONTOLOGY-DESIGN.md` §9 |
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
| 8 | A fixture demonstrates extraction from source text through reviewed claim proposal | `test_ontology_e2e_fixture.py` runs `demo-data/goldman-singapore-guide.txt` through Stage 1→4, builds an `IntentCard(domain="claim")`, and asserts the dedicated approval route writes a `Claim` file with `review_status="approved"` and a resolvable `evidence_id`. Its Deloitte case, plus the focused cases in `test_ontology_extraction.py`, assert Stage 2 returns `resolution_status="ambiguous"` against the two live Deloitte records rather than proceeding to a claim (§6) |
| 9 | Implementation includes migration and rollback instructions | `MIGRATION-PLAN.md` (this deliverable set) |
| 10 | No OpenMetadata, graph database, or large infrastructure dependency added | Verified by inspection: no new entries in `api/pyproject.toml` beyond what Milestone 1 needs (none are anticipated — Pydantic, PyYAML, and the existing Anthropic client cover everything in this design) |

## 5. Definition of done

Milestone 1 is complete. Every row in §4 has checked-in coverage, `ontology.extraction_enabled` defaults to `false` in checked-in config, and the file-level checklist (§3) is implemented. Enabling the pilot flag for a real employer (`MIGRATION-PLAN.md` §3, Phase 3) remains a deliberate follow-up decision and is not part of Milestone 1's definition of done.

## 6. Known risks not resolved by this milestone

These are named in full in `ONTOLOGY-DESIGN.md` §11 and `MIGRATION-PLAN.md` §6; restated here because they affect what "done" means for Milestone 1 specifically:

- **Entity-resolution quality still needs pilot measurement.** The real Deloitte/Deloitte Singapore ambiguity case is covered by `test_ontology_extraction.py` and `test_ontology_e2e_fixture.py`; Stage 2 returns `resolution_status="ambiguous"` and produces no claim. Broader precision and recall remain evaluation work before wider rollout.
- **Per-stage LLM timeout/fallback behavior is implemented and tested.** Stage 1/3 failures return safe no-proposal results, and Stage 4 timeouts remain `unverified_timeout` rather than being promoted. Target-environment latency and failure-rate measurement remain pilot work.
- **JSON repair and discriminated-union validation are implemented.** Stage 3 calls `call_structured_json()` with `ClaimExtractionResult` validation, so repaired output is still checked against the typed claim payload before it can become a proposal.
- **Config flag is not hot-reloadable** (`REPOSITORY-ASSESSMENT.md` §3a) — `ontology.extraction_enabled` takes effect on next restart, not on save. This affects Phase 3 timing (`MIGRATION-PLAN.md` §1) but not Milestone 1 itself, since the flag defaults to off and nothing in Milestone 1 requires fast toggling.
- **Inherited governance debt** (no counsellor auth, no write concurrency protection, open Langfuse egress audit, decorative `contains_personal_data` field) is explicitly **not** Milestone 1's responsibility to fix — the spec's own non-goals exclude "institution-wide data governance" — but per `MIGRATION-PLAN.md` §6 it must be explicitly signed off, not silently assumed acceptable, before Phase 3 enables real counsellor-facing review traffic. The model/store/source-ledger core does not alter legacy records. The dark extraction path may be reached only when its flag is enabled, persists evidence and known-employer entities idempotently, and still writes no claim until review approval.

## 7. Next step after this milestone

Engineering for Milestone 1 is complete. The next step is pilot readiness: run the remaining migration checklist, seed and review claims for one pilot employer, and decide whether to enable `ontology.extraction_enabled` in staging. Keep the flag off until the operational and governance checks in `MIGRATION-PLAN.md` §6 are signed off.
