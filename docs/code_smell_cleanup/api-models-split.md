# API Models Split Spec

**Status:** proposed

## Problem

[`api/models.py`](../../api/models.py) has become a catch-all transport schema bag. It mixes chat payloads, KB observability records, track guidance, employer diffs, and validation helpers in one module.

That makes the API surface harder to navigate and increases the chance that unrelated schema changes collide.

## Goal

Split the transport models by domain while preserving import compatibility during the transition.

## In Scope

- Group chat, KB, track, employer, and validation schemas into domain modules.
- Keep the existing API behavior and serialized payloads unchanged.
- Preserve a stable import path while the split lands.

## Not In Scope

- Changing the actual request or response shapes.
- Renaming public fields unless a bug requires it.
- Splitting every Pydantic model into a separate file if smaller domain groups are enough.

## Existing Building Blocks

- `api/models_insights.py` already shows the repo's preferred pattern for domain-specific model files.
- `web/types/facts.ts` is another example of splitting contracts by domain.

## Proposed Shape

- Create domain modules such as `api/models_chat.py`, `api/models_kb.py`, `api/models_tracks.py`, and `api/models_employers.py`.
- Keep `api/models.py` as a thin compatibility barrel during migration.
- Move imports in routers and services to the domain modules once the split is stable.

## Acceptance Criteria

- The models are easier to find by domain.
- No public API payload changes are introduced by the refactor.
- Existing imports continue to work while the repo migrates off the monolith.

## Test Plan

- Run the backend test suite against the new module layout.
- Add import smoke tests so the split does not break packaging.
- Verify the serialized request and response payloads remain unchanged.

## Risks

- A partial split can create duplicate definitions if the barrel file is not managed carefully.
- Mutable defaults should be audited while touching the models, not copied into the new modules.
