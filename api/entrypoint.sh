#!/bin/sh
set -eu

prepare_dir() {
  mkdir -p "$1"
  # Explicit error reporting: chown failure means the volume is owned by root
  # and appuser will not be able to write to it.  Surface the error immediately
  # instead of swallowing it and letting the application fail later.
  if ! chown -R appuser:appgroup "$1" 2>/dev/null; then
    echo "WARNING: could not chown $1 to appuser:appgroup — writes may fail" >&2
  fi
}

prepare_file_parent() {
  prepare_dir "$(dirname "$1")"
}

# Named Docker volumes and bind mounts arrive owned by root on first use.
# Initialize every writable directory/file parent, then hand off to appuser.
prepare_dir "${SESSIONS_DIR:-/app/data/sessions}"
prepare_dir "${DATA_PATH:-/app/data/qdrant}"
prepare_dir "${CAREER_PROFILES_DIR:-/app/knowledge/career_profiles}"
prepare_dir "${EMPLOYERS_DIR:-/app/knowledge/employers}"
prepare_dir "${DRAFT_TRACKS_DIR:-/app/knowledge/draft_tracks}"
prepare_dir "${CAREER_PROFILE_HISTORY_DIR:-/app/knowledge/career_profiles_history}"
prepare_dir "${SENTENCE_TRANSFORMERS_HOME:-/app/.cache}"
prepare_dir "${UV_CACHE_DIR:-/home/appuser/.cache/uv}"
prepare_file_parent "${QUERY_LOG_PATH:-/app/logs/query_log.jsonl}"
prepare_file_parent "${CAREER_TRACKS_REGISTRY_PATH:-/app/knowledge/career_tracks.yaml}"
prepare_file_parent "${TRACK_PUBLISH_JOURNAL_PATH:-/app/logs/track_publish_journal.jsonl}"
prepare_file_parent "${TRACK_PUBLISH_LOG_PATH:-/app/logs/track_publish_log.jsonl}"
prepare_file_parent "${TRACKS_VERSION_PATH:-/app/knowledge/.tracks-version}"

# Drop privileges and exec uvicorn directly from the virtual environment.
# Using the .venv binary is more reliable than `uv run` in production:
#   - one fewer process in the exec chain
#   - no dependency on uv being correctly configured at runtime
#   - avoids `uv run`'s environment-detection overhead
export HOME=/home/appuser
export UV_CACHE_DIR=/home/appuser/.cache/uv

exec runuser -u appuser -- /app/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
