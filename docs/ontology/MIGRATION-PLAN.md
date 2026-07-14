# Ontology & Metadata Layer — Migration Plan

Status: plan only, no production code changed. Complements `ONTOLOGY-DESIGN.md` §4/§10.

## 1. Compatibility contract

These invariants hold throughout every phase below, not just at the end:

1. `knowledge/employers/*.yaml`, `knowledge/career_profiles/*.yaml`, `knowledge/alumni/*.yaml`, `knowledge/alumni_company_links/**/*.yaml`, `knowledge/source_ledger/*.yaml`, `knowledge/draft_tracks/*.yaml`, `knowledge/career_tracks.yaml` are **never written to by ontology code**. Every write in this design goes to a new path (`knowledge/entities/`, `knowledge/claims/`, `knowledge/evidence/`) or extends an existing ledger record additively (source metadata fields — see §2).
2. `EmployerDetail.structured: dict[str, Any]` keeps its type. No new validation is attached to the generic `PUT /api/kb/employers/{slug}` path. Counsellors using `EmployerFactsTab.tsx`'s existing facts editor are unaffected.
3. `Fact` (`models_facts.py`), `fact_store.list_facts()`, `facts_router.py`'s `/api/kb/facts` and `/api/kb/facts/grouped` endpoints are unmodified and continue to serve exactly what they serve today.
4. Every existing test in `api/tests/` passes, unmodified, at every phase. This is checked mechanically (`pytest api/tests/`) as a gate before each phase lands, not just at the end of Milestone 1.
5. No environment variable that already has a meaning changes meaning. New stores get new env vars (`ONTOLOGY_ENTITIES_DIR`, `ONTOLOGY_CLAIMS_DIR`, `ONTOLOGY_EVIDENCE_DIR`), following the exact naming/override pattern `SOURCE_LEDGER_DIR` already established (`api/services/source_ledger.py:33`) and wired through `runtime_paths.py`'s `runtime_storage_targets()` the same way.

## 2. Source ledger extension — the one existing store this design touches

`SourceLedgerStore._normalize_record()` (`api/services/source_ledger.py:78`) already defaults every field it doesn't find on disk (`record.get("lifecycle") or "active"`, etc.). The migration adds the new `SourceMetadata` fields (`source_kind`, `publisher_name`, `publisher_entity_id`, `published_at`, `jurisdiction`, `coverage_geographies`, `coverage_entity_ids`, `authority_tier`, `contains_personal_data`, `content_hash`) to that same defaulting function, each defaulted to `"unknown"` / `None` / `[]` / `False` as appropriate.

