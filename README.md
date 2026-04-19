# Career Lighthouse

AI-powered career advisory platform for universities. Career offices upload institutional knowledge; students get locally-grounded career advice; counselors get pre-meeting student briefs.

## Quick Start (Demo)

> All setup files (`docker-compose.yml`, `api/`, `web/`) are included in this repo.

```bash
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
just up
```

- Career office: http://localhost:3000/admin
- If you set `ADMIN_KEY`, append `?key=...` to the admin URL
- Student advisor: http://localhost:3000/student

## Admin Key Configuration

The `ADMIN_KEY` protects the admin dashboard and sensitive API endpoints (`/api/kb/*`, `/api/sessions/*`).

### Development (No Auth)

Leave `ADMIN_KEY` empty in `.env` to disable authentication for local development:

```env
ADMIN_KEY=
```

### Production (Required)

Generate a strong random key and set it in `.env`:

```bash
# Generate a secure random key
ADMIN_KEY=$(openssl rand -hex 32)

# Or using Python
ADMIN_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
```

Then add it to your `.env` file:

```env
ADMIN_KEY=your-generated-key-here
```

**Important security notes:**
- The admin key is passed as a **query parameter** (`?key=...`) in the browser — it will appear in server access logs
- For production, consider migrating to `Authorization: Bearer` headers or session cookies (see TODOS.md)
- Rotate the key regularly via SSM SecureString in AWS
- Both the API and Web services must share the same `ADMIN_KEY` value

### Accessing the Admin Dashboard

Once `ADMIN_KEY` is set, access the dashboard with the key as a query parameter:

```
http://localhost:3000/admin?key=your-admin-key-here
```

If the key is missing or incorrect, you'll see an "Unauthorized" error.

## Developer Workflow

Uses [`just`](https://github.com/casey/just) as a task runner. Run `just` to list all recipes.

| Command | Description |
|---|---|
| `just up` | Build and start all services, including Langfuse (Docker) |
| `just langfuse-up` | Start the Langfuse stack on `http://localhost:3001` |
| `just langfuse-ps` | Show the Langfuse profile containers |
| `just langfuse-logs` | Follow logs for the Langfuse stack |
| `just langfuse-down` | Stop the Langfuse stack |
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

- **Session Editor** — the starting point for counsellors. Turn notes into reviewable intent cards, inspect track guidance when the note points to a new or unclear career path, and commit or discard changes from one place. Session extraction now emits flat JSON-only intent cards, so follow-up actions stay editable instead of coming back as nested objects.
- **Knowledge Review** — structured review of proposed KB edits before anything is written.
- **Source Documents** — upload PDF/DOCX/TXT, with similarity warning if the document overlaps an existing one.
- **Employer Facts** — maintain employer YAMLs and review track coverage for employer context.
- **Track Builder** — only for recurring evidence that needs a new or revised track. It shows the live published reference, supports refresh from new research, and keeps the archived working copy separate from the published profile.
- **KB Health** — live observability: doc coverage (good/thin), 7-day avg match score and retrieval diversity, low-confidence query log, and redundant document detection.
- **LLM Observability** — session and prompt traces, live run state, a dedicated Trace Explorer, and optional Langfuse-backed debugging for model calls.

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
- **Configuration**: All thresholds, prompts, and model settings externalized to YAML files in `api/cfg/` — tunable without code changes
- **Career profiles**: YAML files in `knowledge/career_profiles/` injected into the LLM context at query time; editable without code. Legacy slugs are canonicalized on read and write, so old `data_science` payloads migrate to `dsai` automatically.
- **Employer facts**: YAML files in `knowledge/employers/` injected into the LLM context at query time; editable from the admin UI
- **Query logging**: student queries logged to `./logs/query_log.jsonl` for KB health analysis (single-worker deployments only)
- **LLM tracing**: every model call emits structured `started`, `ok`, and `error` trace rows. When `LANGFUSE_*` env vars are set, the same trace data is exported to self-hosted Langfuse for richer inspection, and session runs group correctly once `session_id` is propagated. The admin UI has a dedicated Trace Explorer, and in Docker the API should point at `http://langfuse-web:3000`; the browser-facing UI stays on `http://localhost:3001`. For hosted Langfuse, set `LANGFUSE_HOST` instead. Keep `LANGFUSE_FLUSH_AT` and `LANGFUSE_FLUSH_INTERVAL` low in dev, but let them grow for cloud deployments so tracing stays asynchronous and does not sit on the request path. Session intents are now JSON-only, with the old `<thought>` response plumbing removed from the backend contract.
- **Live timeout visibility**: session analysis and brief generation can still hit the Anthropic timeout under long or expensive requests, but the request now shows a `started` trace immediately and a matching `error` trace if the model times out. Wildly better than staring at a blank spinner.
- **Data stays local**: only Anthropic Claude API call leaves the deployment (PDPA-compliant)

Track publishing now keeps a live published profile plus an archived working copy. If a counsellor refreshes a track from new research and no draft exists yet, the app bootstraps the draft from the published profile first. That keeps existing tracks editable without forcing a manual recreate step.

## Where Data Lives

When you run `just up`, Docker does not upload knowledge files anywhere. It mounts
your local repo into the API container:

- `./data/sessions` → `/app/data/sessions`
- `./knowledge` → `/app/knowledge`
- `./logs` → `/app/logs`

That means:

- Sessions are stored as JSON under `data/sessions/`
- Employer YAMLs are loaded from [knowledge/employers](/home/iancwm/git/career-lighthouse/knowledge/employers)
- Career profile YAMLs are loaded from [knowledge/career_profiles](/home/iancwm/git/career-lighthouse/knowledge/career_profiles)
- Draft tracks and track history stay under `knowledge/...`
- Query logs are written to [logs/query_log.jsonl](/home/iancwm/git/career-lighthouse/logs/query_log.jsonl)

Important distinction:

- Admin edits to employer facts and career profile YAML fields are written back to `knowledge/...`
- Uploaded documents from the Knowledge Base tab are not saved as files under `knowledge/`; they are chunked, embedded, and stored in Qdrant

So if you upload a PDF or TXT and then look in `knowledge/`, you will not see a new file there. The source document becomes vector-store data, not a repo file.

## Production Deployment (AWS ap-southeast-1)

See `terraform/` — deploy to your institution's own AWS account.
