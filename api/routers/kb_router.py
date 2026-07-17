"""Compatibility shim for the split KB routers.

This module intentionally keeps a few helper exports stable for existing tests
and internal imports while the actual route handlers live in the focused
`profile_router`, `tracks_router`, `employers_router`, `facts_router`, and
`kb_admin_router` modules.
"""

from __future__ import annotations

from config import settings
from services import llm as llm_service
from services import trace_adapter
from services.kb_health import invalidate_docs_cache as _invalidate_docs_cache


def _read_langfuse_trace_log(*args, **kwargs):
    """Compatibility wrapper that preserves patchable module dependencies."""
    return trace_adapter.read_langfuse_trace_log(*args, **kwargs)


def _read_llm_trace_log(*args, **kwargs):
    """Compatibility wrapper honoring this shim's patchable settings object."""
    kwargs.setdefault("trace_path", getattr(settings, "llm_trace_log_path", ""))
    return trace_adapter.read_llm_trace_log(*args, **kwargs)

__all__ = [
    "_invalidate_docs_cache",
    "_read_langfuse_trace_log",
    "_read_llm_trace_log",
    "llm_service",
    "settings",
]
