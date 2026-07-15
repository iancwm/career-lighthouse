# M2 Grounded Answers — Implementation Sprint

Generated from: CEO Review (2026-07-15) + Eng Review (2026-07-15)  
Design doc: `docs/ontology/GROUNDING-DESIGN.md`  
Branch: `main` | Commit: `7e6e973`

## Dependency order

```
[Tasks 1-2] MILESTONE-1.md edits
    └── unlocks M1 implementation (external sprint)
         └── unlocks [Tasks 3-15] M2 implementation
```

Tasks 3–15 are all blocked on M1 shipping first.

---

## P1 — Implement in order

| # | ID | Component | Files | Effort (human / CC) | Description |
|---|----|-----------|----|---|---|
| 1 | CEO-T2 | `MILESTONE-1.md` | `docs/ontology/MILESTONE-1.md` | ~10min / ~2min | Lock `ClaimStore.list_claims_for_entity(entity_id: str, review_status: str \| None, lifecycle: str \| None) -> list[Claim]` signature in §3 deliverable table |
| 2 | CEO-T3 | `MILESTONE-1.md` | `docs/ontology/MILESTONE-1.md` | ~30min / ~5min | Lock `entity_id = f"organization-{employer_slug}"` convention; add `EntityStore.create()` validation note that rejects non-conforming IDs |
| 3 | ENG-T1 | `claim_context.py` | `api/services/claim_context.py` | ~10min / ~5min | Fix field path bugs in coverage formula: `c.extraction_confidence` → `c.confidence.extraction`; `c.valid_until` → `c.valid_time.valid_until` |
| 4 | CEO-T1 | `claim_context.py` | `api/services/claim_context.py` | ~10min / ~2min | Cap claim block at `max_context_chars // 6` (not `// 3`) — `// 3` crowds KB chunks to 3,000 chars at default budget |
| 5 | CEO-T5 | `claim_context.py` | `api/services/claim_context.py` | ~15min / ~3min | Stale caveat: use `max(c.valid_time.valid_until for c in stale_claims if c.valid_time.valid_until)`; fallback to `"outdated"` string if all `valid_until=None` |
| 6 | CEO-T4 | `claim_context.py` | `api/services/claim_context.py` | ~30min / ~5min | Broad `try/except Exception` at `get_claim_context()` boundary → return `ClaimContext(claims=[], coverage_confidence="none")` on any store failure |
| 7 | CEO-T8 + ENG-T3 | `employer_store.py + chat_router.py` | `api/services/employer_store.py`, `api/routers/chat_router.py` | ~1.5h / ~20min | Implement `get_matched_slugs(active_career_type, query_text) -> list[str]` using `_match_by_name_or_slug()` strict helper (name/slug only — no notes/process expansion); wire in `chat_router.py` as fast-path slug source alongside `to_context_block()`. See `GROUNDING-DESIGN.md` §D3 and D9 for spec. |
| 8 | ENG-T2 | `chat_router.py` | `api/routers/chat_router.py` | ~5min / ~5min | Tiebreak: `employer_slug = matched_slugs[0] if len(matched_slugs) == 1 else None` |
| 9 | CEO-T7 | `chat_router.py + llm.py` | `api/routers/chat_router.py`, `api/services/llm.py` | ~30min / ~10min | Add to `_call_with_trace()` `trace_metadata`: `grounding_entity_resolved` (bool), `grounding_claims_injected_count` (int), `grounding_coverage_confidence` (str), `grounding_employer_slug` (str \| None) |
| 10 | CEO-T6 | `test_claim_context.py` | `api/tests/test_claim_context.py` | ~20min / ~5min | Unit test: `ontology.grounding_enabled=false` → `ClaimContextService` never instantiated; `chat_with_context()` called with `claim_context=None` |

## P2 — After P1 lands

| # | ID | Component | Files | Effort (human / CC) | Description |
|---|----|-----------|----|---|---|
| 11 | CEO-T9 | `chat_router.py` | `api/routers/chat_router.py` | ~5min / ~1min | Lazy-import `ClaimContextService` inside `if grounding_enabled` block (not module top) — prevents startup crash when M1 stores are partially complete |
| 12 | ENG-T4 | `kb.yaml + claim_context.py` | `api/cfg/kb.yaml`, `api/services/claim_context.py` | ~5min / ~5min | Rename config key `grounding.default_geography` → `ontology.grounding_default_geography` |
| 13 | ENG-T5 | `test_claim_context.py` | `api/tests/test_claim_context.py` | ~20min / ~10min | Test: `coverage_confidence="low"` path — all claims stale; caveat string includes year from `c.valid_time.valid_until` |
| 14 | ENG-T6 | `test_claim_context.py` | `api/tests/test_claim_context.py` | ~20min / ~10min | Test: error rescue paths — `yaml.YAMLError` and `FileNotFoundError` both → `coverage_confidence="none"`, no exception propagated |
| 15 | ENG-T7 | `test_grounding_eval.py` | `api/tests/test_grounding_eval.py`, `docs/ontology/EVALUATION-PLAN.md` | ~30min / ~15min | Eval test: VERIFIED CLAIMS block injected → LLM response cites verified fact (asserts presence of claim content in response) |

---

## Deferred (TODOS.md)

- **Relevance-ordered claim injection** (Later/P3): sort VERIFIED CLAIMS block by `claim_type` affinity to query intent. Currently injected in file-system order. Deferred from Eng D8 — acceptable at pilot scale (<10 claims/employer).
- **TTL cache for EntityStore/ClaimStore** (Later/P3): already in TODOS.md backlog.

---

## Key spec references

- Field path corrections: `GROUNDING-DESIGN.md` §D1
- Ambiguity tiebreak: `GROUNDING-DESIGN.md` §D2  
- Strict entity matching: `GROUNDING-DESIGN.md` §D3
- Config namespace: `GROUNDING-DESIGN.md` §D4
- `active_career_type=None` behavior: `GROUNDING-DESIGN.md` §D9
- Keyword normalization fallback algorithm: `GROUNDING-DESIGN.md` §D10
- Coverage confidence tiers: `GROUNDING-DESIGN.md` (high/medium/low/none definition)
