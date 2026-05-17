"""Tiny YAML persistence helpers shared across YAML-backed stores."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class Singleton:
    """Small base for lazily-created process-local service singletons."""

    _instance = None

    def __new__(cls, *args: Any, **kwargs: Any):
        lock = getattr(cls, "_lock", None)
        if lock is None:
            return cls._get_or_create_instance()
        with lock:
            return cls._get_or_create_instance()

    @classmethod
    def _get_or_create_instance(cls):
        if cls._instance is None:
            cls._instance = super(Singleton, cls).__new__(cls)
            cls._instance._init_singleton()
        return cls._instance

    def _init_singleton(self) -> None:
        """Hook for subclasses to initialize state exactly once."""


def atomic_yaml_write(path: Path, payload: Any) -> None:
    """Atomically write a YAML document."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        yaml.safe_dump(
            payload,
            handle,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
    tmp.replace(path)
    path.chmod(0o600)


def read_yaml(path: Path) -> Any:
    """Read a YAML document if it exists, returning ``None`` for absent files."""
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def normalize_list(value: Any) -> list[Any]:
    """Normalize scalar/list YAML values into a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return [value]


def utc_now_iso() -> str:
    """Return a compact UTC ISO-8601 timestamp ending in ``Z``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def version_stamp() -> str:
    """Return a filesystem-friendly UTC version stamp."""
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def safe_slug(value: str) -> str:
    """Convert text to a conservative filesystem-safe slug."""
    text = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower())
    return re.sub(r"_+", "_", text).strip("_")


def safe_slug_is_valid(slug: str) -> bool:
    """Return True if slug is non-empty, alphanumeric+dash+underscore only, and contains no path traversal."""
    return (
        bool(slug)
        and slug.replace("_", "").replace("-", "").isalnum()
        and "/" not in slug
        and ".." not in slug
    )


def safe_int(value: object, default: int | None = None) -> int | None:
    """Cast value to int, returning default on None or conversion failure."""
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: object, default: float = 0.0) -> float:
    """Cast value to float, returning default on None or conversion failure."""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def fact_payload(fact: object) -> dict:
    """Extract the data sub-dict from a raw fact dict, falling back to the fact dict itself."""
    if not isinstance(fact, dict):
        return {}
    payload = fact.get("data")
    if isinstance(payload, dict):
        return payload
    return fact


def fact_lifecycle(fact: object) -> str:
    """Resolve the lifecycle state of a raw fact dict, mapping deleted=True to 'superseded'."""
    if not isinstance(fact, dict):
        return "active"
    lifecycle = str(fact.get("lifecycle") or "").strip().lower()
    if lifecycle in {"active", "superseded", "archived"}:
        return lifecycle
    if fact.get("deleted"):
        return "superseded"
    return "active"
