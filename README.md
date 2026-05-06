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
- If you set `ADMIN_KEY`, open `/admin?key=...` once; middleware exchanges it for an HttpOnly session cookie and redirects to the clean URL
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
- The admin key is only accepted on the first request as a **query parameter** (`?key=...`); middleware validates it, sets an HttpOnly session cookie, and redirects to the clean URL
- That first request can still appear in server access logs, so prefer TLS everywhere and rotate the key regularly
- Rotate the key regularly via SSM SecureString in AWS
- Both the API and Web services must share the same `ADMIN_KEY` value

### Accessing the Admin Dashboard

Once `ADMIN_KEY` is set, access the dashboard with the key as a query parameter on the first visit:

```
http://localhost:3000/admin?key=your-admin-key-here
```

After the redirect, the clean `/admin` URL uses the session cookie. If the key is missing or incorrect on first visit, you'll see an "Unauthorized" error.

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
| `just format` | Format the Python backend with Ruff |
| `just format-check` | Verify the Python backend is still Ruff-formatted |
| `just typecheck` | Validate the web app with Next.js build |
| `just check` | Run the Ruff format check plus the web TypeScript check |
| `just lock-api` | Refresh `api/uv.lock` after changing Python dependencies |
| `just qdrant` | Start a local Qdrant server (needed for `dev-api`) |
| `just dev-api` | Run API dev server locally with hot-reload |
| `just dev-web` | Run Next.js dev server |
| `just test` | Run all tests (API + web) |
| `just test-api` | Run pytest suite |
| `just test-web` | Run Vitest suite |
| `just push-changes` | Analyze the current diff against TODOs/plans and summarize progress toward a goal |
| `just ingest` | Ingest all `demo-data/` files into the running API |

## Documentation

`docs/README.md` is the index for the docs tree.

- Active specs live in `docs/session_pipeline_stabilization/`
- Active execution-progress notes live in `docs/superpowers/plans/`
- Completed sprint specs and dated plans live in `docs/archived/`
- Root docs for the current project state are `AUDIT.md`, `DESIGN.md`, `TODOS.md`, and `CHANGELOG.md`

## Python Package Management

The backend uses `uv` with [api/pyproject.toml](/home/iancwm/git/career-lighthouse/api/pyproject.toml) as the dependency manifest and [api/uv.lock](/home/iancwm/git/career-lighthouse/api/uv.lock) as the locked resolution.

```bash
cd api
uv sync --extra dev --group dev
uv run python -m pytest
uv lock
```

Use `uv lock` after editing `api/pyproject.toml`, then commit both the manifest and `api/uv.lock`.

## Admin Dashboard

The career office dashboard (`/admin`) includes:

- **Session Editor** — the starting point for counsellors. Turn notes into reviewable intent cards, inspect track guidance when the note points to a new or unclear career path, and commit or discard changes from one place. Alumni-heavy Staging Area notes now emit `alumni` cards alongside track and employer cards, and SmartCanvas renders an alumni-specific review surface with confidence, evidence, trajectory, and company-history context. Session extraction emits flat JSON-only intent cards, and the backend validates card diffs with Pydantic so bad payloads fail fast instead of leaking into YAML writes.
- **Knowledge Review** — structured review of proposed KB edits before anything is written.
- **Source Documents** — upload PDF/DOCX/TXT, with similarity warning if the document overlaps an existing one.
- **Employer Facts** — maintain employer YAMLs, review track coverage for employer context, inspect the full extracted fact `data` payload before saving structured updates, and keep sticky save/discard context visible during long extracted-fact reviews.
- **Alumni Records** — maintain canonical alumni YAMLs plus append-only company-link history, while the Staging Area alumni-card flow feeds the same store through reviewed commits instead of a separate modal workflow.
- **Track Builder** — only for recurring evidence that needs a new or revised track. It shows the live published reference, supports refresh from new research, keeps the archived working copy separate from the published profile, and now holds the selected draft plus publish/rollback actions in a compact workbench layout. If a published track exists but the draft copy is missing, the builder now seeds the draft and registry automatically so the track stays editable instead of disappearing from the editor.
- **KB Health** — live observability: doc coverage (good/thin), 7-day avg match score and retrieval diversity, low-confidence query log, and redundant document detection.
- **LLM Observability** — session and prompt traces, live run state, a dedicated Trace Explorer that reads Langfuse first, and optional Langfuse-backed debugging for model calls.

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
| `POST` | `/api/kb/employers/{slug}/extract-facts` | Extract structured facts from employer notes using LLM |

