# Docs Index

This directory holds active sprint docs plus archived sprint history.

## The Only Update Paths

Keep repo documentation updates in one of these three places:

- `docs/` for sprint specs, working notes, and archived sprint artifacts
- `TODOS.md` for the active backlog
- `CHANGELOG.md` for significant shipped feature changes

## How To Use It

- Put active sprint work in the `docs/` root
- Move completed sprint docs into `docs/archived/`
- Put new or changing backlog items in `TODOS.md`
- Put user-visible shipped changes in `CHANGELOG.md`
- Avoid creating new top-level documentation files unless they are one of the three paths above

## Layout

- `docs/` root contains active sprint docs only
- `docs/archived/` contains completed sprint specs and historical planning docs

## Current State

- `docs/ontology/` holds the ontology & metadata layer design set for typed claims/evidence/entities: `ONTOLOGY-DESIGN.md` (core models), `MILESTONE-1.md` (M1 scope/acceptance criteria), `MIGRATION-PLAN.md` (rollout phases), `EVALUATION-PLAN.md` (eval suite spec), `GROUNDING-DESIGN.md` (M2 claim injection design, CEO + Eng review complete), and `SPRINT-M2-TASKS.md` (M2 implementation task list). Repository assessment archived at `docs/archived/ontology/REPOSITORY-ASSESSMENT.md`.
- **Milestone 1 has shipped** (all phases in `MILESTONE-1.md` §3's file checklist landed, every §4 acceptance criterion has a passing checked-in test): `Entity`/`Evidence`/`Claim` models and stores (`api/models_ontology.py`, `entity_store.py`, `claim_store.py`, `evidence_store.py`), the additive `SourceMetadata` extension to the source ledger, the Stage 1-4 extraction pipeline (`api/services/ontology_extraction.py`), `api/routers/ontology_router.py`, the `IntentCard(domain="claim")` review path including a dedicated `SmartCanvas.tsx` renderer, and the acceptance-criterion-8 e2e fixture (`test_ontology_e2e_fixture.py`). `ontology.extraction_enabled` defaults to `false` in checked-in `kb.yaml` — the pipeline ships dark.
- **Milestone 2 has shipped** (all P0/P1 tasks and P2 polish tasks in `SPRINT-M2-TASKS.md` landed, all required tests per `GROUNDING-DESIGN.md` passing): `ClaimContextService` (`api/services/claim_context.py`), the VERIFIED CLAIMS prompt injection in `chat_with_context()` (`api/services/llm.py`), `EmployerEntityStore.get_matched_slugs()` fast-path resolution, the entity-id convention fix in `entity_store.py`/`ontology_extraction.py` (P0/Task 0), Langfuse `grounding_*` trace metadata, and the gold eval query (`api/tests/test_grounding_eval.py`, `EVALUATION-PLAN.md` §7). `ontology.grounding_enabled` defaults to `false` in checked-in `kb.yaml` — the pipeline ships dark. Enabling either milestone's flag for a real employer (at least 3 approved claims for a pilot employer, per `GROUNDING-DESIGN.md`'s rollout sequence) is the next decision, not further engineering.
- No active sprint beyond the above. The backlog lives in `TODOS.md`.
- The most recent completed sprint is [SPRINT-SECURITY-RELIABILITY-2026-05-15.md](archived/SPRINT-SECURITY-RELIABILITY-2026-05-15.md) — all 10 security/reliability/test items shipped and archived 2026-05-20.
- Other archived top-level sprint docs include [SPRINT-UX-POLISH-2026-05-10.md](archived/SPRINT-UX-POLISH-2026-05-10.md), [SPRINT-UX-WORKSPACE-CLARITY.md](archived/SPRINT-UX-WORKSPACE-CLARITY.md), and [SPRINT-LAUNCH-READINESS.md](archived/SPRINT-LAUNCH-READINESS.md).
