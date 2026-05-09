
### History section: add pagination once list grows large (Later)

**What:** Add a "Show more" button to the history section in `SessionInbox.tsx`, capped at 20 entries per page (matching `SESSION_PAGE_SIZE`).

**Why:** Currently renders all completed sessions at once with no limit. Acceptable now but could become a long list after 6+ months of use.

**Context:** The history section was added as part of the UX Polish sprint (2026-05-10). At current single-team scale it's fine. Watch it if completed sessions accumulate past ~50.

**Depends on:** None.
