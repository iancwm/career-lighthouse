---
description: Analyze the current git diff against TODOs, plan docs, or an optional ad hoc goal and summarize progress before pushing.
---

# /push-changes

Analyze the current repository diff and report how much closer the changes move the project toward a documented sprint goal or an ad hoc task.

## Arguments

- Optional free-form goal text. If present, treat it as the primary ad hoc goal.

## Workflow

1. Confirm you are in the project root and inspect the current git diff.
2. If no arguments were provided, run:

```bash
python3 scripts/push_changes.py
```

3. If arguments were provided, run:

```bash
python3 scripts/push_changes.py --goal "$ARGUMENTS"
```

4. Present the resulting analysis clearly:
   - Diff source and scope
   - Closest matching TODO/spec/plan, or the supplied ad hoc goal
   - Estimated progress lift toward that goal
   - Remaining gaps, especially tests or missing follow-through

## Guardrails

- Do not commit, push, or modify git history.
- Do not fabricate goal alignment. If the diff does not match a repo goal well, say that plainly.
- If the working tree contains unrelated changes, mention that the report reflects the whole current diff.
