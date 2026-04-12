# Career Lighthouse

AI-powered career advisory platform for universities. Career offices upload institutional knowledge; students get locally-grounded career advice; counselors get pre-meeting student briefs.

## Quick Start (Demo)

> All setup files (`docker-compose.yml`, `api/`, `web/`) are included in this repo.

```bash
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
just up
```

- Career office: http://localhost:3000/admin?key=demo2026
- Student advisor: http://localhost:3000/student

## Developer Workflow

Uses [`just`](https://github.com/casey/just) as a task runner. Run `just` to list all recipes.

| Command | Description |
|---|---|
| `just up` | Build and start all services (Docker) |
| `just where-data` | Show where YAML knowledge, Qdrant data, and logs are stored |
| `just down` | Stop all services |
| `just logs` | Follow logs for all services |
| `just clean` | Stop services and wipe Qdrant data volume |
| `just install` | Install all dependencies (`uv sync` + `npm ci`) |
| `just lock-api` | Refresh `api/uv.lock` after changing Python dependencies |
| `just qdrant` | Start a local Qdrant server (needed for `dev-api`) |
| `just dev-api` | Run API dev server locally with hot-reload |
| `just dev-web` | Run Next.js dev server |
| `just test` | Run all tests (API + web) |
| `just test-api` | Run pytest suite |
| `just test-web` | Run Vitest suite |
| `just push-changes` | Analyze the current diff against TODOs/plans and summarize progress toward a goal |
| `just ingest` | Ingest all `demo-data/` files into the running API |

## Python Package Management

The backend uses `uv` with [api/pyproject.toml](/home/iancwm/git/career-lighthouse/api/pyproject.toml) as the dependency manifest and [api/uv.lock](/home/iancwm/git/career-lighthouse/api/uv.lock) as the locked resolution.

```bash
cd api
uv sync --extra dev
uv run python -m pytest
uv lock
```

Use `uv lock` after editing `api/pyproject.toml`, then commit both the manifest and `api/uv.lock`.

## Admin Dashboard

The career office dashboard (`/admin`) includes:

- **Session Editor** — the starting point for counsellors. Turn notes into reviewable intent cards, inspect track guidance when the note points to a new or unclear career path, and commit or discard changes from one place.
- **Knowledge Review** — structured review of proposed KB edits before anything is written.
- **Source Documents** — upload PDF/DOCX/TXT, with similarity warning if the document overlaps an existing one.
- **Employer Facts** — maintain employer YAMLs and review track coverage for employer context.
- **Track Builder** — only for recurring evidence that needs a new or revised track. It shows the live published reference, supports refresh from new research, and keeps the archived working copy separate from the published profile.
- **KB Health** — live observability: doc coverage (good/thin), 7-day avg match score and retrieval diversity, low-confidence query log, and redundant document detection.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/ingest` | Upload a document (PDF/DOCX/TXT) to the KB |
| `DELETE` | `/api/docs/{doc_id}` | Remove a document and its chunks |
| `GET` | `/api/docs` | List all documents |
| `POST` | `/api/chat` | Student chat (RAG + career profile injection) |
| `POST` | `/api/brief` | Generate a pre-meeting student brief from a resume |
| `POST` | `/api/kb/analyse` | Analyse counsellor input against the KB — returns diff, no writes |
| `POST` | `/api/kb/commit-analysis` | Commit a counsellor-approved diff to Qdrant + YAML profiles |
| `GET` | `/api/kb/health` | KB health metrics (coverage, match scores, query log) |
| `POST` | `/api/kb/test-query` | Test a query against the KB with per-chunk scores |
| `GET` | `/api/kb/career-profiles` | List loaded career profiles with completeness metadata |
| `GET` | `/api/kb/tracks` | List registered career tracks |
| `GET` | `/api/kb/tracks/{slug}` | Read the live published reference for a track |
| `GET` | `/api/kb/tracks/{slug}/history` | List published versions for a track |
| `POST` | `/api/kb/draft-tracks/{slug}/generate-update` | Refresh a draft track from new counsellor research |

## Architecture

- **Backend**: FastAPI (Python) — embeddings via sentence-transformers (in-process), vector DB via Qdrant (local volume), LLM via Anthropic Claude
- **Frontend**: Next.js 14
- **Career profiles**: YAML files in `knowledge/career_profiles/` injected into the LLM context at query time; editable without code. Legacy slugs are canonicalized on read and write, so old `data_science` payloads migrate to `dsai` automatically.
- **Employer facts**: YAML files in `knowledge/employers/` injected into the LLM context at query time; editable from the admin UI
- **Query logging**: student queries logged to `./logs/query_log.jsonl` for KB health analysis (single-worker deployments only)
- **Data stays local**: only Anthropic Claude API call leaves the deployment (PDPA-compliant)

Track publishing now keeps a live published profile plus an archived working copy. If a counsellor refreshes a track from new research and no draft exists yet, the app bootstraps the draft from the published profile first. That keeps existing tracks editable without forcing a manual recreate step.

## Where Data Lives

When you run `just up`, Docker does not upload knowledge files anywhere. It mounts
your local repo into the API container:

- `./knowledge` → `/app/knowledge`
- `./logs` → `/app/logs`

That means:

- Employer YAMLs are loaded from [knowledge/employers](/home/iancwm/git/career-lighthouse/knowledge/employers)
- Career profile YAMLs are loaded from [knowledge/career_profiles](/home/iancwm/git/career-lighthouse/knowledge/career_profiles)
- Query logs are written to [logs/query_log.jsonl](/home/iancwm/git/career-lighthouse/logs/query_log.jsonl)

Important distinction:

- Admin edits to employer facts and career profile YAML fields are written back to `knowledge/...`
- Uploaded documents from the Knowledge Base tab are not saved as files under `knowledge/`; they are chunked, embedded, and stored in Qdrant

So if you upload a PDF or TXT and then look in `knowledge/`, you will not see a new file there. The source document becomes vector-store data, not a repo file.

## Production Deployment (AWS ap-southeast-1)

See `terraform/` — deploy to your institution's own AWS account.
