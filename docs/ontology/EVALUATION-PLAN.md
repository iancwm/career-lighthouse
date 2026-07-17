# Ontology & Metadata Layer — Evaluation Plan

Status: evaluation plan for the shipped ontology implementation. The Milestone 1 minimal fixture and Milestone 2 gold query test are checked in; the full gold-set run and human accuracy report remain pending before pilot enablement.

## 1. Existing evaluation precedent to reuse

The repo already has a gold-fixture evaluation convention, established for KB retrieval quality:

- `api/tests/fixtures/eval_queries.jsonl` — one JSON object per line, each a query plus expected-answer assertions (`expected_employer`, `expected_track`, `should_not_say_no_info`).
- `scripts/sync_langfuse_eval_dataset.py` — syncs the fixture file into a Langfuse dataset for online eval tracking, with a `--dry-run` mode that works without Langfuse credentials.
- `docs/archived/sprint_cq_finish/E1_accuracy_report.md` — a hand-written accuracy report against three real employer-note inputs (Grab, DBS, Accenture) with an explicit ≥80% field-accuracy rubric.

The ontology evaluation plan follows this exact shape rather than introducing a new methodology: a new gold-fixture file, a scoring script, and a written accuracy report, all under the same directories the repo already uses for eval artifacts.

## 2. Gold dataset

New fixture: `api/tests/fixtures/ontology_gold_claims.jsonl`. Each line is one **source document** (not one query) paired with the claims a human reviewer expects the pipeline to produce from it:

```json
{
  "source_id": "goldman-singapore-guide.txt",
  "source_kind": "counsellor_note",
  "authority_tier": "internal_counsellor",
  "text_ref": "demo-data/goldman-singapore-guide.txt",
  "expected_claims": [
    {
      "claim_type": "recruitment_stage",
      "subject_entity_name": "Goldman Sachs Singapore",
      "payload": {"stage_name": "HireVue video interview", "sequence": 2, "stage_type": "recruiter_screen", "modality": "video"},
      "scope": {"organization_unit_id": null, "programme_id": null},
      "must_be_evidence_grounded": true
    }
  ],
  "expected_non_claims": [
    "GS Singapore culture is intense — should NOT become a global Goldman Sachs employer-wide policy claim; source is SG-specific"
  ]
}
```

`expected_non_claims` captures the spec's overgeneralization risks directly (SG-specific → global, one role's process → all roles) as explicit negative test cases, not just positive coverage.

### 2.1 Source material for the initial dataset (spec-required categories → concrete repo files)

| Spec category | Source in this repo |
|---|---|
| Official employer information | `knowledge/employers/goldman_sachs.yaml`, `stripe_singapore.yaml` `notes`/`application_process` fields |
| Counsellor notes | `demo-data/goldman-singapore-guide.txt`, `demo-data/gic-recruiting-guide.txt`, `demo-data/big-four-recruiting.txt` |
| Alumni notes | `demo-data/smu-alumni-paths.txt`, `demo-data/networking-and-coffee-chats.txt` |
| Compensation information | Salary figures embedded in `demo-data/goldman-singapore-guide.txt` and `knowledge/draft_tracks/*.yaml` `salary_range_2024`/`salary_levels` |
| Interview processes | `demo-data/goldman-singapore-guide.txt` (Superday process), `demo-data/consulting-paths.txt` |
| Application windows | `demo-data/goldman-singapore-guide.txt` ("September deadline for summer analyst") |
| Ambiguous organization/programme names | **Real, not constructed**: `knowledge/employers/deloitte.yaml` (slug `deloitte`, tracks `consulting`/`model_validation_risk`) and `knowledge/employers/deloitte_singapore.yaml` (slug `deloitte_singapore`, tracks `management_consulting`/`sustainability_esg`) are two unreconciled production records for what is plausibly one organization (`REPOSITORY-ASSESSMENT.md` §2). This pair is the primary gold-fixture case for entity resolution — the pipeline is expected to return `resolution_status="ambiguous"` for a mention of "Deloitte," not silently pick one, merge them, or create a third record. Secondary, constructed case: "MITB" appears in `stripe_singapore.yaml`'s `application_process` field meaning "Master of IT in Business" — a fixture item should test that this does not collide with an unrelated "MITB" acronym elsewhere, since employer notes freely use programme abbreviations without disambiguation today |
| Contradictory/stale information | Constructed: two source snippets giving different EP-sponsorship guidance for the same employer at different dates, to exercise `assertion_status="contradicted"` and `lifecycle="superseded"` |

Where the spec's category has no natural repo source (ambiguous names, contradictions), the dataset includes **hand-authored fixture text**, clearly marked as synthetic in the fixture file (`"synthetic": true`), rather than waiting for real data to surface these cases. This mirrors how `test_prompt_injection_e2e.py` already uses hand-authored adversarial payloads rather than only real-world ones.

### 2.2 Dataset size and shipped slice

Milestone 1 shipped with a minimal three-entry fixture in
`api/tests/fixtures/ontology_gold_claims.jsonl`: two Goldman positive cases
and one synthetic Deloitte ambiguity case. That slice is enough for the
Milestone 1 acceptance tests, but it is not the full evaluation set.

The evaluation target remains 10-15 source documents covering both
Milestone-1 claim types (`application_window`, `recruitment_stage`) with at
least 3 items per spec category above. Expand the fixture before enabling the
pilot and hand-score the resulting claims.

## 3. Evaluation categories and how each is scored

