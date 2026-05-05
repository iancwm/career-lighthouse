"""Helpers for adapting third-party SDK objects into plain API shapes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from services.shared_yaml import safe_int


def coerce_mapping(value: object) -> dict[str, Any] | None:
    """Best-effort conversion of SDK objects into plain dicts."""
    if isinstance(value, dict):
        return value
    for method_name in ("model_dump", "dict", "to_dict"):
        method = getattr(value, method_name, None)
        if callable(method):
            try:
                dumped = method()
            except Exception:
                continue
            if isinstance(dumped, dict):
                return dumped
    return None


def coerce_sequence(value: object) -> list[object]:
    """Best-effort conversion of SDK collections into plain lists."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    mapping = coerce_mapping(value)
    if mapping:
        for key in ("data", "items", "traces", "observations"):
            candidate = mapping.get(key)
            if isinstance(candidate, list):
                return candidate
    for name in ("data", "items", "traces", "observations"):
        if hasattr(value, name):
            candidate = getattr(value, name)
            if isinstance(candidate, list):
                return candidate
    return [value]


def get_value(value: object, *names: str, default: Any = None) -> Any:
    """Return the first non-None value found by dict key or object attribute."""
    if isinstance(value, dict):
        for name in names:
            if name in value and value[name] is not None:
                return value[name]
    for name in names:
        if hasattr(value, name):
            candidate = getattr(value, name)
            if candidate is not None:
                return candidate
    return default


def format_timestamp(value: object) -> str:
    """Normalize a datetime or string timestamp value to an ISO-8601 UTC string."""
    if isinstance(value, datetime):
        ts = value
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc).isoformat()
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    return str(value)


def estimate_input_chars(payload: object) -> int:
    """Estimate the character length of an LLM call's input payload."""
    mapping = coerce_mapping(payload)
    if not mapping:
        return len(str(payload or ""))

    system_chars = safe_int(mapping.get("system_chars"), 0) or 0
    messages = mapping.get("messages")
    message_chars = 0
    if isinstance(messages, list):
        for message in messages:
            if not isinstance(message, dict):
                continue
            message_chars += safe_int(message.get("content_chars"), 0) or 0
    if system_chars or message_chars:
        return system_chars + message_chars
    return len(str(payload or ""))


def estimate_output_chars(payload: object) -> int:
    """Estimate the character length of an LLM call's output payload."""
    if payload is None:
        return 0
    if isinstance(payload, str):
        return len(payload)
    mapping = coerce_mapping(payload)
    if mapping and "content" in mapping:
        content = mapping.get("content")
        if isinstance(content, str):
            return len(content)
    return len(str(payload))


def truncate_preview(text: str | None, limit: int = 500) -> str:
    """Trim a string to at most `limit` characters, appending an ellipsis when truncated."""
    if not text:
        return ""
    clean = text.strip()
    if len(clean) <= limit:
        return clean
    return clean[:limit] + "…"


def preview_input(payload: object) -> str:
    """Extract a human-readable preview of an LLM input payload."""
    mapping = coerce_mapping(payload)
    if not mapping:
        return truncate_preview(str(payload or ""))

    messages = mapping.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            if not isinstance(message, dict):
                continue
            preview = message.get("content_preview")
            if preview:
                return truncate_preview(str(preview))
    system_preview = mapping.get("system_preview")
    if system_preview:
        return truncate_preview(str(system_preview))
    return truncate_preview(json.dumps(mapping, ensure_ascii=False))


def preview_output(payload: object) -> str:
    """Extract a human-readable preview of an LLM output payload."""
    mapping = coerce_mapping(payload)
    if mapping:
        for key in ("content_preview", "text", "output", "message", "content"):
            value = mapping.get(key)
            if isinstance(value, str) and value.strip():
                return truncate_preview(value)
    if isinstance(payload, str):
        return truncate_preview(payload)
    return truncate_preview(str(payload or ""))
