# Sprint: UX Polish — Friendly Feedback & Emotional Journey

**Date:** 2026-05-10
**Branch:** main
**Status:** REVIEWED — ready to implement
**Design doc:** `~/.gstack/projects/iancwm-career-lighthouse/iancwm-main-design-20260509-162746.md`
**Eng review decisions:** D1–D5 (see below)

## What we're fixing

The admin panel is functional but cold. Counsellors uploading notes hit four trust gaps:
1. Logo is undersized; page description truncates with no useful info
2. After clicking "Create Session", there's silence — no card, no movement
3. Completed sessions vanish silently — no history of who submitted what
4. Status labels and empty states read like system output

## Eng Review Decisions (amends the design doc)

**D1 — Notice auto-dismiss removed**
The design doc proposed `setTimeout(() => setNotice(""), 4000)` to auto-clear "Processing your notes…". Removed. The component already polls every 4s during active sessions (line 187). When analysis completes, `loadSessions()` overwrites the notice with "Your session is ready." naturally. The timer would have raced against this and cleared the "ready" notice prematurely.

**D2 — Test updates required in same pass**
Design doc didn't mention tests. Button text change (`"Create Session"` → `"Add Session Notes"`) and notice text change (`"Analyzing now…"` → `"Processing your notes…"`) break all 3 existing `SessionInbox.test.tsx` tests. Fix in the same commit. Also add 7 new tests (see Test Plan section).

**D3 — displayedSessions derives from non-completed sessions**
Design doc stored all sessions in state (including completed) and sliced the full array for pagination. This would cause the "Show more" counter to include completed sessions, confusing counsellors who already see them in History. Fix: `const inboxSessions = sessions.filter(s => s.status !== "completed")` and derive `displayedSessions` from `inboxSessions`.

---

## Implementation — 5 fixes, 3 files

### File 1: `web/components/admin/AdminWorkspaceHeader.tsx`

**Fix 1a — Logo size (line 36)**
```tsx
// Before
<span className="shrink-0 font-display text-sm font-medium text-[var(--cl-ink)]">Career Lighthouse</span>

// After
<span className="shrink-0 font-display text-base font-semibold text-[var(--cl-ink)]">Career Lighthouse</span>
```

**Fix 1b — Remove description span (line 40 only — not the parent div)**
```tsx
// Delete this line only:
<span className="block text-xs text-[var(--cl-muted)] truncate max-w-sm">{currentSurface.description}</span>
```

---

### File 2: `web/components/admin/SessionInbox.tsx`

**Fix 3 — Status labels (replace statusLabel function at lines 89–96)**
```tsx
function statusLabel(status: string): string {
  if (status === "analyzed") return "Ready to review"
  if (status === "completed") return "Done"
  if (status === "analyzing" || status === "in-progress") return `Processing${".".repeat(statusPulse)}`
  if (status === "failed") return "Something went wrong"
  if (status === "cancelled") return "Stopped"
  return status
}
```

**Fix 3b — Button copy (line 652)**
```tsx
// Before
{creating ? "Creating…" : "Create Session"}

// After
{creating ? "Submitting…" : "Add Session Notes"}
```

**Fix 2 — Optimistic card + notice (replace createSessionWithText, lines 114–130)**
```tsx
async function createSessionWithText(noteText: string) {
  const res = await adminFetch("/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_input: noteText, counsellor_id: "counsellor" }),
  })
  if (!res.ok) throw new Error("create failed")
  const session: KnowledgeSession = await res.json()
  setRawInput("")

  // Inject optimistic card immediately — counsellor sees movement right away.
  // The 4s fast-poll (line 187) and the analyze chain below both call loadSessions()
  // which will overwrite this with DB state within one tick. That's expected.
  setSessions((prev) => [session, ...prev])

  onSelectSession(session.id)
  // Kick off analysis; refresh once done (or on failure).
  adminFetch(`/api/sessions/${session.id}/analyze`, { method: "POST" })
    .then(() => loadSessions())
    .catch(() => loadSessions())

  // "Processing" notice persists until loadSessions() overwrites it with "Your session is ready."
  // Do NOT add a setTimeout here — it would race against the polling and clear the "ready" notice.
  setNotice("Processing your notes…")
}
```

**Fix 4 — History section**

Add state variable with other useState declarations:
```tsx
const [showHistory, setShowHistory] = useState(false)
```

Replace `loadSessions()` body (lines 150–176):
```tsx
async function loadSessions() {
  try {
    const res = await adminFetch("/api/sessions")
    if (!res.ok) throw new Error("load failed")
    const data: KnowledgeSession[] = await res.json()
    const allSessions = data
    // Notification tracking excludes completed — no transition fires on completed sessions
    const trackingSessions = allSessions.filter((s) => s.status !== "completed")
    const previousStatuses = previousSessionStatusRef.current
    for (const session of trackingSessions) {
      const previous = previousStatuses.get(session.id)
      const pendingCards = session.intent_cards.filter((card) => card.status === "pending").length
      if ((previous === "analyzing" || previous === "in-progress") && session.status === "analyzed") {
        setNotice(
          pendingCards > 0
            ? `Your session is ready. ${pendingCards} cards are ready to review.`
            : "Your session is ready."
        )
        setPromotedSessionId(session.id)
      }
    }
    previousSessionStatusRef.current = new Map(trackingSessions.map((s) => [s.id, s.status]))
    setSessions(allSessions)  // store full list including completed
  } catch {
    setError("Could not load sessions.")
  } finally {
    setLoading(false)
  }
}
```

