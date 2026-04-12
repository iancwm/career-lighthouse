"""Draft track storage and publish helpers.

This module powers the counsellor-owned track publishing workflow:
  - draft track YAMLs in knowledge/draft_tracks/
  - registry entries in knowledge/career_tracks.yaml
  - published track history in knowledge/career_profiles_history/
  - lightweight audit / journal logs in logs/

The implementation is intentionally file-backed so it matches the current
career profile and employer storage model and works in local Docker with the
existing bind mounts.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

import yaml

from models import DraftTrackDetail, TrackRegistryEntry, TrackVersionInfo
from services.career_profiles import _default_profiles_dir

logger = logging.getLogger(__name__)


def _default_knowledge_root() -> Path:
    profiles_dir = _default_profiles_dir()
    return profiles_dir.parent


def _default_drafts_dir() -> Path:
    return _default_knowledge_root() / "draft_tracks"


def _default_registry_path() -> Path:
    return _default_knowledge_root() / "career_tracks.yaml"


def _default_history_dir() -> Path:
    return _default_knowledge_root() / "career_profiles_history"


def _default_logs_dir() -> Path:
    return _default_knowledge_root().parent / "logs"


def _default_publish_journal_path() -> Path:
    return _default_logs_dir() / "track_publish_journal.jsonl"


def _default_publish_audit_log_path() -> Path:
    return _default_logs_dir() / "track_publish_log.jsonl"


def _default_tracks_version_path() -> Path:
    return _default_knowledge_root() / ".tracks-version"


def _drafts_dir() -> Path:
    return Path(os.environ.get("DRAFT_TRACKS_DIR", str(_default_drafts_dir())))


def _registry_path() -> Path:
    return Path(os.environ.get("CAREER_TRACKS_REGISTRY_PATH", str(_default_registry_path())))


def _history_dir() -> Path:
    return Path(os.environ.get("CAREER_PROFILE_HISTORY_DIR", str(_default_history_dir())))


def _publish_journal_path() -> Path:
    return Path(os.environ.get("TRACK_PUBLISH_JOURNAL_PATH", str(_default_publish_journal_path())))


def _publish_audit_log_path() -> Path:
    return Path(os.environ.get("TRACK_PUBLISH_LOG_PATH", str(_default_publish_audit_log_path())))


def _tracks_version_path() -> Path:
    return Path(os.environ.get("TRACKS_VERSION_PATH", str(_default_tracks_version_path())))


def _profiles_dir() -> Path:
    return Path(os.environ.get("CAREER_PROFILES_DIR", str(_default_profiles_dir())))


def _slug_is_safe(slug: str) -> bool:
    return bool(slug) and slug.replace("_", "").isalnum() and "/" not in slug and ".." not in slug


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _version_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


def _atomic_yaml_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    tmp.replace(path)


def _atomic_text_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    tmp.replace(path)


def _normalise_keywords(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        token = str(value).strip()
        if not token:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(token)
    return result


def _registry_payload(entries: list[TrackRegistryEntry]) -> dict:
    return {
        "tracks": [
            {
                "slug": item.slug,
                "label": item.label,
                "status": item.status,
                "last_published": item.last_published,
            }
            for item in entries
        ]
    }


class TrackDraftStore:
    """Singleton for draft tracks and registry-backed publish helpers."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
            cls._instance._lock = Lock()
        return cls._instance

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._drafts: dict[str, dict] = {}
        drafts_dir = _drafts_dir()
        if drafts_dir.exists():
            for yaml_path in sorted(drafts_dir.glob("*.yaml")):
                try:
                    with open(yaml_path, encoding="utf-8") as f:
                        payload = yaml.safe_load(f) or {}
                    if isinstance(payload, dict):
                        payload.setdefault("slug", yaml_path.stem)
                        self._drafts[yaml_path.stem] = payload
                except Exception as exc:
                    logger.warning("TrackDraftStore: failed to load %s: %s", yaml_path.name, exc)
        self._loaded = True

    def invalidate(self) -> None:
        self._loaded = False

    def list_drafts(self) -> list[DraftTrackDetail]:
        self._ensure_loaded()
        items = [DraftTrackDetail(**payload) for payload in self._drafts.values()]
        items.sort(key=lambda item: (item.last_updated or "", item.slug), reverse=True)
        return items

    def get_draft(self, slug: str) -> DraftTrackDetail | None:
        self._ensure_loaded()
        payload = self._drafts.get(slug)
        return DraftTrackDetail(**payload) if payload else None

    def save_draft(self, detail: DraftTrackDetail) -> DraftTrackDetail:
        if not _slug_is_safe(detail.slug):
            raise ValueError("Invalid slug format.")
        payload = detail.model_dump()
        payload["slug"] = detail.slug
        payload["track_name"] = detail.track_name.strip()
        payload["status"] = detail.status or "draft"
        payload["match_keywords"] = _normalise_keywords(detail.match_keywords)
        payload["last_updated"] = _today()
        _atomic_yaml_write(_drafts_dir() / f"{detail.slug}.yaml", payload)
        self.invalidate()
        return DraftTrackDetail(**payload)

    def ensure_registry_exists(self) -> list[TrackRegistryEntry]:
        path = _registry_path()
        if path.exists():
            return self.list_registry()

        entries: list[TrackRegistryEntry] = []
        for yaml_path in sorted(_profiles_dir().glob("*.yaml")):
            slug = yaml_path.stem
            if not _slug_is_safe(slug):
                raise ValueError(f"Invalid existing profile slug: {slug}")
            with open(yaml_path, encoding="utf-8") as f:
                payload = yaml.safe_load(f) or {}
            entries.append(TrackRegistryEntry(
                slug=slug,
                label=str(payload.get("career_type") or slug).strip(),
                status="active",
                last_published=None,
            ))
        _atomic_yaml_write(path, _registry_payload(entries))
        return entries

    def list_registry(self) -> list[TrackRegistryEntry]:
        path = _registry_path()
        if not path.exists():
            return self.ensure_registry_exists()
        with open(path, encoding="utf-8") as f:
            payload = yaml.safe_load(f) or {}
        items = payload.get("tracks") or []
        result = [TrackRegistryEntry(**item) for item in items if isinstance(item, dict)]
        result.sort(key=lambda item: item.slug)
        return result

    def list_history(self, slug: str) -> list[TrackVersionInfo]:
        versions: list[TrackVersionInfo] = []
        history_dir = _history_dir() / slug
        if not history_dir.exists():
            return versions
        for yaml_path in sorted(history_dir.glob("*.yaml"), reverse=True):
            version = yaml_path.stem
            versions.append(TrackVersionInfo(
                version=version,
                published_at=version,
                filename=yaml_path.name,
            ))
        return versions

    def publish_draft(self, slug: str, actor: str = "system") -> str:
        with self._lock:
            draft = self.get_draft(slug)
            if draft is None:
                raise FileNotFoundError(f"Draft '{slug}' not found.")

            version = _version_stamp()
            journal_path = _publish_journal_path()
            _append_jsonl(journal_path, {
                "ts": datetime.now(timezone.utc).isoformat(),
                "action": "publish_started",
                "slug": slug,
                "version": version,
                "actor": actor,
            })

            published_path = _profiles_dir() / f"{slug}.yaml"
            previous_payload = None
            if published_path.exists():
                with open(published_path, encoding="utf-8") as f:
                    previous_payload = yaml.safe_load(f) or {}
                history_path = _history_dir() / slug / f"{version}.yaml"
                _atomic_yaml_write(history_path, previous_payload)

            published_payload = {
                "career_type": draft.track_name.strip(),
                "match_description": (draft.match_description or f"{draft.track_name} {' '.join(draft.match_keywords)}").strip(),
                "match_keywords": _normalise_keywords(draft.match_keywords),
                "match_cosine": False,
                "structured": draft.structured or {
                    "sponsorship_tier": "",
                    "compass_points_typical": "",
                    "salary_min_sgd": None,
                    "salary_max_sgd": None,
                    "ep_realistic": bool(draft.international_realistic),
                },
                "ep_sponsorship": draft.ep_sponsorship,
                "compass_score_typical": draft.compass_score_typical,
                "top_employers_smu": draft.top_employers_smu,
                "recruiting_timeline": draft.recruiting_timeline,
                "international_realistic": draft.international_realistic,
                "entry_paths": draft.entry_paths,
                "salary_range_2024": draft.salary_range_2024,
                "typical_background": draft.typical_background,
                "counselor_contact": draft.counselor_contact,
                "notes": draft.notes,
            }

            _atomic_yaml_write(published_path, published_payload)

            registry = self.list_registry()
            updated = False
            for item in registry:
                if item.slug == slug:
                    item.label = draft.track_name.strip()
                    item.status = "active"
                    item.last_published = version
                    updated = True
                    break
            if not updated:
                registry.append(TrackRegistryEntry(
                    slug=slug,
                    label=draft.track_name.strip(),
                    status="active",
                    last_published=version,
                ))
            registry.sort(key=lambda item: item.slug)
            _atomic_yaml_write(_registry_path(), _registry_payload(registry))

            draft_payload = draft.model_dump()
            draft_payload["status"] = "published"
            draft_payload["archived_at"] = _today()
            draft_payload["last_updated"] = _today()
            _atomic_yaml_write(_drafts_dir() / f"{slug}.yaml", draft_payload)

            _append_jsonl(_publish_audit_log_path(), {
                "ts": datetime.now(timezone.utc).isoformat(),
                "actor": actor,
                "action": "publish_track",
                "slug": slug,
                "from_version": "none" if previous_payload is None else "previous",
                "to_version": version,
            })
            _append_jsonl(journal_path, {
                "ts": datetime.now(timezone.utc).isoformat(),
                "action": "publish_completed",
                "slug": slug,
                "version": version,
                "actor": actor,
                "source_refs": [ref.model_dump() for ref in draft.source_refs],
            })
            _atomic_text_write(_tracks_version_path(), datetime.now(timezone.utc).isoformat())
            self.invalidate()
            return version

    def rollback_track(self, slug: str, actor: str = "system") -> str:
        with self._lock:
            versions = self.list_history(slug)
            if not versions:
                raise FileNotFoundError(f"No rollback history for '{slug}'.")
            target = versions[0]
            history_path = _history_dir() / slug / target.filename
            with open(history_path, encoding="utf-8") as f:
                payload = yaml.safe_load(f) or {}
            _atomic_yaml_write(_profiles_dir() / f"{slug}.yaml", payload)
            _append_jsonl(_publish_audit_log_path(), {
                "ts": datetime.now(timezone.utc).isoformat(),
                "actor": actor,
                "action": "rollback_track",
                "slug": slug,
                "to_version": target.version,
            })
            _atomic_text_write(_tracks_version_path(), datetime.now(timezone.utc).isoformat())
            self.invalidate()
            return target.version


def get_track_draft_store() -> TrackDraftStore:
    return TrackDraftStore()


def read_publish_journal() -> list[dict]:
    """Read all entries from the track publish journal, newest first."""
    path = _publish_journal_path()
    if not path.exists():
        return []
    entries: list[dict] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except Exception as exc:
        logger.warning("read_publish_journal: failed to read %s: %s", path, exc)
    entries.reverse()
    return entries