## Architecture

- **Backend**: FastAPI (Python) — embeddings via sentence-transformers (in-process), vector DB via Qdrant (local volume), LLM via Anthropic Claude
- **Frontend**: Next.js 14
- **Configuration**: All thresholds, prompts, and model settings externalized to YAML files in `api/cfg/` — tunable without code changes
- **Career profiles**: YAML files in `knowledge/career_profiles/` injected into the LLM context at query time; editable without code. Legacy slugs are canonicalized on read and write, so old `data_science` payloads migrate to `dsai` automatically.
- **Employer facts**: YAML files in `knowledge/employers/` injected into the LLM context at query time; editable from the admin UI. Structured fact previews from `structured.facts` are also rendered in the admin UI and included in the employer context block so extracted data can influence answers immediately.
- **Query logging**: student queries logged to `./logs/query_log.jsonl` for KB health analysis (single-worker deployments only)
- **LLM tracing**: every model call emits structured `started`, `ok`, and `error` trace rows. When `LANGFUSE_*` env vars are set, Langfuse is the primary observability source for trace exploration, and the admin Trace Explorer reads Langfuse sessions first with JSONL fallback only when Langfuse is unavailable. Session runs group correctly once `session_id` is propagated. In Docker the API should point at `http://langfuse-web:3000`; the browser-facing UI stays on `http://localhost:3001`. For hosted Langfuse, set `LANGFUSE_HOST` instead. Keep `LANGFUSE_FLUSH_AT` and `LANGFUSE_FLUSH_INTERVAL` low in dev, but let them grow for cloud deployments so tracing stays asynchronous and does not sit on the request path. Session intents are now JSON-only, with the old `<thought>` response plumbing removed from the backend contract, and unexpected client exceptions now record a matching `error` trace instead of leaving orphaned `started` rows.
- **Live timeout visibility**: session analysis and brief generation can still hit the Anthropic timeout under long or expensive requests, but the request now shows a `started` trace immediately and a matching `error` trace if the model times out. The repair path also retries transient overloads, so a one-off 529 no longer turns into a blank session. Wildly better than staring at a blank spinner.
- **Data stays local**: only Anthropic Claude API call leaves the deployment (PDPA-compliant)

Track publishing now keeps a live published profile plus an archived working copy. If a counsellor refreshes a track from new research and no draft exists yet, the app bootstraps the draft from the published profile first, and it backfills the track registry if the published track was added through another workflow. That keeps existing tracks editable without forcing a manual recreate step or a manual registry fix.

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
- Draft tracks and track history stay under `knowledge/...`, and missing draft copies are seeded from valid published profiles on first access so the Track Builder stays in sync with the published catalog
- Query logs are written to [logs/query_log.jsonl](/home/iancwm/git/career-lighthouse/logs/query_log.jsonl)

Important distinction:

- Admin edits to employer facts and career profile YAML fields are written back to `knowledge/...`
- Extracted employer facts are saved under `structured.facts` in the relevant employer YAML and are shown in the admin fact cards and extraction modal before commit
- Uploaded documents from the Knowledge Base tab are not saved as files under `knowledge/`; they are chunked, embedded, and stored in Qdrant

So if you upload a PDF or TXT and then look in `knowledge/`, you will not see a new file there. The source document becomes vector-store data, not a repo file.

## Production Deployment (AWS ap-southeast-1)

See `terraform/` — deploy to your institution's own AWS account.
