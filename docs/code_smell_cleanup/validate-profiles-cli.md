# Validate Profiles CLI Cleanup Spec

**Status:** proposed

## Problem

[`scripts/validate_profiles.py`](../../scripts/validate_profiles.py) reaches into application internals with `sys.path` surgery to import `profile_to_context_block`.

That makes the script brittle outside the repo root and couples a utility script to the repository layout instead of to a proper entrypoint.

## Goal

Make the profile validation tool callable without path hacking and keep the shared formatting logic in one importable location.

## In Scope

- Remove the `sys.path.insert(...)` pattern from the script.
- Expose the profile formatter through a stable module or CLI entrypoint.
- Keep the existing validation behavior and thresholds unchanged.

## Not In Scope

- Reworking the profile formatting logic itself.
- Changing validation rules unless the import refactor exposes a bug.
- Moving the validator into a different product workflow.

## Existing Building Blocks

- `api/services/career_profiles.py` already contains the canonical formatting logic.
- The script is already narrow enough that a better entrypoint should be straightforward.

## Proposed Shape

- Export a stable helper from the API package or a shared utility module.
- Let the script import that helper directly without mutating `sys.path`.
- If needed, add a console-script entrypoint so the validator can be run from anywhere.

## Acceptance Criteria

- The validator runs from the repo root without path hacks.
- The script still produces the same validation result and exit codes.
- The shared formatter remains the canonical implementation.

## Test Plan

- Add a smoke test for the script entrypoint.
- Verify the validator still works with the current profile fixture set.
- Keep the formatter output stable where possible.

## Risks

- A new entrypoint can drift if it is not wired to the canonical helper.
- If the CLI is packaged too aggressively, it may become harder to use during local debugging.