Replace bucket derivation (lines 489–492, after `if (loading)` check):
```tsx
// Derive inbox sessions (excludes completed — those live in History)
const inboxSessions = sessions.filter((s) => s.status !== "completed")
const displayedSessions = showAllSessions ? inboxSessions : inboxSessions.slice(0, SESSION_PAGE_SIZE)

// History is always derived from the full list, not the paginated inbox
const historySessions = sessions.filter((s) => s.status === "completed")

const readySessions = displayedSessions.filter((s) => s.status === "analyzed")
const activeSessions = displayedSessions.filter((s) => s.status === "in-progress" || s.status === "analyzing")
// Use .some() not .includes() — defensive against re-created objects
const recentSessions = displayedSessions.filter(
  (s) => !readySessions.some((r) => r.id === s.id) && !activeSessions.some((a) => a.id === s.id)
)
```

Add History section after the existing three sections (after `</section>` for "Recent sessions"):
```tsx
{/* History — collapsible, collapsed by default */}
<section>
  <button
    type="button"
    onClick={() => setShowHistory((v) => !v)}
    className="text-xs text-[var(--cl-muted)] py-2 hover:text-[var(--cl-ink)] transition-colors"
  >
    {showHistory ? "Hide history" : `Show history (${historySessions.length})`}
  </button>
  {showHistory && (
    historySessions.length === 0
      ? <p className="text-sm text-[var(--cl-muted)] py-4 text-center">No history yet.</p>
      : historySessions.map((session) => (
          <div
            key={session.id}
            className="flex items-center justify-between px-3 py-2 border-b border-[var(--cl-divider)] text-sm text-[var(--cl-muted)]"
          >
            <span className="truncate max-w-[200px]">
              {session.raw_input?.slice(0, 60) ?? "Session"}
              {(session.raw_input?.length ?? 0) > 60 ? "…" : ""}
            </span>
            <span>{session.created_by}</span>
            <span>{new Date(session.created_at).toLocaleDateString()}</span>
            <span className="text-[var(--cl-success)]">Done</span>
          </div>
        ))
  )}
</section>
```

**Fix 5 — Empty states**

Replace the `sessions.length === 0` empty state (lines 657–675) — keep the existing block but change copy:
```tsx
{sessions.length === 0 ? (
  <div className="rounded-xl border border-[#D8D0C4] bg-[#F0E7DB] p-8 text-center">
    <p className="text-2xl mb-3">📝</p>
    <h4 className="text-lg font-semibold text-[#1F2937] mb-2">No sessions yet</h4>
    <p className="text-sm text-[#5F6B76] max-w-md mx-auto mb-6">
      Upload a student's notes to get started.
    </p>
    <button
      onClick={scrollToTextarea}
      className="rounded-xl bg-[#0F766E] px-6 py-2 text-sm font-medium text-white hover:bg-[#0A5C57] transition-colors"
      style={{ minHeight: "44px" }}
    >
      Start a session
    </button>
  </div>
) : (
```

Inside the else branch, add "All caught up!" state before the `<div className="space-y-6">` block:
```tsx
{/* "All caught up!" — inbox is clear but history may exist */}
{activeSessions.length === 0 && readySessions.length === 0 && recentSessions.length === 0 && (
  <p className="text-sm text-[var(--cl-muted)] py-6 text-center">All caught up!</p>
)}
```

---

### File 3: `web/components/admin/__tests__/SessionInbox.test.tsx`

**Regression fixes (required — CI will fail without these):**

1. Replace all occurrences of `/Create Session/i` → `/Add Session Notes/i` (5 occurrences in 3 tests)
2. Replace `"Analyzing now…"` → `"Processing your notes…"` (line 238)

**New tests to add (7 tests):**

1. **Optimistic card appears immediately**
   - Mock loadSessions to resolve only after a delay
   - After clicking "Add Session Notes", verify session card appears BEFORE loadSessions resolves
   - Tests: `setSessions((prev) => [session, ...prev])` path

2. **"Processing your notes…" notice appears after create**
   - After clicking "Add Session Notes", verify notice banner shows "Processing your notes…"

3. **History toggle shows completed sessions**
   - Load with one completed session in GET response
   - Verify history section is collapsed by default ("Show history (1)" button visible, session NOT visible)
   - Click toggle → session appears

4. **History toggle collapses on second click**
   - Extends test 3: click "Hide history" → session disappears

5. **Empty history state**
   - Load with no completed sessions, toggle history → "No history yet." appears

6. **"All caught up!" empty inbox with history**
   - Load with one completed session, no active/analyzed/recent
   - Verify "All caught up!" text appears in active sections area

7. **Status label copy**
   - Load with sessions of each status type
   - Verify: "analyzed" → "Ready to review", "failed" → "Something went wrong"

---

## Implementation Order

Follow this order so each fix is independently testable:

1. **Fix 1** — `AdminWorkspaceHeader.tsx` logo + description (2 lines, zero risk)
2. **Fix 3** — status labels + button copy + update test references (copy-only)
3. **Fix 4** — loadSessions split + history section + displayedSessions change
4. **Fix 2** — optimistic card (depends on Fix 4 having the correct setSessions flow)
5. **Fix 5** — empty states
6. **New tests** — write all 7 new tests
7. **Run:** `cd web && npm test` — all tests must pass green

## Success Criteria

- [ ] Uploading notes immediately shows a card in "Analyzing Now" with "Processing…" label
- [ ] "Processing your notes…" notice persists until analysis completes
- [ ] "Your session is ready." notice appears and persists (no premature clear)
- [ ] Completed sessions accessible via history toggle
- [ ] No status label shows raw system code
- [ ] Logo is visually prominent
- [ ] Empty inbox shows "All caught up!" when history exists
- [ ] "Upload a student's notes to get started." on first-ever load
- [ ] "Show more" counter counts only inbox sessions, not history
- [ ] All tests pass green

## Deploy

```bash
docker compose up --build web
```

No env var changes. No backend changes.
