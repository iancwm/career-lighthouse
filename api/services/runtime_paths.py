"""Runtime storage path helpers for local Docker and deployed environments."""
from __future__ import annotations

import os
import uuid
from pathlib import Path


def repo_root() -> Path:
    """Return the repository root regardless of whether we are in Docker."""
    return Path(__file__).resolve().parents[2]


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default)))


def default_sessions_dir() -> Path:
    return repo_root() / "data" / "sessions"


def default_data_path() -> Path:
    return repo_root() / "data" / "qdrant"


def default_profiles_dir() -> Path:
    return repo_root() / "knowledge" / "career_profiles"


def default_employers_dir() -> Path:
    return repo_root() / "knowledge" / "employers"


def default_drafts_dir() -> Path:
    return repo_root() / "knowledge" / "draft_tracks"


def default_registry_path() -> Path:
    return repo_root() / "knowledge" / "career_tracks.yaml"


def default_history_dir() -> Path:
    return repo_root() / "knowledge" / "career_profiles_history"


def default_query_log_path() -> Path:
    return repo_root() / "logs" / "query_log.jsonl"


def default_publish_journal_path() -> Path:
    return repo_root() / "logs" / "track_publish_journal.jsonl"


def default_publish_log_path() -> Path:
    return repo_root() / "logs" / "track_publish_log.jsonl"


def default_tracks_version_path() -> Path:
    return repo_root() / "knowledge" / ".tracks-version"


def default_sentence_transformers_home() -> Path:
    return repo_root() / ".cache"


def default_uv_cache_dir() -> Path:
    return repo_root() / ".cache" / "uv"


def runtime_storage_targets() -> dict[str, tuple[str, Path]]:
    """Return the writable storage roots that should exist at startup."""
    return {
        "SESSIONS_DIR": ("dir", _env_path("SESSIONS_DIR", default_sessions_dir())),
        "DATA_PATH": ("dir", _env_path("DATA_PATH", default_data_path())),
        "CAREER_PROFILES_DIR": ("dir", _env_path("CAREER_PROFILES_DIR", default_profiles_dir())),
        "EMPLOYERS_DIR": ("dir", _env_path("EMPLOYERS_DIR", default_employers_dir())),
        "DRAFT_TRACKS_DIR": ("dir", _env_path("DRAFT_TRACKS_DIR", default_drafts_dir())),
        "CAREER_PROFILE_HISTORY_DIR": ("dir", _env_path("CAREER_PROFILE_HISTORY_DIR", default_history_dir())),
        "SENTENCE_TRANSFORMERS_HOME": ("dir", _env_path("SENTENCE_TRANSFORMERS_HOME", default_sentence_transformers_home())),
        "UV_CACHE_DIR": ("dir", _env_path("UV_CACHE_DIR", default_uv_cache_dir())),
        "QUERY_LOG_PATH": ("file", _env_path("QUERY_LOG_PATH", default_query_log_path())),
        "CAREER_TRACKS_REGISTRY_PATH": ("file", _env_path("CAREER_TRACKS_REGISTRY_PATH", default_registry_path())),
        "TRACK_PUBLISH_JOURNAL_PATH": ("file", _env_path("TRACK_PUBLISH_JOURNAL_PATH", default_publish_journal_path())),
        "TRACK_PUBLISH_LOG_PATH": ("file", _env_path("TRACK_PUBLISH_LOG_PATH", default_publish_log_path())),
        "TRACKS_VERSION_PATH": ("file", _env_path("TRACKS_VERSION_PATH", default_tracks_version_path())),
    }


def ensure_writable_directory(path: Path, label: str) -> None:
    """Create *path* and verify the current process can write to it.

    The probe file is created under the directory itself and removed
    immediately after the write check succeeds.
    """
    path.mkdir(parents=True, exist_ok=True)
    probe = path / f".write-check-{os.getpid()}-{uuid.uuid4().hex}"
    try:
        with open(probe, "w", encoding="utf-8") as handle:
            handle.write("ok")
    except OSError as exc:
        raise RuntimeError(f"{label} is not writable at {path}: {exc}") from exc
    finally:
        probe.unlink(missing_ok=True)


def validate_runtime_storage() -> None:
    """Fail fast if any configured storage root is missing or unwritable."""
    for label, (kind, path) in runtime_storage_targets().items():
        if kind == "dir":
            ensure_writable_directory(path, label)
        else:
            ensure_writable_directory(path.parent, label)