- **Forward compatibility**: old ledger records on disk (no new keys present) load fine — `_normalize_record` fills in defaults, exactly as it does today for records written before `record_version` existed.
- **Backward compatibility**: if this change is rolled back, ledger records that *do* have the new keys (written after the change shipped) still load fine under the old `_normalize_record` — extra YAML keys are simply ignored by `dict.get()`-based field access. No data loss, no crash, in either direction. This is the standard "additive optional field" migration and needs no converter script.
- **`content_hash` backfill** is the one field worth a small opportunistic script (`scripts/backfill_source_content_hash.py`) that computes a hash from the already-stored source text (via Qdrant chunk payloads, since raw source text isn't retained outside chunks) for existing ledger records — but this is a `Later` nice-to-have, not required for Milestone 1 acceptance, since `content_hash` has no reader in Milestone 1's scope (it exists on the model for future dedup use).

## 3. New-store rollout (no migration needed — these stores start empty)

`knowledge/entities/`, `knowledge/claims/`, `knowledge/evidence/`, `knowledge/ontology/` do not exist today, so there is no legacy data to migrate into them at ship time. "Migration" for these stores means the *decision to start populating them*, which is gated behind the `ontology.extraction_enabled` feature flag from `ONTOLOGY-DESIGN.md` §10, not a data transformation.

Phased enablement:

| Phase | What ships | What's live | Rollback if needed |
|---|---|---|---|
| 0 | `models_ontology.py`, store classes, unit tests | Nothing — no router wires to them | Revert the PR; no data was ever written |
| 1 | Source ledger extension (§2) | New fields present on new/updated ledger records only | Revert the PR; extra YAML keys are inert |
| 2 | `/extract-claims` endpoint, feature-flagged off | Endpoint exists but returns 404/disabled unless flag is on | Flip flag off; endpoint becomes a no-op |
| 3 | Flag on for one pilot employer (config-gated, not code-gated — e.g. `ontology.pilot_employer_slugs: ["stripe_singapore"]` in `kb.yaml`) | Real `Claim`/`Evidence` files start appearing under `knowledge/claims/`, `knowledge/evidence/`, all with `review_status="proposed"` until a counsellor reviews them | Remove the slug from the pilot list; stop new writes. Existing claim files are inert (nothing reads `review_status="proposed"` claims outside the review UI) and can be left in place or deleted — see §4 |
| 4 | Wider rollout | All employers | N/A — by this point the pipeline has been validated against `EVALUATION-PLAN.md` |

## 4. Rollback instructions

**Any phase, at any time:**

1. Set `ontology.extraction_enabled: false` in `api/cfg/kb.yaml` (or remove pilot slugs from `ontology.pilot_employer_slugs`). This immediately stops new `Claim`/`Evidence` writes. No code deploy required if the flag is read at request time (recommended) rather than at process start.
2. If a code rollback is also needed (e.g., a bug in the extraction pipeline itself, not just "we want to pause"): revert the ontology router/service PRs. Because no existing router or store is modified by this design (§1, invariant 1), reverting is a clean `git revert` with no merge-conflict risk against unrelated concurrent work on `employer_store.py`/`alumni_store.py`/etc.
3. **Data left behind by a rollback is safe to leave in place.** `knowledge/claims/*.yaml` and `knowledge/evidence/*.yaml` files are not referenced by any code path outside the ontology router/services being rolled back — no other part of the system reads them (they do not feed `fact_store.list_facts()`, employer context blocks, or chat retrieval). If a clean slate is preferred, `rm -rf knowledge/claims knowledge/evidence knowledge/entities` is safe and reversible only in the sense that the extraction work would need to be re-run — no other store's integrity depends on these directories existing.
4. **Source ledger extension rollback** (§2): safe to leave the extra fields in place even if the code reading them is reverted, per the backward-compatibility note in §2. No cleanup required.

## 5. Explicit non-migrations (matches spec Non-Goals)

- **No backfill of `structured.facts` → `knowledge/claims/`.** The ~125 employer YAMLs and their embedded facts (e.g. the Stripe example in `REPOSITORY-ASSESSMENT.md` §6) stay exactly as they are. `fact_store.list_facts()` keeps reading them from their current location.
- **No forced migration of `EmployerFactsTab.tsx`'s existing facts-editing UI** onto the new claim model. Both surfaces coexist; TODOS.md gets an entry proposing eventual convergence once the pilot proves the new pipeline is at least as good, but that decision and its execution plan are explicitly out of scope for Milestone 1.
- **No alumni-store or employer-store schema changes.** Both remain untouched; the new `Entity` records for organizations/people are additive shadow records pointed at the legacy slugs via `external_ids`, not replacements.

## 6. Operational checklist before flipping the pilot flag (Phase 3)

- [ ] `pytest api/tests/` green, including new ontology test files.
- [ ] `EVALUATION-PLAN.md`'s gold dataset run against the pipeline at least once, with the unsupported-claim rate reviewed by a human (not just a passing threshold — this is a new pipeline, first real run deserves eyes-on review).
- [ ] `ONTOLOGY_ENTITIES_DIR`/`ONTOLOGY_CLAIMS_DIR`/`ONTOLOGY_EVIDENCE_DIR` confirmed writable in the target environment (Docker bind mount or local dev), per the CLAUDE.md pre-flight checklist item on filesystem writes — checked with the same `ensure_writable_directory()` helper `runtime_paths.py` already uses for every other storage root, added to `runtime_storage_targets()`.
- [ ] `X-Admin-Key` verified on the new `/extract-claims` and claim-commit endpoints via a live request, not just code inspection (per CLAUDE.md's admin/API pre-flight item).
- [ ] Pilot employer slug confirmed to have a source ledger record with `source_kind`/`authority_tier` populated (so the prompt actually receives authority context, not `"unknown"` defaults for every field).
