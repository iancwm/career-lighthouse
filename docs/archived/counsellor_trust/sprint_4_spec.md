# Counsellor Trust Sprint 4 Spec

Status: Draft (2026-04-22)  
Owner: Counsellor Trust track  
Audience: product, design, engineering, and sponsor review  
Related backlog: [sprint_list.md](./sprint_list.md)

## Purpose

Sprint 4 makes retrieval behave like the trust model the product already claims to have. Sprint 1 established active vs superseded for structured knowledge. Sprint 2 made publishing understandable. Sprint 3 made student context and provenance visible. Sprint 4 is the part that makes raw document retrieval obey the same rules.

Today, Qdrant still acts like a flat pool of chunks. The chat path asks for top-k results, turns those into citations, and assumes that the filename is good enough to stand in for source state. That is not good enough. A student answer should never quietly pull from stale material just because it is still indexed.

## Problem

The backend still has a split brain:

- structured YAML facts already have lifecycle semantics and context filtering
- raw uploaded documents still look like timeless chunks in Qdrant
- admin health tells us about volume and overlap, but not whether the current answer is backed by current sources

That leaves a trust gap. The UI can say "current" all day. If retrieval still lets old chunks participate in student answers, the system is pretending.

## Sprint Goal

Make raw document retrieval consistent with the existing trust model:

1. Add a durable source ledger for uploaded documents
2. Filter retrieval so normal student flows only see active sources
3. Expose active vs superseded counts and stale-source evidence in admin observability
4. Make the no-current-source case explicit instead of silently falling back to stale material

## Non-Goals

This sprint does not include:

- auth hardening
- timeout handling
- optimistic locking
- a second search index or shadow Qdrant collection
- a major admin IA redesign
- a background job system
- a full reingestion of every document in the product

The goal is trust policy and instrumentation on the current architecture, not a new platform.

## Users

Primary user: counsellor/admin, who needs to know whether the backend is still using current sources.

Secondary user: student, who should only see active sources presented as current.

## Design Principles

- Keep YAML the canonical source of truth for structured knowledge.
- Keep Qdrant as the support layer for semantic retrieval, not the truth layer.
- Prefer explicit lifecycle state over filename inference.
- Fail honestly when no active sources remain.
- Reuse existing cache and observability patterns instead of introducing a parallel system.

## Trust Model

### Source state

Raw source documents should be tracked with explicit lifecycle metadata:

- active
- superseded
- archived

The source ledger is the durable record for those states. Qdrant chunk payloads remain useful for retrieval, but they do not define lifecycle on their own.

### Visual hierarchy

The admin surfaces need a simple reading order:

1. Is the source state healthy?
2. What evidence says that is true?
3. Which chunks or queries are still stale?

That means the lifecycle summary should sit above the raw trace table, not inside it. The table is for evidence. The summary is for orientation. A wall of equal-weight cards would be the wrong shape here. This is a workspace, not a poster.

### Admin surface map

```text
LLMObservabilityTab
  -> headline and short explainer
  -> source-state summary strip
  -> KB health cards
  -> document coverage / stale-source panel
  -> weak-query panel
  -> trace table

DocList
  -> compact inventory list
  -> filename
  -> lifecycle state
  -> chunk count
  -> upload date
  -> delete action
```

The student-facing fallback should be much smaller. It belongs inline in the chat answer area, attached to the response that could not find active sources. It should read as an honest constraint, not a system failure.

### Source ledger shape

Each source record should carry at least:

- source_filename
- lifecycle
- uploaded_at
- uploaded_by
- superseded_by
- linked_knowledge_object
- chunk_count

Unknown values should be explicit, not implied.

### Data flow