| Category | Definition | Scoring method |
|---|---|---|
| Entity detection | Did Stage 1 find the mentions a human would find? | Precision/recall of `mention.text` spans against hand-labeled spans in the fixture |
| Entity resolution | Did Stage 2 resolve mentions to the right `entity_id`, or correctly flag ambiguity/new? | Exact match of `resolution_status` + `resolved_entity_id` against fixture expectation. **For the Deloitte/Deloitte Singapore fixture (§2.1), `resolution_status="ambiguous"` is the passing result** — a scorer that rewards a confident merge or a confident single-match here is scoring the wrong behavior |
| Claim extraction | Did Stage 3 produce the expected `claim_type` + core payload fields? | Field-level match against `expected_claims[].payload`, same ≥80% threshold rubric as `E1_accuracy_report.md` |
| Relation accuracy | Is `subject_entity_id`/`object_entity_id` correct? | Exact match against fixture |
| Scope accuracy | Does `scope` correctly narrow (or correctly *not* narrow) per `expected_non_claims`? | Boolean: did the pipeline avoid every listed overgeneralization? |
| Temporal accuracy | Is `valid_time`/`observation_time`/`date_precision` classified correctly (e.g., "September deadline" → `month` precision, not `exact_date`)? | Exact match against fixture |
| Evidence grounding | Is every claim's evidence excerpt an exact substring of the source document? | Automated: `excerpt in source_text` — see `test_ontology_extraction.py` in `ONTOLOGY-DESIGN.md` §9, run here as an eval-time check with a pass rate reported rather than a pytest assertion |
| Duplicate detection | Does Stage 4 recognize a second extraction pass over the same source doesn't create a second identical claim? | Re-run the pipeline twice over the same fixture; assert `claim_id` sets are equal (idempotency, per the deterministic-hash `claim_id` design) |
| Contradiction detection | Does Stage 4 flag the contradictory-source fixture item as `contradicted` rather than silently adding a second `active` claim? | Exact match against the contradiction fixture item's expected `assertion_status` |
| Unsupported-claim rate | % of produced claims whose evidence does NOT actually support them, per human review | Manual review pass over every claim produced from the gold set, logged in the accuracy report (below) |

## 4. Primary quality metric

**% of extracted claims that are valid (schema-passing), correctly scoped (no `expected_non_claims` violations), and directly evidence-grounded (excerpt substring-verified).**

Computed as: `valid_and_grounded_claims / total_claims_produced`, run over the full gold set after every extraction-pipeline change. Target for Milestone 1 sign-off: **≥80%**, matching the field-accuracy bar already established in `E1_accuracy_report.md` for `extract_facts_from_prose` — the new pipeline should not ship at a lower bar than the one it's improving on, and comparing against the same threshold lets the two be compared meaningfully.

## 5. Deliverables

- **Shipped, minimal:** `api/tests/fixtures/ontology_gold_claims.jsonl` and the
  checked-in unit/e2e tests that exercise it.
- **Pending before pilot:** `scripts/eval_ontology_claims.py` to run the full
  Stage 1-4 pipeline and compute the category scores in §3 and the primary
  metric in §4.
- **Pending before pilot:**
  `docs/ontology/ONTOLOGY-E1-ACCURACY-REPORT.md`, written from a real run of
  the expanded gold set rather than speculatively.
- **Optional later:** sync the gold set into the existing Langfuse eval
  dataset infrastructure as `career-lighthouse-ontology-evals`.

## 6. What this evaluation plan deliberately does not cover

Per the spec's non-goals, this plan does not build an ontology-quality dashboard, does not wire evaluation into CI as a blocking gate (the existing pytest suite blocking gate is unaffected — see `MIGRATION-PLAN.md` §1 invariant 4), and does not attempt statistical significance testing given the intentionally small (10-15 item) Milestone-1 gold set. These are reasonable follow-ups once claim-type coverage and real usage volume justify the investment.

## 7. Milestone 2 gold query — grounded chat answers

Per `docs/ontology/SPRINT-M2-TASKS.md` Task 15 (ENG-T7) and `GROUNDING-DESIGN.md`'s
Success Criteria §1: one gold query registered for the claim-injection (grounding)
pipeline, exercised by `api/tests/test_grounding_eval.py` (`@pytest.mark.eval`,
skipped in CI by default — same shape as the `@pytest.mark.integration` tests in
`test_ai_eval.py`, gated on `ANTHROPIC_API_KEY` being set).

| Query | Fixture claims | Expected behavior |
|---|---|---|
| "What are Goldman's interview stages in Singapore?" | 3 approved, non-stale, high-confidence `recruitment_stage` claims for `organization-goldman_sachs`, `scope.geography="SG"` (online application → HireVue video interview → Superday final round) | `chat_with_context()` response contains at least one of `["knowledge base", "per our knowledge base", "based on our records"]` — the VERIFIED CLAIMS block should change model behavior, not just be present in the prompt unused |
| Same query, `claim_context=None` | — (no claims injected) | Response should NOT contain the KB-attribution phrases above — a negative control proving the eval isn't trivially satisfied by every response |

Both assertions are implemented in `TestGroundingEval` in
`test_grounding_eval.py`. The test is deliberately a single gold query at
pilot scope and is skipped unless `ANTHROPIC_API_KEY` is available. It is a
real-LLM eval, not part of the standard 480-passing unit/integration test run.
Expand it alongside the Milestone 1 gold dataset as more claim types and
employers are covered.
