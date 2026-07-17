# M2 Grounded Answers — Implementation Sprint

Generated from: CEO Review (2026-07-15) + Eng Review (2026-07-15)  
Design doc: `docs/ontology/GROUNDING-DESIGN.md`  
Status: SHIPPED on 2026-07-17. This file records the implementation sequence and the remaining pilot gate.

## Historical dependency order

```
[Tasks 1-2] MILESTONE-1.md edits
    └── unlocks M1 implementation (external sprint)
         └── unlocks [Tasks 3-15] M2 implementation
```

Tasks 3–15 were blocked on M1 shipping first. That dependency is now satisfied.

**Post-M1-ship update (2026-07-16):** M1 shipped. Task 1 was moot because the
shipped `ClaimStore.list_claims_for_entity()` already matches the locked
signature. Task 2 exposed the entity-ID gap and was resolved as Task 0 before
the M2 fast path landed.

---

## P0 — Completed prerequisite (found in post-M1-ship requirements review, 2026-07-16)

| # | ID | Component | Files | Effort (human / CC) | Description |
|---|----|-----------|----|---|---|
| 0 | REVIEW-T1 | `entity_store.py` + `ontology_extraction.py` | `api/services/entity_store.py`, `api/services/ontology_extraction.py` | **DONE** | `EntityStore.create_entity()` now accepts an explicit `entity_id`, `ensure_organization_entity_for_employer()` persists `organization-{employer_slug}`, and Stage 2 resolves known employer names/slugs through that stable ID. The stable-ID path is covered by the existing entity and extraction tests; A&O Shearman and Ernst & Young remain useful pilot fixtures because their display names diverge from their filenames. |

---

## P1 — Shipped

All P1 tasks below landed and are covered by the checked-in backend tests.

| # | ID | Component | Files | Effort (human / CC) | Description |
|---|----|-----------|----|---|---|
| 1 | CEO-T2 | `MILESTONE-1.md` | `docs/ontology/MILESTONE-1.md` | ~10min / ~2min | ~~Lock `ClaimStore.list_claims_for_entity(entity_id: str, review_status: str \| None, lifecycle: str \| None) -> list[Claim]` signature in §3 deliverable table~~ — moot, shipped code already matches this signature (verified 2026-07-16) |
| 2 | CEO-T3 | `MILESTONE-1.md` | `docs/ontology/MILESTONE-1.md` | ~30min / ~5min | ~~Lock `entity_id = f"organization-{employer_slug}"` convention; add an explicit-ID store path~~ — superseded by Task 0, which implemented the convention in `ensure_organization_entity_for_employer()` and the extraction resolver |
| 3 | ENG-T1 | `claim_context.py` | `api/services/claim_context.py` | ~10min / ~5min | Fix field path bugs in coverage formula: `c.extraction_confidence` → `c.confidence.extraction`; `c.valid_until` → `c.valid_time.valid_until` |
| 4 | CEO-T1 | `claim_context.py` | `api/services/claim_context.py` | ~10min / ~2min | Cap claim block at `max_context_chars // 6` (not `// 3`) — `// 3` crowds KB chunks to 3,000 chars at default budget |
| 5 | CEO-T5 | `claim_context.py` | `api/services/claim_context.py` | ~15min / ~3min | Stale caveat: use `max(c.valid_time.valid_until for c in stale_claims if c.valid_time.valid_until)`; fallback to `"outdated"` string if all `valid_until=None` |
| 6 | CEO-T4 | `claim_context.py` | `api/services/claim_context.py` | ~30min / ~5min | Broad `try/except Exception` at `get_claim_context()` boundary → return `ClaimContext(claims=[], coverage_confidence="none")` on any store failure |
| 7 | CEO-T8 + ENG-T3 | `employer_store.py + chat_router.py` | `api/services/employer_store.py`, `api/routers/chat_router.py` | ~1.5h / ~20min | Implemented `get_matched_slugs(active_career_type, query_text)` with strict name/slug-only matching and wired it into `chat_router.py` as the fast-path slug source. The explicit employer-slug entity-ID fix is in place. |
| 8 | ENG-T2 | `chat_router.py` | `api/routers/chat_router.py` | ~5min / ~5min | Tiebreak: `employer_slug = matched_slugs[0] if len(matched_slugs) == 1 else None` |
| 9 | CEO-T7 | `chat_router.py + llm.py` | `api/routers/chat_router.py`, `api/services/llm.py` | ~30min / ~10min | Add to `_call_with_trace()` `trace_metadata`: `grounding_entity_resolved` (bool), `grounding_claims_injected_count` (int), `grounding_coverage_confidence` (str), `grounding_employer_slug` (str \| None) |
| 10 | CEO-T6 | `test_claim_context.py` | `api/tests/test_claim_context.py` | ~20min / ~5min | Unit test: `ontology.grounding_enabled=false` → `ClaimContextService` never instantiated; `chat_with_context()` called with `claim_context=None` |

