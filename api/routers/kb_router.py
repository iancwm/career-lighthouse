# api/routers/kb_router.py
"""KB observability and diff-first ingestion endpoints.

POST /api/kb/test-query       — test a query, returns top-5 chunks with scores
GET  /api/kb/health           — KB health metrics for the admin dashboard
POST /api/kb/analyse          — analyse counsellor input, return diff (no writes)
POST /api/kb/commit-analysis  — commit a counsellor-approved diff to KB and YAMLs

Auth note: These endpoints are protected by the router-level `require_admin_key`
dependency and by Next.js middleware (web/middleware.ts). The remaining auth
follow-up is migrating the admin key transport off the query param.
"""
import json
import logging
import os
import uuid
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
from services.career_profiles import CareerProfileStore, get_career_profile_store
from services.employer_store import (
    EmployerEntityStore,
    _default_employers_dir,
    _as_list,
    get_employer_store,
)
from services.fact_store import group_facts, list_facts
from services.shared_yaml import safe_slug_is_valid
from services import trace_adapter
from services.trace_adapter import (
    _observation_to_trace_entries,
    list_recent as list_recent_llm_traces,
)
from services.embedder import Embedder
from services.ingestion import chunk_text, parse_file
from services.source_ledger import get_source_ledger_store
from services.vector_store import VectorStore
from services import llm as llm_service
from services.llm import extract_facts_from_prose
from config import settings
from cfg import kb_cfg
from services.career_profiles import _default_profiles_dir, _derive_structured_fields
from services.track_drafts import TrackDraftStore, get_track_draft_store, read_publish_journal
from services.kb_writer import apply_employer_diff, apply_profile_diff, upsert_kb_chunks

router = APIRouter(prefix="/api/kb", dependencies=[Depends(require_admin_key)])
logger = logging.getLogger(__name__)

_thresholds = kb_cfg["thresholds"]
_COVERAGE_THIN_THRESHOLD = _thresholds["coverage_thin"]
_LOW_CONFIDENCE_THRESHOLD = _thresholds["low_confidence"]
_OVERLAP_SCORE_THRESHOLD = _thresholds["overlap_score"]
_OVERLAP_PCT_THRESHOLD = _thresholds["overlap_pct"]
_LOG_WINDOW_DAYS = kb_cfg["log_window_days"]
_MAX_LOW_CONF_QUERIES = kb_cfg["max_low_conf_queries"]


def _read_langfuse_trace_log(*args, **kwargs):
    return trace_adapter.read_langfuse_trace_log(*args, **kwargs)


def _read_llm_trace_log(*args, **kwargs):
    kwargs.setdefault("trace_path", getattr(settings, "llm_trace_log_path", ""))
    return trace_adapter.read_llm_trace_log(*args, **kwargs)


class TestQueryRequest(BaseModel):
    query: str


# ---------------------------------------------------------------------------
# Sprint 3 helpers
# ---------------------------------------------------------------------------

def _first_sentence(text: str, max_chars: int = 120) -> str:
    """Extract first sentence up to max_chars — mirrors notebook spec."""
    if not text:
        return ""
    text = str(text).strip()
    dot = text.find(".")
    if dot != -1 and dot < max_chars:
        return text[: dot + 1]
    return text[:max_chars]


def _build_profile_summary(store: CareerProfileStore) -> str:
    """Build the CURRENT CAREER PROFILE FIELDS block for the diff prompt."""
    profiles = store.list_profiles()
    lines = []
    for meta in profiles:
        slug = meta["slug"]
        profile = store.get_profile(slug)
        if not profile:
            continue
        ep = _first_sentence(str(profile.get("ep_sponsorship", "")))
        compass = _first_sentence(str(profile.get("compass_score_typical", "")))
        timeline = _first_sentence(str(profile.get("recruiting_timeline", "")))
        notes = _first_sentence(str(profile.get("notes", "")))
        lines.append(
            f"{slug}: ep_sponsorship={ep} | compass={compass} | "
            f"recruiting_timeline={timeline} | notes={notes}"
        )
    return "\n".join(lines)