```text
INGEST / UPDATE
  -> parse file
  -> chunk + embed
  -> write Qdrant points
  -> upsert source ledger entry
  -> invalidate source-state cache

STUDENT CHAT
  -> resolve active source state
  -> search Qdrant
  -> filter out superseded sources
  -> if active hits remain, build citations from those hits
  -> if no active hits remain, answer honestly without falling back to stale chunks

ADMIN HEALTH
  -> read source ledger
  -> compare active ledger entries to live indexed docs
  -> compute active/superseded counts
  -> surface stale-source evidence and active-hit stats
```

## Scope

### Durable source ledger

Add a durable ledger for uploaded documents, stored in the same YAML-first style as the rest of the repo. The ledger should let the system answer:

- which source is active
- which source superseded it
- when the source was uploaded
- who uploaded it, if known
- what knowledge object or employer it belongs to

The ledger should be updated atomically on ingest and re-upload. If a filename is re-uploaded, the newer record becomes active and the older record becomes superseded.

Use the same storage shape the repo already uses for other lifecycle-managed content: one YAML file per source record, plus a history directory for prior snapshots if that helps with auditability. Do not put the entire source inventory into one shared mutable YAML file. That would create a write bottleneck and turn a simple upload into a small database migration.

If the admin deletes a document from `DocList`, the plan should treat that action as an archive or retire operation for the ledger, not a silent loss of history. The raw Qdrant chunks can remain available for audit and stale-source detection, but the source must stop counting as active. If a true hard purge is ever needed, that should be a separate explicit action, not the same button.

### Retrieval filtering

Teach retrieval to consult the source ledger before a chunk can count as current.

Normal student flows should:

- keep active chunks
- exclude superseded chunks from citations
- never mark superseded content as current in the response

If filtering removes every chunk for a query, the assistant should respond honestly. It may answer from student context, but it must not quietly resurrect stale chunks just to avoid an empty result set.

The filter should sit at the retrieval boundary, close to the Qdrant search result normalization step, so every caller sees the same active-only policy. Keep the filter keyed by source filename and lifecycle state, not by ad hoc prompt logic.

### Admin observability

Extend the admin KB view so it can tell the truth about source state:

- active source count
- superseded source count
- stale source count
- retrieval hits against active sources
- retrieval hits against superseded sources

The admin should be able to tell whether stale chunks still exist and whether they are still being considered by retrieval. Volume-only metrics are not enough.

Where a count is sourced from the ledger, treat it as the truth and use Qdrant chunk totals as supporting evidence. The dashboard should never derive lifecycle state from whether a filename happens to still appear in the vector index.

### Stale-source detection

Implement a lightweight stale-source check that compares the source ledger against currently indexed docs.

The goal is not a perfect forensic scanner. The goal is a fast, readable signal that answers:

- "this source was superseded"
- "these chunks still exist"
- "these retrieval hits are still coming from old material"

### Backfill for existing docs

Add a one-time backfill path for currently indexed documents that predate the ledger.

The backfill should seed one active ledger record per indexed filename so the system starts from a consistent baseline instead of treating old content as invisible or orphaned.

Backfill should be idempotent. If it runs twice, it should not create duplicate active records for the same filename.

## Interaction States

| Feature | Loading | Empty | Error | Success | Partial |
|---------|---------|-------|-------|---------|---------|
| Student retrieval | Search in progress | No active sources available for this question | Active-source lookup fails, show an honest fallback and keep chat usable | Citations come only from active sources | Some chunks filtered out, but active hits remain usable |
| No-active-source fallback | N/A | No current source material for this question | If the fallback message itself fails, return the plain chat response without citations rather than stale citations | Assistant says it cannot confirm from current sources and proceeds cautiously | Student context still shapes the answer |
| Admin observability | Loading metrics | No stale sources yet | Inline error if ledger or health state cannot load | Active vs superseded counts, stale evidence, and active-hit stats are visible | Some metrics available, others explicitly unknown |

### Interaction notes

- Loading should use skeleton cards and muted placeholders, not spinners alone.
- Empty states should explain what happened and what the admin can do next.
- The no-active-source case should not look like a broken app. It should look like a careful answer that refuses to overclaim.
- Stale-source evidence should be scannable as a list, with the most recent or most relevant items first.

