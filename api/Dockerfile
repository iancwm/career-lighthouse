FROM python:3.11-slim

# Enable BuildKit for cache mount support
ENV DOCKER_BUILDKIT=1

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies with persistent cache across builds
# Only re-downloads NEW packages; existing cache speeds up rebuilds
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen

# Pre-download the embedding model into the image so first boot is fast
COPY <<EOF /tmp/preload.py
from sentence_transformers import SentenceTransformer
SentenceTransformer('all-MiniLM-L6-v2')
EOF
RUN --mount=type=cache,target=/root/.cache/huggingface \
    uv run python /tmp/preload.py && rm /tmp/preload.py

COPY . .

# Run as non-root user to limit blast radius on container escape
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser && \
    mkdir -p /home/appuser/.cache/uv /app/.cache && \
    chown -R appuser:appgroup /home/appuser /app/.cache
RUN chown -R appuser:appgroup /app
ENV HOME=/home/appuser
ENV UV_CACHE_DIR=/home/appuser/.cache/uv
ENV DATA_PATH=/app/data/qdrant
ENV SESSIONS_DIR=/app/data/sessions
ENV CAREER_PROFILES_DIR=/app/knowledge/career_profiles
ENV EMPLOYERS_DIR=/app/knowledge/employers
ENV DRAFT_TRACKS_DIR=/app/knowledge/draft_tracks
ENV CAREER_TRACKS_REGISTRY_PATH=/app/knowledge/career_tracks.yaml
ENV CAREER_PROFILE_HISTORY_DIR=/app/knowledge/career_profiles_history
ENV TRACK_PUBLISH_JOURNAL_PATH=/app/logs/track_publish_journal.jsonl
ENV TRACK_PUBLISH_LOG_PATH=/app/logs/track_publish_log.jsonl
ENV TRACKS_VERSION_PATH=/app/knowledge/.tracks-version
ENV QUERY_LOG_PATH=/app/logs/query_log.jsonl
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache

RUN chmod 755 /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]

EXPOSE 8000

# Health check — uses stdlib urllib so no curl dependency needed
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
