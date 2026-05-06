---
created: 2026-05-06
---

# Langfuse Eval Dataset Sync — Operator Guide

## What this does

`scripts/sync_langfuse_eval_dataset.py` upserts the canonical eval fixtures from
`api/tests/fixtures/eval_queries.jsonl` into a Langfuse dataset.

The Langfuse dataset acts as the prompt-and-version scoring source; the repo JSONL
file is the version-controlled truth set. Without a sync path these two can drift.

## When to run

- After adding or editing queries in `eval_queries.jsonl`
- After a major prompt change (to establish a new baseline score)
- After onboarding a new employer/track to verify retrieval quality

## Prerequisites

1. `langfuse` package must be installed:
   ```bash
   cd api && uv add langfuse
   # or: pip install langfuse
   ```
2. The following env vars must be set for live runs:
   - `LANGFUSE_PUBLIC_KEY`
   - `LANGFUSE_SECRET_KEY`
   - `LANGFUSE_HOST` (default: `https://cloud.langfuse.com` — set to self-hosted URL if applicable)

## Usage

### Dry run (no writes — safe without env vars)
```bash
python scripts/sync_langfuse_eval_dataset.py --dry-run
```
Output shows what would be upserted without making any API calls.

### Live upsert
```bash
LANGFUSE_PUBLIC_KEY=pk-... LANGFUSE_SECRET_KEY=sk-... LANGFUSE_HOST=https://cloud.langfuse.com \
    python scripts/sync_langfuse_eval_dataset.py
```

### Custom dataset name
```bash
LANGFUSE_EVAL_DATASET=my-evals python scripts/sync_langfuse_eval_dataset.py
# or:
python scripts/sync_langfuse_eval_dataset.py --dataset-name my-evals
```

## Verification

After running, confirm in the Langfuse UI:
1. Navigate to **Datasets** → `career-lighthouse-evals` (or your custom name).
2. Verify item count matches the number logged by the script.
3. Spot-check 2–3 items: `input.query` should match fixture text; `expected_output` should contain employer/track/flag fields.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | All items upserted (or dry-run) |
| 1 | One or more items failed to upsert |
| 2 | Langfuse not configured and `--dry-run` not passed |

## Dataset schema

Each dataset item has:
- `input.query` — the student question
- `expected_output.expected_employer` — employer name that should appear in the response (optional)
- `expected_output.expected_track` — career track slug that should be resolved (optional)
- `expected_output.should_not_say_no_info` — if true, LLM must not say it lacks information
- `metadata.source` — always `"eval_queries.jsonl"`
- `metadata.index` — 1-based fixture index

## Adding new fixtures

Add a line to `api/tests/fixtures/eval_queries.jsonl`:
```json
{"query": "What is the EP requirement for Stripe?", "expected_employer": "Stripe Singapore", "should_not_say_no_info": true}
```
Then run the sync script to push to Langfuse.
