---
created: 2026-05-06
sprint: unified_session_and_quality
---

# Session Pipeline Reliability Scorecard

Closure artifact for Block B of the unified session + quality sprint.

## What this measures

End-to-end reliability of the session-card extraction pipeline across four observable failure modes:

| Dimension | Signal | Where to check |
|---|---|---|
| **JSON parse / repair** | `drop_point = json_parse_or_repair` in workflow detail | TraceExplorerTab → Evidence → Repair |
| **Alumni path decision** | `alumni_path` field in workflow detail | TraceExplorerTab → Evidence → Alumni path |
| **Validation failures** | `drop_point = card_validation` + `validation_summary` | TraceExplorerTab → Evidence → Validation |
| **Append result** | `append_summary` dict | TraceExplorerTab → Evidence → Append |

## How repair failures are preserved

When `generate_session_intents` raises a ValueError caused by JSON parse or repair failure:

1. `session.analysis_workflow["drop_point"]` is set to `"json_parse_or_repair"` (not the generic `"session_intent_generation"`)
2. `session.analysis_workflow["repair"]["applied"]` is set to `True`
3. `session.analysis_workflow["repair"]["failure"]` captures the error message
4. Each repair LLM call is logged to `api/logs/llm_traces.jsonl` with `repair_attempt` and `repair_applied` metadata

The `TraceExplorerTab → Evidence → Repair` section surfaces all of these via `renderKeyValueMap(detail.repair_summary)`.

## Verification run — 2026-05-06

Test: create 3 sessions; inspect workflow detail for each.

| Run | Notes length | Status | Drop point | Repair | Alumni |
|---|---|---|---|---|---|
| Baseline (short) | ~200 chars | ok | — | not applied | skipped_not_alumni_heavy |
| Large (1500+ chars) | ~1800 chars | ok | — | not applied | skipped_not_alumni_heavy |
| Alumni-heavy | ~400 chars + name + company | ok | — | not applied | invoked |

All three runs completed with `drop_point = null` (success), confirming the happy path. Repair evidence fields are available in the Evidence section of TraceExplorerTab for any run that triggers repair.

## Known limitations

- Repair-path failures can only be triggered by injecting malformed model output (not reproducible without a stub model).
- `alumni_path` is only set when the text contains alumni-heavy signals; low-signal notes will show `skipped_not_alumni_heavy`.
- `append_summary` and `validation_summary` are `{}` on success runs — they are populated only on failure paths.
