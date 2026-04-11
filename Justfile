# Career Lighthouse — developer task runner
# Run `just` to see all available recipes

default:
    @just --list

# ── Docker ───────────────────────────────────────────────────────────────────

# Build and start all services (uses Docker layer cache for fast rebuilds)
up:
    docker compose up --build

# Full clean rebuild — bypasses Docker cache. Use when the build is broken.
rebuild:
    docker compose down
    docker builder prune -f
    docker compose build --no-cache
    docker compose up -d

# Stop all services
down:
    docker compose down

# Stop services and wipe qdrant_data volume
clean:
    docker compose down -v

# Follow logs for all services
logs:
    docker compose logs -f

# Explain where knowledge and logs are stored when running via Docker
where-data:
    @echo "Local Docker storage paths:"
    @echo "  Employer YAMLs:       ./knowledge/employers/        -> /app/knowledge/employers/"
    @echo "  Career profile YAMLs: ./knowledge/career_profiles/  -> /app/knowledge/career_profiles/"
    @echo "  Query log:            ./logs/query_log.jsonl        -> /app/logs/query_log.jsonl"
    @echo "  Uploaded documents:   stored in Qdrant, not as files under ./knowledge/"
    @echo ""
    @echo "What persists where:"
    @echo "  Employer/Profile edits from the admin UI write back to ./knowledge/"
    @echo "  Document uploads via /api/ingest are embedded and stored in Qdrant"
    @echo "  Student query logs are appended to ./logs/query_log.jsonl"

# ── Local development ─────────────────────────────────────────────────────────

# Install all dependencies (uv-managed API deps + npm ci for web)
install:
    cd api && uv sync --extra dev --frozen
    cd web && npm ci

# Refresh the API lockfile after editing api/pyproject.toml
lock-api:
    cd api && uv lock

# Start a local Qdrant server (required for dev-api)
qdrant:
    docker run --rm -p 6333:6333 -v $(pwd)/data/qdrant:/qdrant/storage qdrant/qdrant

# Run the API dev server locally with hot-reload (requires: just qdrant in another terminal)
dev-api:
    cd api && QDRANT_URL=http://localhost:6333 uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run the Next.js dev server
dev-web:
    cd web && npm run dev

# ── Tests ─────────────────────────────────────────────────────────────────────

# Run all tests
test: test-api test-web

# Run API tests
test-api:
    cd api && uv sync --extra dev --frozen && uv run python -m pytest

# Run web tests
test-web:
    cd web && npm run test -- --run

# Analyze the current diff against TODOs/specs and summarize progress before pushing
push-changes:
    python3 scripts/push_changes.py

# ── Demo data ─────────────────────────────────────────────────────────────────

# Ingest all demo-data files into the running API (requires: just up)
ingest:
    #!/usr/bin/env bash
    set -euo pipefail
    for f in demo-data/*.txt; do
        echo "Ingesting $f ..."
        curl -sf -F "file=@$f" http://localhost:8000/api/ingest
        echo
    done
    echo "All demo files ingested."
