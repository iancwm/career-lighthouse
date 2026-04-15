FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies (no dev extras, frozen lockfile)
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# Pre-download the embedding model into the image so first boot is fast
RUN uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

# Run as non-root user to limit blast radius on container escape
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
RUN mkdir -p /home/appuser/.cache/uv
RUN chown -R appuser:appgroup /app
RUN chown -R appuser:appgroup /home/appuser
COPY entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh
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

EXPOSE 8000

# Health check — uses stdlib urllib so no curl dependency needed
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
