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
| `just down` | Stop all services |
| `just logs` | Follow logs for all services |
| `just clean` | Stop services and wipe Qdrant data volume |
| `just install` | Install all dependencies (`uv sync` + `npm ci`) |
| `just qdrant` | Start a local Qdrant server (needed for `dev-api`) |
| `just dev-api` | Run API dev server locally with hot-reload |
| `just dev-web` | Run Next.js dev server |
| `just test` | Run all tests (API + web) |
| `just test-api` | Run pytest suite |
| `just test-web` | Run Vitest suite |
| `just ingest` | Ingest all `demo-data/` files into the running API |

## Admin Dashboard

The career office dashboard (`/admin`) includes:

- **Document management** — upload PDF/DOCX/TXT, with similarity warning if the document overlaps an existing one
- **Brief generator** — generate pre-meeting student briefs from the KB
- **KB Health** — live observability: doc coverage (good/thin), 7-day avg match score and retrieval diversity, low-confidence query log, and redundant document detection

## Architecture

- **Backend**: FastAPI (Python) — embeddings via sentence-transformers (in-process), vector DB via Qdrant (local volume), LLM via Anthropic Claude
- **Frontend**: Next.js 14
- **Query logging**: student queries logged to `./logs/query_log.jsonl` for KB health analysis (single-worker deployments only)
- **Data stays local**: only Anthropic Claude API call leaves the deployment (PDPA-compliant)

## Production Deployment (AWS ap-southeast-1)

See `terraform/` — deploy to your institution's own AWS account.
