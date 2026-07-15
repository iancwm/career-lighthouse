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

- Active design work: `docs/ontology/` holds the ontology & metadata layer design set for typed claims/evidence/entities: `ONTOLOGY-DESIGN.md` (core models), `MILESTONE-1.md` (M1 scope/acceptance criteria), `MIGRATION-PLAN.md` (rollout phases), `EVALUATION-PLAN.md` (eval suite spec), `GROUNDING-DESIGN.md` (M2 claim injection design, CEO + Eng review complete), and `SPRINT-M2-TASKS.md` (M2 implementation task list). No production code has shipped from this design set yet. Repository assessment archived at `docs/archived/ontology/REPOSITORY-ASSESSMENT.md`.
- No active sprint beyond the above. The backlog lives in `TODOS.md`.
- The most recent completed sprint is [SPRINT-SECURITY-RELIABILITY-2026-05-15.md](archived/SPRINT-SECURITY-RELIABILITY-2026-05-15.md) — all 10 security/reliability/test items shipped and archived 2026-05-20.
- Other archived top-level sprint docs include [SPRINT-UX-POLISH-2026-05-10.md](archived/SPRINT-UX-POLISH-2026-05-10.md), [SPRINT-UX-WORKSPACE-CLARITY.md](archived/SPRINT-UX-WORKSPACE-CLARITY.md), and [SPRINT-LAUNCH-READINESS.md](archived/SPRINT-LAUNCH-READINESS.md).
