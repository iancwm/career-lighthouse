# Career Lighthouse

AI-powered career advisory platform for universities. Career offices upload institutional knowledge; students get locally-grounded career advice; counselors get pre-meeting student briefs.

## Quick Start (Demo)

> All setup files (`docker-compose.yml`, `api/`, `web/`) are included in this repo.

```bash
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
docker compose up
```

- Career office: http://localhost:3000/admin?key=demo2026
- Student advisor: http://localhost:3000/student

## Architecture

- **Backend**: FastAPI (Python) — embeddings via sentence-transformers (in-process), vector DB via Qdrant (local volume), LLM via Anthropic Claude
- **Frontend**: Next.js 14
- **Data stays local**: only Anthropic Claude API call leaves the deployment (PDPA-compliant)

## Production Deployment (AWS ap-southeast-1)

See `terraform/` — deploy to your institution's own AWS account.
