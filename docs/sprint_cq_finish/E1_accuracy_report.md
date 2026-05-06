---
created: 2026-05-06
status: methodology_complete_run_pending
---

# E1: LLM Extraction Accuracy Report

Closure artifact for Block C (E1) of the unified session + quality sprint.

## What is being tested

`extract_facts_from_prose()` in `api/services/llm.py:1761`. The function calls Claude to extract structured facts from free-text employer notes and returns a list of fact dicts with keys: `slug`, `type`, `timestamp`, `source`, `confidence`, `data`.

**Allowed fact types:** `timeline_phase`, `alumni`, `interview_stage`, `compensation`, `skill_requirement`.

**Target accuracy:** ≥ 80% field-level accuracy across 3 test runs.

## Test inputs (3 real employer notes)

### Note 1 — Grab
```
Identified as active fintech/superapp data analyst hirer in Singapore (alongside
Stripe, Wise, Instacart). Preferences: MITB specialized tracks or bootcamp + portfolio
> MBA or MSc. Domain knowledge in payments/fintech valued.
Source: Alumni call with Jane Teoh (Stripe), April 2025.
```

**Expected facts:**
- 1× `skill_requirement` — MITB/bootcamp preference, payments/fintech domain knowledge, confidence ~80
- 1× `timeline_phase` — active hiring phase, April 2025, confidence ~70

### Note 2 — DBS
```
Active model validation hiring driven by MAS 2023 Model Governance Guidelines.
Expects 8-10 model risk analysts/year through 2026. Prefers quant MSc + MAS RMiT
or risk certification. No direct PM role; entry via BA/Scrum Master and internal cert.
```

**Expected facts:**
- 1× `timeline_phase` — active hiring 2024-2026 driven by MAS guidelines
- 1× `skill_requirement` — quant MSc + MAS RMiT or risk cert
- 1× `interview_stage` (optional) — entry-path constraint (BA/Scrum Master)

### Note 3 — Accenture
```
Accenture is ramping up junior hiring for their new Generative AI business unit
in Singapore. Targeting data analysts and data engineers with Python and prompt
engineering skills. They prefer candidates who have completed at least one internship
in a tech firm. Source: Career fair conversation, March 2025.
```

**Expected facts:**
- 1× `skill_requirement` — Python, prompt engineering, prior tech internship required
- 1× `timeline_phase` — active GenAI unit hiring, March 2025

## How to run

```bash
cd api
ANTHROPIC_API_KEY=<key> uv run python3 -c "
import asyncio, sys
sys.path.insert(0, '.')
from services.llm import extract_facts_from_prose

notes = [
    ('Grab', '''Identified as active fintech/superapp data analyst hirer in Singapore...<paste full note>'''),
    ('DBS', '''Active model validation hiring driven by MAS 2023 Model Governance Guidelines...<paste>'''),
    ('Accenture', '''Accenture is ramping up junior hiring for their new Generative AI business unit...<paste>'''),
]

async def main():
    for employer, note_text in notes:
        facts = await extract_facts_from_prose(note_text, employer_name=employer)
        print(f'{employer}: {len(facts)} facts')
        for f in facts:
            print(f'  type={f[\"type\"]} confidence={f[\"confidence\"]} slug={f[\"slug\"]}')

asyncio.run(main())
"
```

## Scoring rubric

For each extracted fact:
- **Correct type** (25%): fact type matches expected category
- **Non-hallucinated slug** (25%): slug is derived from actual note content
- **Confidence plausible** (25%): confidence ≥ 70 for well-supported facts; ≤ 65 for hedged facts
- **Data fields grounded** (25%): all `data` dict values are present in the source note

Score = (correct fields / total expected fields) × 100. Target ≥ 80%.

## Manual write-path validation

Also verified via the FactEditor UI (manual entry):
1. Open admin → employer → Grab → Facts tab
2. Add a `skill_requirement` fact: slug `grab-mitb-preferred`, confidence 80, data: `{preference: "MITB or bootcamp > MBA"}`.
3. Confirm it writes to `knowledge/employers/grab.yaml` under `structured.facts`.
4. Reload the employer YAML and verify the slug appears in the active facts list.

Status: **pending manual run** (requires `ANTHROPIC_API_KEY` in local or staging env).

## Prompt changes needed (if accuracy < 80%)

If extraction accuracy falls short, candidate refinements:
- Add explicit instruction to NOT infer `alumni` facts from contact attribution (e.g. "Jane Teoh" = source, not alumna).
- Increase schema constraint on `data` keys per type (add per-type field list to the prompt).
- Lower confidence floor from 50 → 60 to reduce low-signal noise.
