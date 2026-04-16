# Documentation Structure

This directory contains specification documents and archived planning materials for career-lighthouse.

## Active Documents (Root Level)

The root of the repo contains the active project documentation:

- **AUDIT.md** — Production readiness audit; updated continuously as security/infrastructure work ships
- **DESIGN.md** — Core system design and architecture rationale
- **TODOS.md** — Active backlog; ordered by priority (Now, Next, Later, Done)
- **CHANGELOG.md** — Release notes and version history
- **README.md** — Getting started guide

## Schema Documentation

- **docs/schema/** — Data schema designs and standards
  - `SCHEMA-FOUNDATION.md` — Structured schema foundation for career knowledge base (facts with metadata, timestamps, sourcing)

## Archived Materials

- **docs/archived/** — Historical documents and drafts
  - `code-quality-reviewer-prompt.md` — Legacy code review guidelines (archived 2026-04-16)
  - `implementer-prompt.md` — Legacy implementation guidance (archived 2026-04-16)
  - `spec-reviewer-prompt.md` — Legacy spec review guidelines (archived 2026-04-16)
  - **plans/** — Prior planning documents from earlier sessions
    - All dated plans moved here to keep `/docs` clean while preserving history for reference

## Navigation

**For understanding the current state:**
- Start with README.md (getting started)
- Read DESIGN.md (architecture)
- Check TODOS.md (what's being worked on)
- Review AUDIT.md (security/production status)

**For implementation details:**
- See `/docs/schema/` for data structure specifications

**For historical context:**
- See `/docs/archived/plans/` for prior session work
- See `/docs/archived/` for legacy guidelines

## Adding New Docs

- **Active specs** → root level (DESIGN.md, TODOS.md, etc.)
- **Schema definitions** → docs/schema/
- **Historical/archived material** → docs/archived/
