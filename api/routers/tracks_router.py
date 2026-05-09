"""Career-track draft and publish endpoints."""

from __future__ import annotations

import yaml
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from dependencies import get_embedder, get_vector_store, require_admin_key
from models_tracks import (
    DraftTrackDetail,
    SourceRef,
    TrackPublishResponse,
    TrackReferenceDetail,
    TrackRegistryEntry,
    TrackVersionInfo,
)
from routers.kb_router_shared import draft_ready_for_publish, logger, profiles_dir
from services import llm as llm_service
from services.career_profiles import CareerProfileStore, get_career_profile_store
from services.embedder import Embedder
from services.kb_ingestion_service import (
    extract_generation_input,
    merge_source_refs,
    retrieve_generation_chunks,
)
from services.shared_yaml import safe_slug_is_valid
from services.track_drafts import (
    TrackDraftStore,
    get_track_draft_store,
    read_publish_journal,
)
from services.vector_store import VectorStore

router = APIRouter(prefix="/api/kb", dependencies=[Depends(require_admin_key)])


@router.get("/tracks", response_model=list[TrackRegistryEntry])
def list_tracks(
    draft_store: TrackDraftStore = Depends(get_track_draft_store),
):
    """List registered career tracks."""
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

    path = profiles_dir() / f"{slug}.yaml"
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

    detail.status = "ready_for_publish" if draft_ready_for_publish(detail) else "draft"
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
    detail.status = "ready_for_publish" if draft_ready_for_publish(detail) else "draft"
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
    detail.status = "ready_for_publish" if draft_ready_for_publish(detail) else "draft"
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
    detail.status = "ready_for_publish" if draft_ready_for_publish(detail) else "draft"
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
    if not draft_ready_for_publish(draft):
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
    """Read the track publish journal (JSONL), newest first."""
    return read_publish_journal()
