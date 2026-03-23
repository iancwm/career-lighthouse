# Career Lighthouse — developer task runner
# Run `just` to see all available recipes

default:
    @just --list

# ── Docker ───────────────────────────────────────────────────────────────────

# Build and start all services
up:
    docker compose up --build

# Stop all services
down:
    docker compose down

# Follow logs for all services
logs:
    docker compose logs -f

# Stop services and wipe qdrant_data volume
clean:
    docker compose down -v

# ── Local development ─────────────────────────────────────────────────────────

# Install all dependencies (uv sync for API, npm ci for web)
install:
    cd api && uv sync --extra dev
    cd web && npm ci

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
    cd api && uv sync --extra dev && uv run python -m pytest

# Run web tests
test-web:
    cd web && npm run test -- --run

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