## P2 — Shipped polish

All P2 tasks below landed. The pilot sequence remains gated by approved claim
data, the real-LLM evaluation, and governance sign-off.

| # | ID | Component | Files | Effort (human / CC) | Description |
|---|----|-----------|----|---|---|
| 11 | CEO-T9 | `chat_router.py` | `api/routers/chat_router.py` | ~5min / ~1min | Lazy-import `ClaimContextService` inside `if grounding_enabled` block (not module top) — prevents startup crash when M1 stores are partially complete |
| 12 | ENG-T4 | `kb.yaml + claim_context.py` | `api/cfg/kb.yaml`, `api/services/claim_context.py` | ~5min / ~5min | Rename config key `grounding.default_geography` → `ontology.grounding_default_geography` |
| 13 | ENG-T5 | `test_claim_context.py` | `api/tests/test_claim_context.py` | ~20min / ~10min | Test: `coverage_confidence="low"` path — all claims stale; caveat string includes year from `c.valid_time.valid_until` |
| 14 | ENG-T6 | `test_claim_context.py` | `api/tests/test_claim_context.py` | ~20min / ~10min | Test: error rescue paths — `yaml.YAMLError` and `FileNotFoundError` both → `coverage_confidence="none"`, no exception propagated |
| 15 | ENG-T7 | `test_grounding_eval.py` | `api/tests/test_grounding_eval.py`, `docs/ontology/EVALUATION-PLAN.md` | ~30min / ~15min | Eval test: VERIFIED CLAIMS block injected → LLM response cites verified fact (asserts presence of claim content in response) |

---

## Remaining pilot gate

Engineering is complete. Before enabling grounding for a real employer, the
operator still needs to seed at least three approved claims, enable the flags
in staging, verify `grounding_claims_injected_count > 0` in Langfuse, run the
gold evaluation, and complete the governance checks in `MIGRATION-PLAN.md`.

## Deferred (TODOS.md)

- **Relevance-ordered claim injection** (Later/P3): sort VERIFIED CLAIMS block by `claim_type` affinity to query intent. Currently injected in file-system order. Deferred from Eng D8 — acceptable at pilot scale (<10 claims/employer).
- **TTL cache for EntityStore/ClaimStore** (Later/P3): already in TODOS.md backlog.

---

## Key spec references

- Entity-id convention gap (Task 0): `GROUNDING-DESIGN.md` §D2/D3 vs. shipped `api/services/entity_store.py` and `api/services/ontology_extraction.py`
- Field path corrections: `GROUNDING-DESIGN.md` §D1
- Ambiguity tiebreak: `GROUNDING-DESIGN.md` §D2  
- Strict entity matching: `GROUNDING-DESIGN.md` §D3
- Config namespace: `GROUNDING-DESIGN.md` §D4
- `active_career_type=None` behavior: `GROUNDING-DESIGN.md` §D9
- Keyword normalization fallback algorithm: `GROUNDING-DESIGN.md` §D10
- Coverage confidence tiers: `GROUNDING-DESIGN.md` (high/medium/low/none definition)
