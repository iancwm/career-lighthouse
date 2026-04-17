#!/bin/sh
set -eu

prepare_dir() {
  mkdir -p "$1"
  chown -R appuser:appgroup "$1" 2>/dev/null || true
}

prepare_file_parent() {
  prepare_dir "$(dirname "$1")"
}

# The named Docker volumes and mounts come in owned by root on first use.
# Initialize the writable directories, then drop back to appuser.
prepare_dir "${SESSIONS_DIR:-/app/data/sessions}"
prepare_dir "${DATA_PATH:-/app/data/qdrant}"
prepare_dir "${CAREER_PROFILES_DIR:-/app/knowledge/career_profiles}"
prepare_dir "${EMPLOYERS_DIR:-/app/knowledge/employers}"
prepare_dir "${DRAFT_TRACKS_DIR:-/app/knowledge/draft_tracks}"
prepare_dir "${CAREER_PROFILE_HISTORY_DIR:-/app/knowledge/career_profiles_history}"
prepare_dir "${SENTENCE_TRANSFORMERS_HOME:-/app/.cache}"
prepare_dir "${UV_CACHE_DIR:-/home/appuser/.cache/uv}"
prepare_file_parent "${QUERY_LOG_PATH:-/app/logs/query_log.jsonl}"
prepare_file_parent "${LLM_TRACE_LOG_PATH:-/app/logs/llm_trace_log.jsonl}"
prepare_file_parent "${CAREER_TRACKS_REGISTRY_PATH:-/app/knowledge/career_tracks.yaml}"
prepare_file_parent "${TRACK_PUBLISH_JOURNAL_PATH:-/app/logs/track_publish_journal.jsonl}"
prepare_file_parent "${TRACK_PUBLISH_LOG_PATH:-/app/logs/track_publish_log.jsonl}"
prepare_file_parent "${TRACKS_VERSION_PATH:-/app/knowledge/.tracks-version}"

exec runuser -u appuser -- env HOME=/home/appuser UV_CACHE_DIR=/home/appuser/.cache/uv sh -lc 'cd /app && exec /usr/local/bin/uv run uvicorn main:app --host 0.0.0.0 --port 8000'
