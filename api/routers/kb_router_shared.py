"""Shared helpers for the split KB routers."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from pydantic import BaseModel

from config import settings
from models_employers import EmployerDetail
from models_tracks import DraftTrackDetail
from services import trace_adapter
from services.career_profiles import default_profiles_dir
from services.employer_store import as_list, default_employers_dir

logger = logging.getLogger(__name__)


def _read_langfuse_trace_log(*args, **kwargs):
    return trace_adapter.read_langfuse_trace_log(*args, **kwargs)


def _read_llm_trace_log(*args, **kwargs):
    kwargs.setdefault("trace_path", getattr(settings, "llm_trace_log_path", ""))
    return trace_adapter.read_llm_trace_log(*args, **kwargs)


class TestQueryRequest(BaseModel):
    query: str


def build_employer_detail(emp: dict) -> EmployerDetail:
    """Normalize a raw employer YAML dict into the API response model."""
    return EmployerDetail(
        slug=emp.get("slug", ""),
        employer_name=emp.get("employer_name", ""),
        tracks=as_list(emp.get("tracks")),
        ep_requirement=emp.get("ep_requirement"),
        intake_seasons=as_list(emp.get("intake_seasons")),
        singapore_headcount_estimate=emp.get("singapore_headcount_estimate"),
        application_process=emp.get("application_process"),
        counsellor_contact=emp.get("counsellor_contact"),
        notes=emp.get("notes"),
        structured=dict(emp.get("structured") or {}),
        last_updated=emp.get("last_updated"),
        completeness=emp.get("completeness", "amber"),
    )


def profiles_dir() -> Path:
    return Path(
        os.environ.get(
            "CAREER_PROFILES_DIR",
            str(default_profiles_dir()),
        )
    )


def employers_dir() -> Path:
    return Path(
        os.environ.get(
            "EMPLOYERS_DIR",
            str(default_employers_dir()),
        )
    )


def draft_ready_for_publish(detail: DraftTrackDetail) -> bool:
    """Return True if the draft has the minimum required fields to publish."""
    required_text = [
        detail.track_name,
        detail.ep_sponsorship,
        detail.recruiting_timeline,
        detail.salary_range_2024,
        detail.typical_background,
    ]
    return (
        all(str(value).strip() for value in required_text)
        and len(detail.top_employers_smu) > 0
        and len(detail.entry_paths) > 0
        and len(detail.match_keywords) > 0
    )