## Success Criteria

Sprint 4 is successful if:

- Normal student retrieval does not surface superseded content as current citations.
- When no active source survives filtering, the assistant does not fall back to stale chunks.
- Admin can see active vs superseded source counts in one place.
- Admin can see retrieval hits by active status, not just generic match scores.
- Stale source detection can point to lingering chunks after a source has been superseded.
- The system can answer, without opening raw YAML or Qdrant, whether the current chat experience is backed by current sources.
- Existing chat latency and response shape stay basically the same.

## Implementation Notes

- Reuse the existing singleton/cache pattern used by `EmployerEntityStore` and `health_cache`.
- Keep the source ledger and the chat retrieval policy on the same lifecycle model, so the student and admin views cannot drift apart.
- Keep the retrieval filter close to the search boundary, not scattered across callers.
- Keep Qdrant payloads simple. Do not turn them into a second source of truth.
- Keep the new admin metrics readable in `LLMObservabilityTab`, and keep document inventory in `DocList` if that still adds value.
- Add a small helper for "active-only" retrieval so the chat path and any admin previews can share the same policy.
- Cache the source-state map, not raw document bodies. The cache should hold lifecycle state, upload metadata, and active filename sets only.

## Design Considerations

### Design system alignment

This sprint should follow `DESIGN.md` instead of inventing a new visual language:

- Use `Fraunces` for the primary page title and any high-level trust headline.
- Use `Instrument Sans` for labels, status text, helper copy, and table content.
- Use `IBM Plex Mono` for dates, lifecycle state, chunk counts, and trace metadata.
- Keep warm neutrals as the base surface.
- Use teal for active or trusted state, amber for warning or stale emphasis, and muted gray for low-priority metadata.

The admin surface should feel like one editorial workspace, not a patchwork of stats widgets. Use cards only where the card is the interaction, such as a stale-source alert or a trace item. Otherwise, let spacing and typography do the work.

### Source-state summary design

The top of `LLMObservabilityTab` should show one compact summary strip with three things:

- active sources
- superseded sources
- stale sources

That strip should be the first thing the admin sees after the page title. It is the trust signal. The rest of the page is evidence.

Each summary item should have:

- a label
- a big number
- a short qualifier
- an obvious state color

Keep the numbers readable first, decorative second. No tiny badges tucked into corners.

### Document inventory design

`DocList` is still useful, but it should become a compact trust inventory instead of a generic file list.

Each row should show:

- filename
- lifecycle badge
- chunk count
- upload date

The delete action should stay at the end of the row, be obviously destructive, and remain a 44px touch target. If lifecycle is added here, it should be visually subordinate to the filename but still immediately visible. Think reference shelf, not inbox.

`DocList` should read from the source ledger as the primary data source, then enrich each row with the current chunk count from Qdrant. That keeps archived or superseded records visible even if the live vector index no longer treats them as active.

### Student fallback design

The no-active-source fallback should be short and calm.

It should say, in plain English, that the assistant could not confirm the answer from current source material. Then it should continue with whatever student context is safe to use. The student should not feel punished for the system's missing data, but they also should not be tricked into thinking stale material is current.

This is the whole tension of the sprint. Be honest without sounding broken.

### Mobile behavior

On mobile, the observability page should collapse into a single column in this order:

1. source-state summary
2. key KB health numbers
3. stale-source evidence
4. weak-query history
5. trace table

That order matters. The summary and the warnings should appear before the long evidence table. A counselor on a phone is usually checking whether something is safe to trust, not auditing a trace dump.

`DocList` should also stack into one column on mobile, with the delete action still reachable without horizontal scrolling.

### Accessibility

- All lifecycle badges and delete actions need visible focus states.
- Primary controls should stay at or above 44px height.
- Error and warning colors should never be the only signal. Pair them with text labels like `active`, `superseded`, or `stale`.
- Trace rows should remain readable by screen readers, with the operation, status, and timestamp in a sane order.
- If a source-state count is unknown, say `Unknown` rather than showing `0`.

