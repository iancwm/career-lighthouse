# Langfuse Observability Sprint: Design

Status: Implemented, merged to `main` on 2026-05-04  
Last updated: 2026-05-04  
Source artifact:
- `/home/iancwm/.gstack/projects/iancwm-career-lighthouse/iancwm-main-design-20260503-110743.md`
Implementation commit:
- `7efbd83 feat: implement langfuse observability sprint`

## Goal

Turn the current vague trace-reading loop into a clear workflow-debugging experience:

- obvious entrypoint from the Staging Area
- live handoff when analysis finishes
- plain-English explanation first
- technical evidence second

## Shipped Outcome

The sprint shipped the intended queue-first debugging flow across the existing admin surfaces:

- `web/components/admin/SessionInbox.tsx` now splits the Staging Area into `Ready to review`, `Analyzing now`, and `Recent sessions`.
- completion handoff now uses the `Your session is ready...` success banner, promotes the row visually, and exposes `Review now` plus `Debug Workflow`
- `web/components/admin/SmartCanvas.tsx` auto-selects the first pending card after analysis completes instead of making the operator hunt manually
- `web/components/admin/TraceExplorerTab.tsx` and the workflow watchlist inside `web/components/admin/LLMObservabilityTab.tsx` now deliver the two-layer detail model: summary first, evidence second

## Primary User

Primary user:

- Ian Chong, technical owner of the session-card pipeline

Secondary future user:

- non-technical operators who need to understand what happened before reading trace-native language

## Design Principles

- Orientation first, explanation second
- Queue first, dashboard second
- Show the system state at the moment it changes
- Support two reading levels without splitting the product
- Prefer job-to-be-done labels over infrastructure labels
- Treat partial states as honest product states, not generic failures

## Information Architecture

### Header

The compact header should carry orientation only:

- product name
- active surface label
- utility actions

Do not keep truncated descriptive copy in the compact header row.

Explanatory copy belongs in the directive/banner area below.

### Staging Area

Reshape the Staging Area into a live queue:

1. `Ready to review`
2. `Analyzing now`
3. `Recent sessions`

This replaces the passive “single list with statuses” model.

### Debug Entry

Primary CTA label:

- `Debug Workflow`

Underlying technical surface name:

- `Trace Explorer`

Do not use `Traces` as the main call to action.

## Completion Handoff

### If the user is in the session canvas

When analysis completes:

- remove the waiting state immediately
- reveal the first pending card automatically
- do not require a manual refresh before card review can begin

### If the user is in the Staging Area list

When analysis completes:

- move the session into `Ready to review`
- apply a brief visual pulse to the row
- show a temporary success banner
- provide a one-click `Review now` action
- do not forcibly navigate away from the list

Recommended banner tone:

- `Your session is ready. 3 cards are ready to review.`

## Workflow Detail Design

The workflow-detail surface must support two layers.

### Layer 1: What happened

Plain-English summary:

- overall outcome
- likely cause
- card outcome
- next recommended action

This layer should be understandable by non-technical users.

### Layer 2: Technical details

Evidence rail:

- prompt name/version/label/source
- timeline of steps
- repair attempts
- validation and append evidence
- card counts
- drop-point analysis
- linked scores/metadata

Technical users should be able to continue into this layer without losing fidelity.

## Interaction States

### Staging Area queue

- Loading: live `Analyzing now` treatment
- Empty: warm no-sessions state with `Start a session`
- Error: inline failure with retry, composer preserved
- Success: session promoted into `Ready to review`
- Partial: list still usable, with a soft stale-data warning

### Session completion

- Success: top banner + promoted row + `Review now`
- Warning: analysis completed with some rejected cards, keep warning visible
- Failure: row remains visible with retry action

### Session canvas

- Analysis-in-progress state remains visible in place
- First pending card auto-revealed on success
- If some cards were rejected, show cards plus a warning summary

### Workflow detail

- Loading: summary visible while detail loads
- Empty: `No workflow recorded yet`
- Error: fallback explanation, not silent collapse
- Partial: show known sections, replace missing sections with explicit placeholders

Example placeholder style:

- `Prompt version unavailable for this run`
- `Router append result was not recorded for this session`
- `Repair output not available from fallback trace data`

## Product Language

Use job-shaped language:

- `Review now`
- `Debug Workflow`
- `Analyzing now`

Success copy can be warmer and more assistant-like as long as it stays precise:

- `Your session is ready`
- `3 cards are ready to review`

Avoid infrastructure-first wording for primary actions:

- avoid `Traces` as the main CTA

## Visual Direction

Align to the repo-wide `editorial utilitarian` system in `DESIGN.md`.

Rules:

- quiet chrome
- hierarchy through typography and spacing
- layout-first admin surfaces
- no equal-weight dashboard mosaic
- no decorative SaaS-dashboard filler

Preferred usage:

- `Instrument Sans` for controls and operational copy
- `Fraunces` only where a major heading needs lift
- `IBM Plex Mono` only for timestamps, versions, and trace metadata

Color intent:

- warm neutrals for shells and secondary surfaces
- teal for primary action
- amber for in-progress/caution
- red only for true breakage

## Responsive Rules

Desktop:

- preserve the compact multi-row shell
- keep explanatory copy out of the compressed header
- keep the next action visible without a hunt

Tablet:

- keep queue sections ahead of secondary metrics
- collapse utility actions before collapsing primary workflow labels

Mobile:

- preserve the Staging Area hierarchy:
  - composer
  - `Ready to review`
  - `Analyzing now`
  - `Recent sessions`
- show Layer 1 summary before any technical metadata
- do not hide the primary workflow behind ambiguous navigation

## Accessibility Rules

- completion banner announced via polite live region
- primary actions remain at least 44px tall
- focus order follows queue priority, then detail
- partial-detail placeholders are readable text, not icon-only
- color is never the only state signal

## Anti-Slop Rules

- Keep the admin UI layout-first, not tile-first.
- Use cards only where the card is itself the interaction.
- Do not turn the observability screen into a generic KPI dashboard.
- Metrics and trends are secondary support, not the first visual priority.

## Future Note

For this sprint, keep `Debug Workflow` as the main technical CTA.

If non-technical operator rollout becomes real later, test a softer alias such as:

- `What happened?`
- `Explain this run`

That experiment is intentionally deferred and tracked in `TODOS.md`.