def _build_employer_detail(emp: dict) -> EmployerDetail:
    """Normalize a raw employer YAML dict into the API response model."""
    return EmployerDetail(
        slug=emp.get("slug", ""),
        employer_name=emp.get("employer_name", ""),
        tracks=_as_list(emp.get("tracks")),
        ep_requirement=emp.get("ep_requirement"),
        intake_seasons=_as_list(emp.get("intake_seasons")),
        singapore_headcount_estimate=emp.get("singapore_headcount_estimate"),
        application_process=emp.get("application_process"),
        counsellor_contact=emp.get("counsellor_contact"),
        notes=emp.get("notes"),
        structured=dict(emp.get("structured") or {}),
        last_updated=emp.get("last_updated"),
        completeness=emp.get("completeness", "amber"),
    )


def _profiles_dir() -> Path:
    return Path(os.environ.get(
        "CAREER_PROFILES_DIR",
        str(_default_profiles_dir()),
    ))


def _employers_dir() -> Path:
    return Path(os.environ.get(
        "EMPLOYERS_DIR",
        str(_default_employers_dir()),
    ))


def _build_employer_summary(store: EmployerEntityStore) -> str:
    """Build the CURRENT EMPLOYER FACTS block for the analyse diff prompt."""
    employers = store.list_employers()
    lines = []
    for emp in employers:
        slug = emp.get("slug", "")
        name = emp.get("employer_name", slug)
        ep = _first_sentence(str(emp.get("ep_requirement", "")))
        seasons = ", ".join(emp.get("intake_seasons") or [])
        lines.append(f"{slug} ({name}): ep_requirement={ep} | intake_seasons={seasons}")
    return "\n".join(lines)


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


def _extract_generation_input(
    text: str | None,
    source_type: str,
    file: UploadFile | None,
) -> tuple[str, str, str]:
    """Return counsellor input text plus normalized source metadata."""
    if source_type == "file" and file is not None:
        raw_bytes = file.file.read()
        fname = file.filename or "upload.txt"
        try:
            counsellor_input = parse_file(raw_bytes, fname)
        except Exception as exc:
            logger.warning("draft generation: failed to parse uploaded file %r: %s", fname, exc)
            raise HTTPException(status_code=422, detail="Could not extract text from the uploaded file.")
        return counsellor_input, "file", fname

    if not text or not text.strip():
        raise HTTPException(status_code=422, detail="Provide either 'text' or a file upload.")
    return text.strip(), "note", "counsellor_note"


def _retrieve_generation_chunks(
    counsellor_input: str,
    embedder: Embedder,
    store: VectorStore,
) -> list[dict]:
    try:
        chunks_for_query = chunk_text(counsellor_input, max_tokens=256)
        query_text = chunks_for_query[0] if chunks_for_query else counsellor_input
        query_vec = embedder.encode(query_text)
        return store.search(query_vec, top_k=8)
    except Exception as exc:
        logger.error("draft generation: KB search failed: %s", exc)
        raise HTTPException(status_code=503, detail="KB unavailable")


