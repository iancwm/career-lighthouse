# api/routers/kb_router.py
"""KB observability and diff-first ingestion endpoints.

POST  /api/kb/test-query                      — test a query, returns top-5 chunks with scores
GET   /api/kb/health                          — KB health metrics for the admin dashboard
POST  /api/kb/analyse                         — analyse counsellor input, return diff (no writes)
POST  /api/kb/commit-analysis                 — commit a counsellor-approved diff to KB and YAMLs
DELETE /api/kb/employers/{slug}               — soft-delete (renames to *.yaml.disabled)
PATCH  /api/kb/employers/{slug}/restore       — restore a soft-deleted employer

Auth note: These endpoints are protected by the router-level `require_admin_key`
dependency and by Next.js middleware (web/middleware.ts). The remaining auth
follow-up is migrating the admin key transport off the query param.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional, Literal

import numpy as np
import yaml
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from starlette.requests import Request
from pydantic import BaseModel

from dependencies import get_embedder, get_vector_store, require_admin_key
from models_employers import (
    EmployerDetail,
    EmployerHistoryVersion,
)
from models_kb import (
    AlreadyCovered,
    DocCoverageItem,
    KBAnalysisResult,
    KBCommitRequest,
    KBCommitResponse,
    KBHealthResponse,
    IngestResponse,
    LLMTraceEntry,
    LLMWorkflowDetail,
    LLMWorkflowSummary,
    LowConfidenceQuery,
    OverlapPair,
    TestQueryResult,
)
from models_facts import FactGroupResponse, FactQueryResponse
from models_tracks import (
    DraftTrackDetail,
    SourceRef,
    TrackPublishResponse,
    TrackReferenceDetail,
    TrackRegistryEntry,
    TrackVersionInfo,
)
from services import health_cache
from services.career_profiles import (
    CareerProfileStore,
    get_career_profile_store,
    default_profiles_dir,
    derive_structured_fields,
)
from services.employer_store import (
    EmployerEntityStore,
    get_employer_store,
    default_employers_dir,
    compute_completeness,
    as_list,
)
from services.fact_store import group_facts, list_facts
from services.shared_yaml import safe_slug_is_valid
from services import trace_adapter
from services.trace_adapter import (
    _observation_to_trace_entries,
    get_workflow_detail,
    list_recent as list_recent_llm_traces,
    list_workflow_summaries,
)
from services.embedder import Embedder
from services.kb_health import assemble_kb_health, invalidate_docs_cache
from services.vector_store import VectorStore
from services.kb_ingestion_service import (
    analyse_counsellor_input,
    extract_generation_input,
    merge_source_refs,
    retrieve_generation_chunks,
)
from services import llm as llm_service
from services.llm import extract_facts_from_prose
from config import settings
from cfg import kb_cfg, career_profiles_cfg
from services.track_drafts import (
    TrackDraftStore,
    get_track_draft_store,
    read_publish_journal,
)
from services.kb_writer import apply_employer_diff, apply_profile_diff, upsert_kb_chunks

router = APIRouter(prefix="/api/kb", dependencies=[Depends(require_admin_key)])
logger = logging.getLogger(__name__)


def _read_langfuse_trace_log(*args, **kwargs):
    return trace_adapter.read_langfuse_trace_log(*args, **kwargs)


def _read_llm_trace_log(*args, **kwargs):
    kwargs.setdefault("trace_path", getattr(settings, "llm_trace_log_path", ""))
    return trace_adapter.read_llm_trace_log(*args, **kwargs)


class TestQueryRequest(BaseModel):
    query: str


def _build_employer_detail(emp: dict) -> EmployerDetail:
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


def _profiles_dir() -> Path:
    return Path(
        os.environ.get(
            "CAREER_PROFILES_DIR",
            str(default_profiles_dir()),
        )
    )


def _employers_dir() -> Path:
    return Path(
        os.environ.get(
            "EMPLOYERS_DIR",
            str(default_employers_dir()),
        )
    )


def _draft_ready_for_publish(detail: DraftTrackDetail) -> bool:
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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/career-profiles")
def career_profiles(
    profile_store: CareerProfileStore = Depends(get_career_profile_store),
):
    """List all loaded career profiles with metadata (admin use only).

    Returns structured metadata from the 'structured:' YAML block alongside
    basic completeness indicators. Does not return the full profile content.

    Auth note: protected by the router-level `require_admin_key` dependency.
    """
    return profile_store.list_profiles()


@router.get("/career-profiles/broken")
def broken_career_profiles(
    profile_store: CareerProfileStore = Depends(get_career_profile_store),
):
    """List career profiles that failed validation due to missing required fields.

    Returns the slug, filename, list of missing fields, and which fields exist.
    This endpoint makes broken profiles visible to admins instead of silently skipping them.
    """
    return profile_store.list_broken_profiles()


@router.post("/career-profiles/{slug}/auto-complete", response_model=dict)
async def auto_complete_profile(
    slug: str,
    profile_store: CareerProfileStore = Depends(get_career_profile_store),
):
    """Use the LLM to fill in missing required fields for a broken career profile.

    Reads the existing partial profile, passes its content to the LLM with instructions
    to fill the missing fields, writes the completed profile back to disk, and triggers
    a store reload so it becomes immediately available.

    Returns the completed profile dict.
    """
    broken = profile_store.get_broken_profile(slug)
    if broken is None:
        raise HTTPException(
            status_code=404, detail=f"Broken profile '{slug}' not found"
        )

    # Determine which fields are missing
    required = set(career_profiles_cfg["required_fields"])
    existing = set(broken.keys())
    missing = required - existing

    if not missing:
        return {"slug": slug, "completed_fields": [], "profile": broken}

    try:
        filled = await llm_service.auto_complete_profile_fields(
            broken_profile=broken,
            missing_fields=list(missing),
            slug=slug,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("auto_complete_profile: LLM call failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Could not auto-complete: {exc}")

    # Merge filled fields into the broken profile
    for field, value in filled.items():
        if field in missing:
            broken[field] = value

    # Write back to disk
    profiles_dir = Path(
        os.environ.get("CAREER_PROFILES_DIR", str(default_profiles_dir()))
    )
    yaml_path = profiles_dir / f"{slug}.yaml"
    try:
        tmp = yaml_path.with_suffix(".tmp")
        profiles_dir.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                broken, f, allow_unicode=True, default_flow_style=False, sort_keys=False
            )
        tmp.replace(yaml_path)
    except Exception as exc:
        logger.error("auto_complete_profile: failed to write %s: %s", yaml_path, exc)
        raise HTTPException(
            status_code=500, detail=f"Could not save completed profile: {exc}"
        )

    # Invalidate the store so the completed profile is immediately loaded
    profile_store.invalidate()

    return {"slug": slug, "completed_fields": list(filled.keys()), "profile": broken}


@router.get("/tracks", response_model=list[TrackRegistryEntry])
def list_tracks(
    draft_store: TrackDraftStore = Depends(get_track_draft_store),
):
    """List registered career tracks.

    Bootstraps the registry from existing career profile YAMLs on first access.
    """
    try:
        return draft_store.list_registry()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/tracks/{slug}", response_model=TrackReferenceDetail)
def get_track_reference(
    slug: str,
    draft_store: TrackDraftStore = Depends(get_track_draft_store),
):
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")

    registry = {item.slug: item for item in draft_store.list_registry()}
    entry = registry.get(slug)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Track '{slug}' not found.")

    path = _profiles_dir() / f"{slug}.yaml"
    if not path.exists():
        raise HTTPException(
            status_code=404, detail=f"Published track '{slug}' not found."
        )

    try:
        with open(path, encoding="utf-8") as f:
            payload = yaml.safe_load(f) or {}
    except Exception as exc:
        logger.error("get_track_reference: failed to read %r: %s", slug, exc)
        raise HTTPException(
            status_code=500, detail="Failed to read published track YAML."
        )

    return TrackReferenceDetail(
        slug=slug,
        label=entry.label,
        status=entry.status,
        last_published=entry.last_published,
        track_name=str(payload.get("career_type") or entry.label or slug).strip(),
        match_description=str(payload.get("match_description") or "").strip(),
        match_keywords=list(payload.get("match_keywords") or []),
        ep_sponsorship=str(payload.get("ep_sponsorship") or "").strip(),
        compass_score_typical=str(payload.get("compass_score_typical") or "").strip(),
        top_employers_smu=list(payload.get("top_employers_smu") or []),
        recruiting_timeline=str(payload.get("recruiting_timeline") or "").strip(),
        international_realistic=bool(payload.get("international_realistic", True)),
        entry_paths=list(payload.get("entry_paths") or []),
        salary_range_2024=str(payload.get("salary_range_2024") or "").strip(),
        typical_background=str(payload.get("typical_background") or "").strip(),
        counselor_contact=payload.get("counselor_contact"),
        notes=str(payload.get("notes") or "").strip(),
    )


@router.get("/tracks/{slug}/history", response_model=list[TrackVersionInfo])
def list_track_history(
    slug: str,
    draft_store: TrackDraftStore = Depends(get_track_draft_store),
):
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")
    return draft_store.list_history(slug)


@router.get("/draft-tracks", response_model=list[DraftTrackDetail])
def list_draft_tracks(
    draft_store: TrackDraftStore = Depends(get_track_draft_store),
):
    """List all counsellor draft tracks."""
    return draft_store.list_drafts()


@router.get("/draft-tracks/{slug}", response_model=DraftTrackDetail)
def get_draft_track(
    slug: str,
    draft_store: TrackDraftStore = Depends(get_track_draft_store),
):
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")
    draft = draft_store.get_draft(slug)
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Draft track '{slug}' not found.")
    return draft


@router.post("/draft-tracks", response_model=DraftTrackDetail, status_code=201)
def create_draft_track(
    detail: DraftTrackDetail,
    draft_store: TrackDraftStore = Depends(get_track_draft_store),
):
    if not safe_slug_is_valid(detail.slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")
    if not detail.track_name or not detail.track_name.strip():
        raise HTTPException(status_code=422, detail="track_name is required.")
    if draft_store.get_draft(detail.slug) is not None:
        raise HTTPException(
            status_code=409, detail=f"Draft track '{detail.slug}' already exists."
        )

    detail.status = "ready_for_publish" if _draft_ready_for_publish(detail) else "draft"
    try:
        return draft_store.save_draft(detail)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.put("/draft-tracks/{slug}", response_model=DraftTrackDetail)
def update_draft_track(
    slug: str,
    detail: DraftTrackDetail,
    draft_store: TrackDraftStore = Depends(get_track_draft_store),
):
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")
    existing = draft_store.get_draft(slug)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Draft track '{slug}' not found.")
    detail.slug = slug
    detail.status = "ready_for_publish" if _draft_ready_for_publish(detail) else "draft"
    try:
        return draft_store.save_draft(detail)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/draft-tracks/generate", response_model=DraftTrackDetail, status_code=201)
def generate_draft_track(
    slug: str = Form(...),
    track_name: str = Form(...),
    text: str = Form(None),
    source_type: str = Form("note"),
    file: UploadFile = File(None),
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
    profile_store: CareerProfileStore = Depends(get_career_profile_store),
    draft_store: TrackDraftStore = Depends(get_track_draft_store),
):
    """Generate and save a draft track from counsellor research input."""
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")
    if not track_name or not track_name.strip():
        raise HTTPException(status_code=422, detail="track_name is required.")
    if draft_store.get_draft(slug) is not None:
        raise HTTPException(
            status_code=409, detail=f"Draft track '{slug}' already exists."
        )

    counsellor_input, source_type, source_label = extract_generation_input(
        text, source_type, file
    )
    retrieved = retrieve_generation_chunks(counsellor_input, embedder, store)

    try:
        raw = llm_service.generate_track_draft(
            counsellor_input=counsellor_input,
            track_name=track_name.strip(),
            slug=slug,
            existing_tracks=profile_store.list_profiles(),
            retrieved_chunks=retrieved,
            source_label=source_label,
            source_type=source_type,
        )
    except ValueError as exc:
        logger.warning("generate_draft_track: Claude returned malformed JSON: %s", exc)
        raise HTTPException(
            status_code=422,
            detail="We could not generate a draft from this research yet.",
        )
    except Exception as exc:
        logger.error("generate_draft_track: LLM call failed: %s", exc)
        raise HTTPException(
            status_code=503, detail="Draft generation service unavailable"
        )

    try:
        detail = DraftTrackDetail(**raw)
    except Exception as exc:
        logger.warning(
            "generate_draft_track: validation failed: %s | raw=%r", exc, str(raw)[:300]
        )
        raise HTTPException(
            status_code=422,
            detail="We could not generate a draft from this research yet.",
        )

    detail.slug = slug
    detail.track_name = track_name.strip()
    detail.status = "ready_for_publish" if _draft_ready_for_publish(detail) else "draft"
    if not detail.source_refs:
        detail.source_refs = [SourceRef(type=source_type, label=source_label)]
    try:
        return draft_store.save_draft(detail)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/draft-tracks/{slug}/generate-update", response_model=DraftTrackDetail)
def refresh_draft_track_from_research(
    slug: str,
    text: str = Form(None),
    source_type: str = Form("note"),
    file: UploadFile = File(None),
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
    profile_store: CareerProfileStore = Depends(get_career_profile_store),
    draft_store: TrackDraftStore = Depends(get_track_draft_store),
):
    """Refresh an existing draft track using additional counsellor research."""
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")
    existing = draft_store.get_draft(slug)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Draft track '{slug}' not found.")

    counsellor_input, source_type, source_label = extract_generation_input(
        text, source_type, file
    )
    retrieved = retrieve_generation_chunks(counsellor_input, embedder, store)

    try:
        raw = llm_service.generate_track_draft(
            counsellor_input=counsellor_input,
            track_name=existing.track_name.strip(),
            slug=slug,
            existing_tracks=profile_store.list_profiles(),
            retrieved_chunks=retrieved,
            source_label=source_label,
            source_type=source_type,
            existing_draft=existing.model_dump(),
        )
    except ValueError as exc:
        logger.warning(
            "refresh_draft_track_from_research: Claude returned malformed JSON: %s", exc
        )
        raise HTTPException(
            status_code=422,
            detail="We could not update this draft from the new research yet.",
        )
    except Exception as exc:
        logger.error("refresh_draft_track_from_research: LLM call failed: %s", exc)
        raise HTTPException(
            status_code=503, detail="Draft generation service unavailable"
        )

    try:
        detail = DraftTrackDetail(**raw)
    except Exception as exc:
        logger.warning(
            "refresh_draft_track_from_research: validation failed: %s | raw=%r",
            exc,
            str(raw)[:300],
        )
        raise HTTPException(
            status_code=422,
            detail="We could not update this draft from the new research yet.",
        )

    detail.slug = slug
    detail.track_name = existing.track_name.strip()
    detail.status = "ready_for_publish" if _draft_ready_for_publish(detail) else "draft"
    detail.source_refs = merge_source_refs(
        detail.source_refs, source_type, source_label
    )
    try:
        return draft_store.save_draft(detail)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/draft-tracks/{slug}/publish", response_model=TrackPublishResponse)
def publish_draft_track(
    slug: str,
    draft_store: TrackDraftStore = Depends(get_track_draft_store),
    profile_store: CareerProfileStore = Depends(get_career_profile_store),
):
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")
    draft = draft_store.get_draft(slug)
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Draft track '{slug}' not found.")
    if not _draft_ready_for_publish(draft):
        raise HTTPException(
            status_code=422, detail="Draft is incomplete and cannot be published yet."
        )
    try:
        version = draft_store.publish_draft(slug, actor="admin")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("publish_draft_track: failed for %r: %s", slug, exc)
        raise HTTPException(status_code=500, detail="Failed to publish draft track.")
    profile_store.invalidate()
    return TrackPublishResponse(
        status="ok", slug=slug, version=version, registry_updated=True
    )


@router.post("/tracks/{slug}/rollback", response_model=TrackPublishResponse)
def rollback_track(
    slug: str,
    draft_store: TrackDraftStore = Depends(get_track_draft_store),
    profile_store: CareerProfileStore = Depends(get_career_profile_store),
):
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")
    try:
        version = draft_store.rollback_track(slug, actor="admin")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("rollback_track: failed for %r: %s", slug, exc)
        raise HTTPException(status_code=500, detail="Failed to roll back track.")
    profile_store.invalidate()
    return TrackPublishResponse(
        status="ok", slug=slug, version=version, registry_updated=True
    )


@router.get("/publish-journal")
def get_publish_journal():
    """Read the track publish journal (JSONL), newest first.

    Returns raw entries so the frontend can build provenance views.
    """
    return read_publish_journal()


@router.get("/employers", response_model=list[EmployerDetail])
def list_employers(
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
    """List all active employer entities (admin use only).

    Excludes disabled employers (*.yaml.disabled).
    Auth note: protected by the router-level `require_admin_key` dependency.
    """
    return [_build_employer_detail(emp) for emp in employer_store.list_employers()]


@router.get("/employers/{slug}", response_model=EmployerDetail)
def get_employer(
    slug: str,
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
    """Get a single employer entity by slug.

    Auth note: protected by the router-level `require_admin_key` dependency.
    """
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")
    emp = employer_store.get_employer(slug)
    if emp is None:
        raise HTTPException(status_code=404, detail=f"Employer '{slug}' not found.")
    return _build_employer_detail({**emp, "slug": emp.get("slug", slug)})


@router.get("/employers/{slug}/history", response_model=list[EmployerHistoryVersion])
def get_employer_history(
    slug: str,
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
    """Return employer YAML history snapshots, newest first."""
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")
    return employer_store.list_history(slug)


@router.post("/employers", response_model=EmployerDetail, status_code=201)
def create_employer(
    detail: EmployerDetail,
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
    """Create a new employer entity.

    Returns 409 if a YAML (or .yaml.disabled) already exists for this slug.
    Auth note: protected by the router-level `require_admin_key` dependency.
    """
    slug = detail.slug
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")
    if not detail.employer_name or not detail.employer_name.strip():
        raise HTTPException(status_code=422, detail="employer_name is required.")

    edir = _employers_dir()
    edir.mkdir(parents=True, exist_ok=True)
    yaml_path = edir / f"{slug}.yaml"
    disabled_path = edir / f"{slug}.yaml.disabled"

    if yaml_path.exists() or disabled_path.exists():
        raise HTTPException(
            status_code=409, detail=f"Employer '{slug}' already exists."
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    payload = (
        detail.model_dump(exclude_unset=True)
        if hasattr(detail, "model_dump")
        else detail.dict(exclude_unset=True)
    )
    data = {
        "employer_name": detail.employer_name.strip(),
        "slug": slug,
        "tracks": detail.tracks or [],
        "ep_requirement": detail.ep_requirement,
        "intake_seasons": detail.intake_seasons or [],
        "singapore_headcount_estimate": detail.singapore_headcount_estimate,
        "application_process": detail.application_process,
        "counsellor_contact": detail.counsellor_contact,
        "notes": detail.notes,
        "last_updated": now,
    }
    if "structured" in payload:
        data["structured"] = dict(detail.structured or {})
    if "source_documents" in payload:
        data["source_documents"] = list(detail.source_documents or [])
    # Remove None values to keep YAML clean
    data = {k: v for k, v in data.items() if v is not None}

    tmp = yaml_path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                data, f, allow_unicode=True, default_flow_style=False, sort_keys=False
            )
        tmp.replace(yaml_path)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        logger.error("create_employer: failed to write %r: %s", slug, exc)
        raise HTTPException(status_code=500, detail="Failed to write employer YAML.")

    employer_store.invalidate()
    logger.info("create_employer: created %r", slug)

    data["slug"] = slug
    return EmployerDetail(
        **{**data, "completeness": compute_completeness(data), "structured": {}}
    )


@router.put("/employers/{slug}", response_model=EmployerDetail)
def update_employer(
    slug: str,
    detail: EmployerDetail,
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
    """Update an existing employer entity.

    Server always sets last_updated to today regardless of request body.
    The 'completeness' field in the request body is ignored (server-computed).
    Auth note: protected by the router-level `require_admin_key` dependency.
    """
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")

    edir = _employers_dir()
    yaml_path = edir / f"{slug}.yaml"
    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail=f"Employer '{slug}' not found.")

    try:
        with open(yaml_path, encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}
    except Exception as exc:
        logger.error("update_employer: failed to read %r: %s", slug, exc)
        raise HTTPException(status_code=500, detail="Failed to read employer YAML.")

    employer_store.snapshot_history(slug, existing)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    payload = (
        detail.model_dump(exclude_unset=True)
        if hasattr(detail, "model_dump")
        else detail.dict(exclude_unset=True)
    )
    # Merge incoming fields; server always sets last_updated
    existing.update(
        {
            "employer_name": detail.employer_name.strip()
            if detail.employer_name
            else existing.get("employer_name", ""),
            "tracks": detail.tracks
            if detail.tracks is not None
            else existing.get("tracks", []),
            "ep_requirement": detail.ep_requirement,
            "intake_seasons": detail.intake_seasons
            if detail.intake_seasons is not None
            else existing.get("intake_seasons", []),
            "singapore_headcount_estimate": detail.singapore_headcount_estimate,
            "application_process": detail.application_process,
            "counsellor_contact": detail.counsellor_contact,
            "notes": detail.notes,
            "last_updated": now,
        }
    )
    if "structured" in payload:
        existing["structured"] = dict(detail.structured or {})
    if "source_documents" in payload:
        existing["source_documents"] = list(detail.source_documents or [])
    # Preserve slug field
    existing["slug"] = slug

    tmp = yaml_path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                existing,
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )
        tmp.replace(yaml_path)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        logger.error("update_employer: failed to write %r: %s", slug, exc)
        raise HTTPException(status_code=500, detail="Failed to write employer YAML.")

    employer_store.invalidate()
    logger.info("update_employer: updated %r", slug)

    return EmployerDetail(
        **{**existing, "completeness": compute_completeness(existing)}
    )


@router.delete("/employers/{slug}", status_code=204)
def delete_employer(
    slug: str,
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
    """Disable an employer entity by renaming its YAML to *.yaml.disabled.

    Does NOT hard-delete — counsellor can restore via PATCH /api/kb/employers/{slug}/restore.
    Auth note: protected by the router-level `require_admin_key` dependency.
    """
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")

    edir = _employers_dir()
    yaml_path = edir / f"{slug}.yaml"
    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail=f"Employer '{slug}' not found.")

    disabled_path = edir / f"{slug}.yaml.disabled"
    try:
        with open(yaml_path, encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}
        employer_store.snapshot_history(slug, existing)
        yaml_path.rename(disabled_path)
    except Exception as exc:
        logger.error("delete_employer: failed to rename %r: %s", slug, exc)
        raise HTTPException(status_code=500, detail="Failed to disable employer.")

    employer_store.invalidate()
    logger.info("delete_employer: disabled %r (renamed to .yaml.disabled)", slug)


@router.patch("/employers/{slug}/restore")
def restore_employer(
    slug: str,
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
    """Restore a previously disabled employer entity by renaming *.yaml.disabled back to *.yaml.

    Auth note: protected by the router-level `require_admin_key` dependency.
    """
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")

    edir = _employers_dir()
    disabled_path = edir / f"{slug}.yaml.disabled"
    if not disabled_path.exists():
        raise HTTPException(
            status_code=404, detail=f"Disabled employer '{slug}' not found."
        )

    yaml_path = edir / f"{slug}.yaml"
    if yaml_path.exists():
        raise HTTPException(
            status_code=409, detail=f"Employer '{slug}' already exists as active."
        )

    try:
        disabled_path.rename(yaml_path)
    except Exception as exc:
        logger.error("restore_employer: failed to rename %r: %s", slug, exc)
        raise HTTPException(status_code=500, detail="Failed to restore employer.")

    employer_store.invalidate()
    logger.info("restore_employer: restored %r (renamed from .yaml.disabled)", slug)

    with open(yaml_path, encoding="utf-8") as f:
        restored = yaml.safe_load(f) or {}
    restored.setdefault("slug", slug)
    return _build_employer_detail(
        {**restored, "completeness": compute_completeness(restored)}
    )


@router.post("/employers/{slug}/extract-facts")
async def extract_facts_from_employer_notes(
    slug: str,
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
    """Extract structured facts from employer notes and uploaded source documents.

    Concatenates the employer's notes field with any raw text stored via
    /api/ingest?employer_slug=... and extracts timeline, alumni, interview,
    compensation, and skill requirement facts. Returns facts as JSON for counsellor review.

    Auth note: protected by the router-level `require_admin_key` dependency.
    """
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")

    emp = employer_store.get_employer(slug)
    if not emp:
        raise HTTPException(status_code=404, detail=f"Employer '{slug}' not found.")

    notes = emp.get("notes") or ""
    source_docs = emp.get("source_documents") or []
    doc_texts = "\n\n".join(d["raw_text"] for d in source_docs if d.get("raw_text"))
    combined = "\n\n".join(filter(None, [notes.strip(), doc_texts.strip()]))

    if not combined:
        raise HTTPException(
            status_code=400,
            detail="Employer has no notes or source documents to extract from.",
        )

    source_label = "employer_notes+documents" if doc_texts else "employer_notes"
    try:
        facts = await extract_facts_from_prose(combined, emp.get("employer_name", slug))
        return {
            "facts": facts,
            "total": len(facts),
            "source": source_label,
        }
    except Exception as exc:
        logger.error("extract_facts_from_employer_notes: failed for %r: %s", slug, exc)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(exc)}")


def _fact_filters_payload(
    type: str | None,
    employer: str | None,
    school: str | None,
    graduation_year: int | None,
    confidence__gte: int | None,
    source: str | None,
    include_deleted: bool,
    lifecycle: str | None,
    trace_id: str | None,
    source_type: str | None,
    source_label: str | None,
    has_audit_url: bool | None,
) -> dict[str, Any]:
    """Build the filters_applied echo dict for a fact query response, omitting None values."""
    payload: dict[str, Any] = {"include_deleted": include_deleted}
    for key, value in {
        "type": type,
        "employer": employer,
        "school": school,
        "graduation_year": graduation_year,
        "confidence__gte": confidence__gte,
        "source": source,
        "lifecycle": lifecycle,
        "trace_id": trace_id,
        "source_type": source_type,
        "source_label": source_label,
        "has_audit_url": has_audit_url,
    }.items():
        if value is not None:
            payload[key] = value
    return payload


@router.get("/facts", response_model=FactQueryResponse)
def list_facts_endpoint(
    type: str | None = Query(None, alias="type"),
    employer: str | None = Query(None),
    school: str | None = Query(None),
    graduation_year: int | None = Query(None),
    confidence__gte: int | None = Query(None, ge=0, le=100),
    source: str | None = Query(None),
    include_deleted: bool = Query(False),
    lifecycle: str | None = Query(None),
    trace_id: str | None = Query(None),
    source_type: str | None = Query(None),
    source_label: str | None = Query(None),
    has_audit_url: bool | None = Query(None),
):
    """List structured facts from employers and career profiles."""
    facts = list_facts(
        type=type,
        employer=employer,
        school=school,
        graduation_year=graduation_year,
        confidence__gte=confidence__gte,
        source=source,
        include_deleted=include_deleted,
        lifecycle=lifecycle,
        trace_id=trace_id,
        source_type=source_type,
        source_label=source_label,
        has_audit_url=has_audit_url,
    )
    return FactQueryResponse(
        facts=facts,
        total=len(facts),
        filters_applied=_fact_filters_payload(
            type,
            employer,
            school,
            graduation_year,
            confidence__gte,
            source,
            include_deleted,
            lifecycle,
            trace_id,
            source_type,
            source_label,
            has_audit_url,
        ),
    )


@router.get("/facts/grouped", response_model=FactGroupResponse)
def list_grouped_facts_endpoint(
    by: Literal["employer", "type"] = Query("employer"),
    type: str | None = Query(None, alias="type"),
    employer: str | None = Query(None),
    school: str | None = Query(None),
    graduation_year: int | None = Query(None),
    confidence__gte: int | None = Query(None, ge=0, le=100),
    source: str | None = Query(None),
    include_deleted: bool = Query(False),
    lifecycle: str | None = Query(None),
    trace_id: str | None = Query(None),
    source_type: str | None = Query(None),
    source_label: str | None = Query(None),
    has_audit_url: bool | None = Query(None),
):
    """Group structured facts by employer slug or fact type."""
    facts = list_facts(
        type=type,
        employer=employer,
        school=school,
        graduation_year=graduation_year,
        confidence__gte=confidence__gte,
        source=source,
        include_deleted=include_deleted,
        lifecycle=lifecycle,
        trace_id=trace_id,
        source_type=source_type,
        source_label=source_label,
        has_audit_url=has_audit_url,
    )
    grouped = group_facts(facts, by=by)
    return FactGroupResponse(
        by=by,
        groups=grouped,
        total=len(facts),
        filters_applied=_fact_filters_payload(
            type,
            employer,
            school,
            graduation_year,
            confidence__gte,
            source,
            include_deleted,
            lifecycle,
            trace_id,
            source_type,
            source_label,
            has_audit_url,
        ),
    )


@router.post("/analyse", response_model=KBAnalysisResult)
def analyse(
    request: Request,
    text: str = Form(None),
    source_type: str = Form("note"),
    file: UploadFile = File(None),
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
    profile_store: CareerProfileStore = Depends(get_career_profile_store),
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
    """Analyse counsellor input and return a structured KB diff.

    Accepts either a text note (form field 'text') or a file upload.
    Does NOT write to the KB — returns KBAnalysisResult for counsellor review.

    Auth note: protected by the router-level `require_admin_key` dependency.
    """
    if source_type == "file" and file is not None:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum upload size ({settings.max_upload_bytes // (1024 * 1024)}MB).",
            )

    return analyse_counsellor_input(
        text=text,
        source_type=source_type,
        file=file,
        embedder=embedder,
        store=store,
        profile_store=profile_store,
        employer_store=employer_store,
    )


@router.post("/commit-analysis", response_model=KBCommitResponse)
def commit_analysis(
    req: KBCommitRequest,
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
    profile_store: CareerProfileStore = Depends(get_career_profile_store),
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
    """Commit a counsellor-approved KB diff.

    Upserts new chunks to Qdrant, writes updated YAML fields to profile files,
    then invalidates caches so changes are reflected immediately.

    Auth note: protected by the router-level `require_admin_key` dependency.
    """
    # Basic input validation — guard against malformed or outsized payloads
    _MAX_CHUNKS = 10
    _MAX_CHUNK_TEXT = 4000  # chars
    if len(req.new_chunks) > _MAX_CHUNKS:
        raise HTTPException(
            status_code=422, detail=f"Too many chunks (max {_MAX_CHUNKS})."
        )
    for chunk in req.new_chunks:
        if chunk.source_type not in ("note", "file"):
            raise HTTPException(status_code=422, detail="Invalid source_type.")
        if len(chunk.text) > _MAX_CHUNK_TEXT:
            raise HTTPException(
                status_code=422, detail=f"Chunk text exceeds {_MAX_CHUNK_TEXT} chars."
            )

    chunk_result = upsert_kb_chunks(
        req.new_chunks, vector_store=store, embedder=embedder, source="commit-analysis"
    )

    # --- 2. Write profile YAML updates ---
    profiles_updated: list[str] = []
    for slug, field_changes in req.profile_updates.items():
        result = apply_profile_diff(
            slug,
            field_changes,
            create_missing=False,
            skip_invalid=True,
            source="commit-analysis",
        )
        if result.changed_fields:
            profiles_updated.append(slug)
            logger.info(
                "commit-analysis: updated profile %r fields: %s",
                slug,
                result.changed_fields,
            )
        elif not result.skipped_missing:
            logger.info("commit-analysis: profile %r had no valid field updates", slug)

    # --- 3. Write employer YAML updates ---
    employers_updated: list[str] = []
    for slug, field_changes in req.employer_updates.items():
        result = apply_employer_diff(
            slug,
            field_changes,
            create_missing=False,
            snapshot=True,
            skip_invalid=True,
            source="commit-analysis",
        )
        if result.changed_fields:
            employers_updated.append(slug)
            logger.info(
                "commit-analysis: updated employer %r fields: %s",
                slug,
                result.changed_fields,
            )
        elif not result.skipped_missing:
            logger.info("commit-analysis: employer %r had no valid field updates", slug)

    # --- 4. Invalidate caches ---
    health_cache.invalidate_overlap_cache()
    invalidate_docs_cache()
    profile_store.invalidate()
    employer_store.invalidate()

    return KBCommitResponse(
        status="ok",
        chunks_added=chunk_result.chunks_added,
        profiles_updated=profiles_updated,
        employers_updated=employers_updated,
    )


@router.post("/test-query", response_model=list[TestQueryResult])
def test_query(
    req: TestQueryRequest,
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
):
    """Test a query against the KB. Returns top-5 chunks with similarity scores.

    Admin test queries are NOT logged to the query log — this is intentional.
    Logging admin probes would pollute the low-confidence query analysis with
    queries that don't reflect real student usage.
    """
    try:
        query_vec = embedder.encode(req.query)
        chunks = store.search(query_vec, top_k=5)
        return [
            TestQueryResult(
                source_filename=c["payload"]["source_filename"],
                excerpt=c["payload"]["text"][:300],
                score=round(c["score"], 4),
            )
            for c in chunks
        ]
    except Exception as e:
        logger.error("Qdrant unavailable during test-query: %s", e)
        raise HTTPException(status_code=503, detail="KB unavailable")


@router.get("/health", response_model=KBHealthResponse)
def kb_health(
    store: VectorStore = Depends(get_vector_store),
):
    """KB health metrics for the admin dashboard.

    Returns doc coverage, query log metrics, and overlap pair analysis.
    If Qdrant is unavailable, returns HTTP 503.
    """
    try:
        return assemble_kb_health(store)
    except Exception as e:
        if "Qdrant" in str(e) or "VectorStore" in str(type(e).__name__):
            logger.error("KB health failed: %s", e)
            raise HTTPException(status_code=503, detail="KB unavailable")
        raise


@router.get("/llm-traces", response_model=list[LLMTraceEntry])
def llm_traces(
    limit: int = 50,
    session_id: str | None = None,
    operation: str | None = None,
    status: str | None = None,
):
    """Return recent structured LLM trace entries for admin debugging."""
    if limit < 1:
        raise HTTPException(status_code=422, detail="limit must be at least 1")
    if limit > 200:
        limit = 200
    return list_recent_llm_traces(
        limit=limit,
        session_id=session_id,
        operation=operation,
        status=status,
        trace_path=getattr(settings, "llm_trace_log_path", ""),
    )


@router.get("/workflow-summaries", response_model=list[LLMWorkflowSummary])
def workflow_summaries(
    limit: int = 25,
    session_id: str | None = None,
    status: str | None = None,
):
    """Return lean session-analysis workflow summaries for polling surfaces."""
    if limit < 1:
        raise HTTPException(status_code=422, detail="limit must be at least 1")
    if limit > 200:
        limit = 200
    return list_workflow_summaries(limit=limit, session_id=session_id, status=status)


@router.get("/workflow-detail", response_model=LLMWorkflowDetail)
def workflow_detail(
    session_id: str | None = None,
    workflow_id: str | None = None,
):
    """Return a normalized session-analysis workflow detail object."""
    if not session_id and not workflow_id:
        raise HTTPException(
            status_code=422, detail="session_id or workflow_id is required"
        )
    detail = get_workflow_detail(session_id=session_id, workflow_id=workflow_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Workflow detail not found")
    return detail
