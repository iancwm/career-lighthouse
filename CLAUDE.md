
## Environment settings

CLAUDE_ENABLE_STREAM_WATCHDOG=false

## Pre-flight Checklist

Before changing code, check these first:

- Are filesystem writes going to a path that is actually writable in both Docker and local dev?
- Are admin/API calls using the real same-origin path and the right auth header?
- Is every LLM response treated as untrusted input until it is parsed and validated server-side?
- Have prompts, models, schemas, and allowlists been kept in sync?
- Are imports and helper functions at the right scope for Python and the current module layout?
- Does any background write, index, or analysis step need a timeout, retry, or non-fatal fallback?

## Documentation Map

- `docs/README.md` is the index for the docs tree.
- Active specs live in `docs/schema/` and `docs/llm_hardening/`.
- Completed sprint specs and planning docs move into `docs/archived/`.

## Implementation Learnings

- Filesystem writes are fragile. Docker bind mounts, repo files, `knowledge/`, `logs/`, and local worktrees can be read-only or permission-limited, so expect create/unlink failures and verify writable paths early.
- Admin/API requests need the real auth path. Keep calls on the same origin, send `X-Admin-Key` deliberately, and check CSP/proxy wiring before chasing app logic.
- LLM output is untrusted input. Strip code fences, preserve outer JSON arrays, allow repair helpers to return lists, and validate slugs plus field allowlists before any write.
- Schema drift breaks things quietly. Keep prompts, models, and allowlists aligned, especially for commit/analysis payloads.
- Import timing and helper choice matter. Prefer top-level imports and the correct client/helper accessor when Python starts failing in surprising ways.
- Long-running writes need guardrails. Session analysis, Qdrant writes, and ingestion should have timeout, retry, or non-fatal fallback behavior.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health

## Design System
Always read DESIGN.md before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match DESIGN.md.
