"""Tiny YAML persistence helpers shared across YAML-backed stores."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def atomic_yaml_write(path: Path, payload: Any) -> None:
    """Atomically write a YAML document."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, allow_unicode=True, default_flow_style=False, sort_keys=False)
    tmp.replace(path)


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
