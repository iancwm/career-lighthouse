FROM python:3.11-slim

# Pin uv to an exact version for reproducible builds.
# DO NOT use 'latest' — it can silently introduce breaking changes between builds.
# Bump this deliberately and test before merging.
COPY --from=ghcr.io/astral-sh/uv:0.5.18 /uv /usr/local/bin/uv

WORKDIR /app

# Create the non-root user BEFORE copying application code so the COPY --chown
# flag below can assign ownership in one pass, avoiding a separate chown -R /app
# traversal after the fact (which is slow and creates an unnecessary extra layer).
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup --home /home/appuser appuser && \
    mkdir -p /home/appuser/.cache/uv /app/.cache && \
    chown appuser:appgroup /home/appuser /app/.cache

# Install Python dependencies.
# uv sync writes the .venv into the current WORKDIR (/app).
# The BuildKit cache mount speeds up rebuilds by reusing the uv download cache
# across builds; it is NOT part of the image layer.
# NOTE: BuildKit must be active at build time (Docker >= 23 enables it by default;
#       for older setups pass DOCKER_BUILDKIT=1 to the *host* shell, not in here).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen

# Set the model cache paths BEFORE the preload step so the downloaded files land
# inside the image filesystem at /app/.cache — not inside a BuildKit cache mount
# that disappears after the build step.  Both env vars must point to the same
# subtree so sentence_transformers and the HuggingFace Hub agree on the location.
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache
ENV HF_HOME=/app/.cache/huggingface

# Pre-download the embedding model into the image layer so first boot is fast.
# Trade-off: this adds ~90 MB to the image and re-downloads if the layer cache
# misses (i.e. when uv.lock changes).  That is preferable to a slow/failing
# first container startup in production.
RUN uv run python -c \
    "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy application code.  --chown sets ownership in a single COPY pass instead
# of requiring a follow-up chown -R over the entire /app tree.
COPY --chown=appuser:appgroup . .

# uv creates .venv as root during `uv sync`; transfer ownership so appuser can
# import packages without privilege escalation.
RUN chown -R appuser:appgroup /app/.venv

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

RUN chmod 755 /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]

EXPOSE 8000

# Health check — uses stdlib urllib so no curl dependency needed.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
