"""Tests for deployment-hardening storage checks."""
from __future__ import annotations

import pytest


def test_validate_runtime_storage_creates_configured_paths(tmp_path, monkeypatch):
    from services.runtime_paths import validate_runtime_storage

    monkeypatch.setenv("SESSIONS_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("DATA_PATH", str(tmp_path / "data" / "qdrant"))
    monkeypatch.setenv("CAREER_PROFILES_DIR", str(tmp_path / "knowledge" / "career_profiles"))
    monkeypatch.setenv("EMPLOYERS_DIR", str(tmp_path / "knowledge" / "employers"))
    monkeypatch.setenv("DRAFT_TRACKS_DIR", str(tmp_path / "knowledge" / "draft_tracks"))
    monkeypatch.setenv("CAREER_PROFILE_HISTORY_DIR", str(tmp_path / "knowledge" / "career_profiles_history"))
    monkeypatch.setenv("SENTENCE_TRANSFORMERS_HOME", str(tmp_path / ".cache"))
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / ".cache" / "uv"))
    monkeypatch.setenv("QUERY_LOG_PATH", str(tmp_path / "logs" / "query_log.jsonl"))
    monkeypatch.setenv("CAREER_TRACKS_REGISTRY_PATH", str(tmp_path / "knowledge" / "career_tracks.yaml"))
    monkeypatch.setenv("TRACK_PUBLISH_JOURNAL_PATH", str(tmp_path / "logs" / "track_publish_journal.jsonl"))
    monkeypatch.setenv("TRACK_PUBLISH_LOG_PATH", str(tmp_path / "logs" / "track_publish_log.jsonl"))
    monkeypatch.setenv("TRACKS_VERSION_PATH", str(tmp_path / "knowledge" / ".tracks-version"))

    validate_runtime_storage()

    assert (tmp_path / "sessions").exists()
    assert (tmp_path / "knowledge" / "career_profiles").exists()
    assert (tmp_path / "knowledge" / "employers").exists()
    assert (tmp_path / "logs").exists()


def test_validate_runtime_storage_fails_on_unwritable_root(tmp_path, monkeypatch):
    from services.runtime_paths import validate_runtime_storage

    unwritable = tmp_path / "sessions"
    unwritable.mkdir()
    unwritable.chmod(0o500)
    monkeypatch.setenv("SESSIONS_DIR", str(unwritable))

    try:
        with pytest.raises(RuntimeError, match="SESSIONS_DIR"):
            validate_runtime_storage()
    finally:
        unwritable.chmod(0o700)


def test_session_store_fails_fast_on_unwritable_root(tmp_path, monkeypatch):
    import services.session_store as ss_module
    from services.session_store import SessionStorageError, SessionStore

    unwritable = tmp_path / "sessions"
    unwritable.mkdir()
    unwritable.chmod(0o500)

    original_dir = ss_module._SESSIONS_DIR
    SessionStore._instance = None
    monkeypatch.setenv("SESSIONS_DIR", str(unwritable))
    ss_module._SESSIONS_DIR = unwritable

    try:
        with pytest.raises(SessionStorageError):
            SessionStore()
    finally:
        ss_module._SESSIONS_DIR = original_dir
        SessionStore._instance = None
        unwritable.chmod(0o700)