### Motion

Keep motion minimal. A short fade or slide for refresh is fine. Do not animate the whole page to death. This page is for trust, not vibes.

## Design Decisions

Resolved for this sprint:

- Use a source-ledger backed policy gate, not a shadow index.
- Keep superseded chunks in Qdrant for audit and stale detection, but exclude them from normal student citations.
- Store the source ledger in repo YAML, with an in-memory cache that is invalidated on ingest and re-upload.
- Treat missing source metadata as `Unknown`, not blank.
- If retrieval filtering empties the candidate set, answer honestly rather than falling back to stale chunks.
- Keep source-state summary above the trace table and keep the trace table secondary.
- Keep the student fallback inline in chat, not as a separate warning page.
- Keep `DocList` compact and lifecycle-aware instead of turning it into a second observability dashboard.

## What already exists

- `api/services/employer_store.py` already filters superseded structured facts out of context.
- `api/services/health_cache.py` already provides a small in-memory cache with invalidation.
- `api/services/vector_store.py` already knows how to aggregate docs by filename.
- `api/routers/chat_router.py` already builds citations from Qdrant search results.
- `api/routers/kb_router.py` already exposes health metrics and trace logs.
- `web/components/admin/LLMObservabilityTab.tsx` already gives us a place to surface source and retrieval health.
- `web/components/admin/DocList.tsx` already shows the document inventory surface that can stay simple.

## NOT in scope

- Auth hardening, because it is a separate security layer and would widen the sprint.
- Timeout handling, because it is unrelated to retrieval trust.
- Optimistic locking, because it is a different concurrency problem.
- A second Qdrant collection, because it creates sync drift without solving the trust gap better than a ledger-backed filter.
- A full reindex of the knowledge base, because the sprint should tighten policy first and only backfill what is required.
- A major admin IA redesign, because the current surfaces are enough for this policy change.

## Test Requirements

Sprint 4 needs coverage for the full policy chain, not just the happy path.

- Add a regression test that walks student chat when top-k retrieval includes superseded sources and asserts that only active sources survive into citations.
- Add a regression test for the no-active-source path, proving the assistant does not fall back to superseded chunks when filtering empties the result set.
- Add a unit test for the retrieval helper that filters active vs superseded chunks by source ledger state.
- Add a KB health test that reports active source count, superseded source count, stale-source evidence, and active-hit metrics.
- Add an ingest test that writes or updates the source ledger and invalidates the source-state cache when a document is re-uploaded.
- Add a backfill test that seeds current indexed filenames into the ledger as active sources.
- Add a frontend test for `LLMObservabilityTab` that renders source-state metrics and stale-source signals.
- Keep the existing document inventory test coverage, and extend it only if the inventory surface now shows lifecycle state.

## Responsive & Accessibility

- Desktop admin layout should preserve a clear top-to-bottom reading order, not two equally loud columns.
- Tablet should keep the summary and stale-source evidence visible without forcing horizontal scroll.
- Mobile should collapse to a single column with the trust summary first and the trace table last.
- The student fallback must stay readable in the same message stream as the answer, so it can be understood without switching context.
- All trust state should be expressed in text as well as color.
- Ensure the design stays usable with keyboard navigation and does not hide the delete action or refresh action behind hover-only affordances.

## Deliverable Shape

The delivered backend should make it obvious, from the same conversation:

- which sources are current
- which sources were superseded
- whether current student answers are still backed by active sources
- whether the admin dashboard sees the same truth as chat

If the student and admin views disagree, the trust model is still broken.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean (plan) | 2 architecture decisions fixed in-plan |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | clean (plan) | design hierarchy, fallback, mobile order, and accessibility were specified |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**UNRESOLVED:** 0
**VERDICT:** Plan is ready to implement once the backend ledger shape and delete/archive behavior are wired to the existing doc inventory route.
