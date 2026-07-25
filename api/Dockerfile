FROM python:3.11-slim

ARG USER_UID=1000
ARG USER_GID=1000

# python-magic is a Python wrapper around this native library. Keep the
# runtime dependency in the image so importing the upload router works.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libmagic1 \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system --gid "${USER_GID}" appgroup \
    && adduser --system --uid "${USER_UID}" --ingroup appgroup \
        --home /home/appuser appuser \
    && mkdir -p /app /app/.cache /home/appuser/.cache/uv \
    && chown -R appuser:appgroup /app /home/appuser

# Pin uv so a new upstream release does not invalidate the dependency layer.
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

WORKDIR /app
ENV HOME=/home/appuser
ENV UV_CACHE_DIR=/home/appuser/.cache/uv
ENV UV_LINK_MODE=copy

# Install dependencies as their final owner. This avoids a recursive chown
# layer copying the entire virtual environment.
COPY --chown=appuser:appgroup pyproject.toml uv.lock ./
USER appuser
RUN --mount=type=cache,target=/home/appuser/.cache/uv,uid=${USER_UID},gid=${USER_GID} \
    uv sync --no-dev --frozen --no-install-project

# The embedding model is downloaded on first use into the persistent
# transformers_cache volume mounted at /app/.cache by docker-compose.yml.
COPY --chown=appuser:appgroup . .
RUN chmod 755 /app/entrypoint.sh
USER root

ENV DATA_PATH=/app/data/qdrant
ENV SESSIONS_DIR=/app/data/sessions
ENV CAREER_PROFILES_DIR=/app/knowledge/career_profiles
ENV EMPLOYERS_DIR=/app/knowledge/employers
ENV DRAFT_TRACKS_DIR=/app/knowledge/draft_tracks
ENV CAREER_TRACKS_REGISTRY_PATH=/app/knowledge/career_tracks.yaml
ENV CAREER_PROFILE_HISTORY_DIR=/app/knowledge/career_profiles_history
ENV EMPLOYER_HISTORY_DIR=/app/knowledge/employers_history
ENV TRACK_PUBLISH_JOURNAL_PATH=/app/logs/track_publish_journal.jsonl
ENV TRACK_PUBLISH_LOG_PATH=/app/logs/track_publish_log.jsonl
ENV TRACKS_VERSION_PATH=/app/knowledge/.tracks-version
ENV QUERY_LOG_PATH=/app/logs/query_log.jsonl
ENV LLM_TRACE_LOG_PATH=/app/logs/llm_trace_log.jsonl
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache

ENTRYPOINT ["/app/entrypoint.sh"]

EXPOSE 8000

# Health check — uses stdlib urllib so no curl dependency needed
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