def _merge_source_refs(existing_refs: list[dict] | list, source_type: str, source_label: str) -> list[SourceRef]:
    seen: set[tuple[str, str]] = set()
    merged: list[SourceRef] = []
    for raw in list(existing_refs or []) + [{"type": source_type, "label": source_label}]:
        if isinstance(raw, dict):
            ref_type = str(raw.get("type", "")).strip()
            label = str(raw.get("label", "")).strip()
        else:
            ref_type = str(getattr(raw, "type", "")).strip()
            label = str(getattr(raw, "label", "")).strip()
        if not ref_type or not label:
            continue
        key = (ref_type.lower(), label.lower())
        if key in seen:
            continue
        seen.add(key)
        merged.append(SourceRef(type=ref_type, label=label))
    return merged


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_query_log(since: datetime) -> list[dict]:
    """Read JSONL query log, returning entries within the time window.

    Malformed lines are skipped with a warning (never raises).
    Returns empty list if log file is absent or empty.
    """
    entries = []
    try:
        if not os.path.exists(settings.query_log_path):
            return []
        with open(settings.query_log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ts_str = entry["ts"]
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= since:
                    entries.append(entry)
            except (json.JSONDecodeError, KeyError, ValueError):
                logger.warning(
                    "Skipping malformed query log line: %r", line[:120]
                )
    except Exception:
        logger.warning("Failed to read query log", exc_info=True)
    return entries


def _compute_overlap_pairs(store: VectorStore) -> list[dict]:
    """Compute document pairs with high content overlap.

    For each document, samples its chunk vectors (via Qdrant scroll) and searches
    the KB for near-duplicates. Pairs where > 30% of sampled chunks score ≥ 0.85
    against a chunk in another document are flagged.

    Acceptable at pre-launch scale (< 30 docs ≈ < 5 seconds).
    TODO: cache this result; invalidate on each ingest when KB exceeds 30 docs.
          The invalidation hook is already wired in ingest_router.py via health_cache.
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    docs = store.list_docs()
    if len(docs) < 2:
        return []

    pairs: list[dict] = []
    checked: set[frozenset] = set()

    for doc in docs:
        filename = doc["filename"]

        # Retrieve chunk vectors for this document via a filtered scroll
        chunk_points, _ = store._client.scroll(
            collection_name=store._collection,
            scroll_filter=Filter(
                must=[FieldCondition(key="source_filename", match=MatchValue(value=filename))]
            ),
            limit=200,
            with_vectors=True,
            with_payload=True,
        )
        if not chunk_points:
            continue

        # Note: scroll is capped at limit=200 so len(chunk_points) <= 200 always.
        # Sampling for very large docs would require Qdrant scroll pagination; deferred
        # until KB exceeds pre-launch scale. Use all retrieved chunks for now.
        sample = chunk_points

        overlap_against: dict[str, int] = {}
        for pt in sample:
            vec = np.array(pt.vector, dtype=np.float32)
            results = store.search(vec, top_k=2)
            for r in results:
                matched_fn = r["payload"].get("source_filename", "")
                if matched_fn and matched_fn != filename and r["score"] >= _OVERLAP_SCORE_THRESHOLD:
                    overlap_against[matched_fn] = overlap_against.get(matched_fn, 0) + 1

        for other_fn, count in overlap_against.items():
            pct = count / len(sample)
            if pct >= _OVERLAP_PCT_THRESHOLD:
                pair_key = frozenset([filename, other_fn])
                if pair_key not in checked:
                    checked.add(pair_key)
                    pairs.append({
                        "doc_a": filename,
                        "doc_b": other_fn,
                        "overlap_pct": round(pct, 2),
                        "recommendation": "merge or remove one",
                    })

    return pairs


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
def auto_complete_profile(
    slug: str,
    profile_store: CareerProfileStore = Depends(get_career_profile_store),
):
    """Use the LLM to fill in missing required fields for a broken career profile.

    Reads the existing partial profile, passes its content to the LLM with instructions
    to fill the missing fields, writes the completed profile back to disk, and triggers
    a store reload so it becomes immediately available.

    Returns the completed profile dict.
    """
    from config import settings
    from cfg import career_profiles_cfg

    broken = profile_store.get_broken_profile(slug)
    if broken is None:
        raise HTTPException(status_code=404, detail=f"Broken profile '{slug}' not found")

    # Determine which fields are missing
    from cfg import career_profiles_cfg
    required = set(career_profiles_cfg["required_fields"])
    existing = set(broken.keys())
    missing = required - existing

    # Build a prompt that asks the LLM to fill the gaps
    profile_budget = getattr(settings, "llm_auto_complete_max_profile_chars", None) or 6000
    existing_content = "\n".join(f"{k}: {v}" for k, v in broken.items() if v)
    existing_content = existing_content[:profile_budget]
    missing_list = ", ".join(sorted(missing))

    system = (
        f"You are a career data curator for {llm_service.SCHOOL_NAME}.\n"
        "Given a partial career profile YAML and a list of missing required fields,\n"
        "fill in the missing fields based on the existing profile content.\n"
        "Return ONLY a JSON object with the missing field names as keys.\n"
        "Be specific and realistic — use real-world data where possible.\n"
        "Do not modify or repeat fields that already exist.\n"
    )

    user = (
        f"Existing profile fields:\n{existing_content}\n\n"
        f"Missing fields to fill: {missing_list}\n\n"
        f"Return a JSON object with values for each missing field. "
        f"For list fields (top_employers_smu, entry_paths), return a JSON array. "
        f"For boolean fields (international_realistic), return true or false. "
        f"For string fields, return a concise 1-3 sentence value."
    )

    try:
        filled = llm_service.call_structured_json(
            operation="auto_complete_profile",
            model=llm_service.get_model_name(),
            max_tokens=1024,
            system=system,
            user=user,
            schema_name="auto_complete_profile",
            schema_hint=(
                f"JSON object with only the missing fields: {missing_list}. "
                "List fields may be arrays, boolean fields booleans, string fields short prose."
            ),
            trace_metadata={
                "feature": "auto_complete_profile",
                "slug": slug,
                "missing_count": len(missing),
                "input_chars_pre_trim": len(existing_content),
            },
        )
    except HTTPException:
        raise
    except ValueError as exc:
        logger.error("auto_complete_profile: LLM call failed: %s", exc)
        raise HTTPException(status_code=422, detail=f"Could not auto-complete: {exc}")
    except Exception as exc:
        logger.error("auto_complete_profile: LLM call failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Could not auto-complete: {exc}")

    # Merge filled fields into the broken profile
    for field, value in filled.items():
        if field in missing:
            broken[field] = value

    # Write back to disk
    from services.career_profiles import _default_profiles_dir
    profiles_dir = Path(os.environ.get("CAREER_PROFILES_DIR", str(_default_profiles_dir())))
    yaml_path = profiles_dir / f"{slug}.yaml"
    try:
        import yaml as _yaml
        tmp = yaml_path.with_suffix(".tmp")
        profiles_dir.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            _yaml.safe_dump(broken, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        tmp.replace(yaml_path)
    except Exception as exc:
        logger.error("auto_complete_profile: failed to write %s: %s", yaml_path, exc)
        raise HTTPException(status_code=500, detail=f"Could not save completed profile: {exc}")

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
        raise HTTPException(status_code=404, detail=f"Published track '{slug}' not found.")

    try:
        with open(path, encoding="utf-8") as f:
            payload = yaml.safe_load(f) or {}
    except Exception as exc:
        logger.error("get_track_reference: failed to read %r: %s", slug, exc)
        raise HTTPException(status_code=500, detail="Failed to read published track YAML.")

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
        raise HTTPException(status_code=409, detail=f"Draft track '{detail.slug}' already exists.")

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
        raise HTTPException(status_code=409, detail=f"Draft track '{slug}' already exists.")

    counsellor_input, source_type, source_label = _extract_generation_input(text, source_type, file)
    retrieved = _retrieve_generation_chunks(counsellor_input, embedder, store)

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
        raise HTTPException(status_code=422, detail="We could not generate a draft from this research yet.")
    except Exception as exc:
        logger.error("generate_draft_track: LLM call failed: %s", exc)
        raise HTTPException(status_code=503, detail="Draft generation service unavailable")

    try:
        detail = DraftTrackDetail(**raw)
    except Exception as exc:
        logger.warning("generate_draft_track: validation failed: %s | raw=%r", exc, str(raw)[:300])
        raise HTTPException(status_code=422, detail="We could not generate a draft from this research yet.")

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

    counsellor_input, source_type, source_label = _extract_generation_input(text, source_type, file)
    retrieved = _retrieve_generation_chunks(counsellor_input, embedder, store)

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
        logger.warning("refresh_draft_track_from_research: Claude returned malformed JSON: %s", exc)
        raise HTTPException(status_code=422, detail="We could not update this draft from the new research yet.")
    except Exception as exc:
        logger.error("refresh_draft_track_from_research: LLM call failed: %s", exc)
        raise HTTPException(status_code=503, detail="Draft generation service unavailable")

    try:
        detail = DraftTrackDetail(**raw)
    except Exception as exc:
        logger.warning("refresh_draft_track_from_research: validation failed: %s | raw=%r", exc, str(raw)[:300])
        raise HTTPException(status_code=422, detail="We could not update this draft from the new research yet.")

    detail.slug = slug
    detail.track_name = existing.track_name.strip()
    detail.status = "ready_for_publish" if _draft_ready_for_publish(detail) else "draft"
    detail.source_refs = _merge_source_refs(detail.source_refs, source_type, source_label)
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
        raise HTTPException(status_code=422, detail="Draft is incomplete and cannot be published yet.")
    try:
        version = draft_store.publish_draft(slug, actor="admin")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("publish_draft_track: failed for %r: %s", slug, exc)
        raise HTTPException(status_code=500, detail="Failed to publish draft track.")
    profile_store.invalidate()
    return TrackPublishResponse(status="ok", slug=slug, version=version, registry_updated=True)


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
    return TrackPublishResponse(status="ok", slug=slug, version=version, registry_updated=True)


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
        raise HTTPException(status_code=409, detail=f"Employer '{slug}' already exists.")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    payload = detail.model_dump(exclude_unset=True) if hasattr(detail, "model_dump") else detail.dict(exclude_unset=True)
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
            yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        tmp.replace(yaml_path)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        logger.error("create_employer: failed to write %r: %s", slug, exc)
        raise HTTPException(status_code=500, detail="Failed to write employer YAML.")

    employer_store.invalidate()
    logger.info("create_employer: created %r", slug)

    data["slug"] = slug
    from services.employer_store import _compute_completeness
    return EmployerDetail(**{**data, "completeness": _compute_completeness(data), "structured": {}})


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
    payload = detail.model_dump(exclude_unset=True) if hasattr(detail, "model_dump") else detail.dict(exclude_unset=True)
    # Merge incoming fields; server always sets last_updated
    existing.update({
        "employer_name": detail.employer_name.strip() if detail.employer_name else existing.get("employer_name", ""),
        "tracks": detail.tracks if detail.tracks is not None else existing.get("tracks", []),
        "ep_requirement": detail.ep_requirement,
        "intake_seasons": detail.intake_seasons if detail.intake_seasons is not None else existing.get("intake_seasons", []),
        "singapore_headcount_estimate": detail.singapore_headcount_estimate,
        "application_process": detail.application_process,
        "counsellor_contact": detail.counsellor_contact,
        "notes": detail.notes,
        "last_updated": now,
    })
    if "structured" in payload:
        existing["structured"] = dict(detail.structured or {})
    if "source_documents" in payload:
        existing["source_documents"] = list(detail.source_documents or [])
    # Preserve slug field
    existing["slug"] = slug

    tmp = yaml_path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            yaml.safe_dump(existing, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        tmp.replace(yaml_path)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        logger.error("update_employer: failed to write %r: %s", slug, exc)
        raise HTTPException(status_code=500, detail="Failed to write employer YAML.")

    employer_store.invalidate()
    logger.info("update_employer: updated %r", slug)

    from services.employer_store import _compute_completeness
    return EmployerDetail(**{**existing, "completeness": _compute_completeness(existing)})


@router.delete("/employers/{slug}", status_code=204)
def delete_employer(
    slug: str,
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
    """Disable an employer entity by renaming its YAML to *.yaml.disabled.

    Does NOT hard-delete — counsellor can restore via manual rename or future
    PATCH /api/kb/employers/{slug}/restore endpoint.
    Auth note: protected by the router-level `require_admin_key` dependency.
    TODO: Add PATCH restore endpoint — see TODOS.md "Restore path for disabled employer entities".
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
        raise HTTPException(status_code=400, detail="Employer has no notes or source documents to extract from.")

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
    # --- 1. Extract counsellor input text ---
    if source_type == "file" and file is not None:
        # Content-Length guard — fires before buffering the body.
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum upload size ({settings.max_upload_bytes // (1024*1024)}MB)."
            )
        raw_bytes = file.file.read()
        fname = file.filename or "upload.txt"
        try:
            counsellor_input = parse_file(raw_bytes, fname)
        except Exception as exc:
            logger.warning("analyse: failed to parse uploaded file %r: %s", fname, exc)
            raise HTTPException(status_code=422, detail="Could not extract text from the uploaded file.")
        source_label = fname
    else:
        if not text or not text.strip():
            raise HTTPException(status_code=422, detail="Provide either 'text' or a file upload.")
        counsellor_input = text.strip()
        source_label = "counsellor_note"

    # --- 2. Embed and retrieve top-10 KB chunks ---
    try:
        chunks_for_query = chunk_text(counsellor_input, max_tokens=256)
        query_text = chunks_for_query[0] if chunks_for_query else counsellor_input
        query_vec = embedder.encode(query_text)
        retrieved = store.search(query_vec, top_k=10)
    except Exception as exc:
        logger.error("analyse: KB search failed: %s", exc)
        raise HTTPException(status_code=503, detail="KB unavailable")

    # --- 3. Build profile + employer summaries for the diff prompt ---
    profile_summary = _build_profile_summary(profile_store)
    employer_summary = _build_employer_summary(employer_store)

    # --- 4. Call Claude ---
    try:
        raw = llm_service.analyse_kb_input(counsellor_input, retrieved, profile_summary, employer_summary)
    except ValueError as exc:
        logger.warning("analyse: Claude returned malformed JSON: %s", exc)
        raise HTTPException(
            status_code=422,
            detail="Analysis failed — please try again or rephrase your input.",
        )
    except Exception as exc:
        logger.error("analyse: LLM call failed: %s", exc)
        raise HTTPException(status_code=503, detail="Analysis service unavailable")

    # --- 5. Validate and fill chunk_ids ---
    try:
        result = KBAnalysisResult(**raw)
    except Exception as exc:
        logger.warning("analyse: Pydantic validation failed: %s | raw=%r", exc, str(raw)[:300])
        raise HTTPException(
            status_code=422,
            detail="Analysis failed — please try again or rephrase your input.",
        )

    provenance_timestamp = datetime.now(timezone.utc).isoformat()
    for i, chunk in enumerate(result.new_chunks):
        chunk.source_label = source_label
        chunk.source_type = source_type if source_type in ("note", "file") else "note"
        chunk.source_timestamp = chunk.source_timestamp or provenance_timestamp
        # Content-based chunk_id: same text → same ID (idempotent re-commit),
        # different text → different ID (no clobbering across distinct notes).
        content_key = chunk.text.strip()[:120]
        chunk.chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{source_label}::{content_key}"))

    for update_map in (result.profile_updates, result.employer_updates):
        for fields in update_map.values():
            for change in fields.values():
                change.source_type = change.source_type or source_type
                change.source_label = change.source_label or source_label
                change.source_timestamp = change.source_timestamp or provenance_timestamp

    return result


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
        raise HTTPException(status_code=422, detail=f"Too many chunks (max {_MAX_CHUNKS}).")
    for chunk in req.new_chunks:
        if chunk.source_type not in ("note", "file"):
            raise HTTPException(status_code=422, detail="Invalid source_type.")
        if len(chunk.text) > _MAX_CHUNK_TEXT:
            raise HTTPException(status_code=422, detail=f"Chunk text exceeds {_MAX_CHUNK_TEXT} chars.")

    chunk_result = upsert_kb_chunks(req.new_chunks, vector_store=store, embedder=embedder, source="commit-analysis")

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
            logger.info("commit-analysis: updated profile %r fields: %s", slug, result.changed_fields)
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
            logger.info("commit-analysis: updated employer %r fields: %s", slug, result.changed_fields)
        elif not result.skipped_missing:
            logger.info("commit-analysis: employer %r had no valid field updates", slug)

    # --- 4. Invalidate caches ---
    health_cache.invalidate_overlap_cache()
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
        # TODO: cache list_docs() result (60s TTL) when KB exceeds ~200 documents.
        # Currently O(n_chunks) scroll on every call — acceptable at pre-launch scale.
        docs = store.list_docs()
    except Exception as e:
        logger.error("Qdrant unavailable during kb_health: %s", e)
        raise HTTPException(status_code=503, detail="KB unavailable")

    total_docs = len(docs)
    total_chunks = sum(d["chunk_count"] for d in docs)

    # --- Overlap pairs (cached) ---
    cached = health_cache.get_overlap_pairs()
    if cached is None:
        try:
            cached = _compute_overlap_pairs(store)
            health_cache.set_overlap_pairs(cached)
        except Exception:
            logger.warning("Failed to compute overlap pairs", exc_info=True)
            cached = []

    overlapping_filenames = {p["doc_a"] for p in cached} | {p["doc_b"] for p in cached}

    doc_coverage = [
        DocCoverageItem(
            filename=d["filename"],
            chunk_count=d["chunk_count"],
            coverage_status="good" if d["chunk_count"] >= _COVERAGE_THIN_THRESHOLD else "thin",
            has_overlap_warning=d["filename"] in overlapping_filenames,
        )
        for d in docs
    ]

    high_overlap_pairs = [OverlapPair(**p) for p in cached]

    # --- Query log metrics ---
    window_start = datetime.now(timezone.utc) - timedelta(days=_LOG_WINDOW_DAYS)
    entries = _read_query_log(since=window_start)
    source_state = get_source_ledger_store().summarize_source_state(docs, entries)

    avg_match_score: Optional[float] = None
    retrieval_diversity_score: Optional[float] = None
    low_confidence_queries: list[LowConfidenceQuery] = []

    if entries:
        # avg_match_score: mean of top-1 scores across all queries in window
        all_top_scores = [e["scores"][0] for e in entries if e.get("scores")]
        if all_top_scores:
            avg_match_score = round(sum(all_top_scores) / len(all_top_scores), 4)

        # retrieval_diversity_score: avg distinct doc count in top-k results
        diversity_vals = []
        for e in entries:
            top_docs = e.get("top_docs", [])
            if top_docs:
                diversity_vals.append(len(set(top_docs)))
        if diversity_vals:
            retrieval_diversity_score = round(
                sum(diversity_vals) / len(diversity_vals), 2
            )

        # low_confidence_queries: recent queries with top score < threshold
        lc = [e for e in entries if e.get("scores") and e["scores"][0] < _LOW_CONFIDENCE_THRESHOLD]
        lc.sort(key=lambda e: e.get("ts", ""), reverse=True)
        low_confidence_queries = [
            LowConfidenceQuery(
                ts=e["ts"],
                query_text=e["query_text"],
                max_score=round(e["scores"][0], 4),
                doc_matched=e.get("doc_matched"),
            )
            for e in lc[:_MAX_LOW_CONF_QUERIES]
        ]

    return KBHealthResponse(
        total_docs=total_docs,
        total_chunks=total_chunks,
        avg_match_score=avg_match_score,
        retrieval_diversity_score=retrieval_diversity_score,
        low_confidence_queries=low_confidence_queries,
        doc_coverage=doc_coverage,
        high_overlap_pairs=high_overlap_pairs,
        source_state=source_state,
        active_sources=source_state.active_source_count,
        active_source_count=source_state.active_source_count,
        superseded_sources=source_state.superseded_source_count,
        superseded_source_count=source_state.superseded_source_count,
        stale_sources=source_state.stale_source_count,
        stale_source_count=source_state.stale_source_count,
        active_hits=source_state.active_hit_count,
        active_hit_count=source_state.active_hit_count,
        superseded_hits=source_state.superseded_hit_count,
        superseded_hit_count=source_state.superseded_hit_count,
        last_refreshed_at=source_state.last_refreshed_at,
        updated_at=source_state.last_refreshed_at,
        stale_source_evidence=source_state.stale_source_evidence,
    )


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
