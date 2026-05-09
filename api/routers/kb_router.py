"""Compatibility shim for the split KB routers.

This module intentionally keeps a few helper exports stable for existing tests
and internal imports while the actual route handlers live in the focused
`profile_router`, `tracks_router`, `employers_router`, `facts_router`, and
`kb_admin_router` modules.
"""

from __future__ import annotations

from config import settings
from routers.kb_router_shared import _read_langfuse_trace_log, _read_llm_trace_log
from services.kb_health import invalidate_docs_cache as _invalidate_docs_cache

__all__ = [
    "_invalidate_docs_cache",
    "_read_langfuse_trace_log",
    "_read_llm_trace_log",
    "settings",
]
