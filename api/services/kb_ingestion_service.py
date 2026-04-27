"""Business logic for diff-first KB ingestion and related research helpers."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile

from models_kb import KBAnalysisResult
from models_tracks import SourceRef
from services.career_profiles import CareerProfileStore
from services.employer_store import EmployerEntityStore
from services.embedder import Embedder
from services.ingestion import chunk_text, parse_file
from services import llm as llm_service
from services.vector_store import VectorStore

logger = logging.getLogger(__name__)


def first_sentence(text: str, max_chars: int = 120) -> str:
    """Extract the first sentence up to max_chars."""
    if not text:
        return ""
    text = str(text).strip()
    dot = text.find(".")
    if dot != -1 and dot < max_chars:
        return text[: dot + 1]
    return text[:max_chars]


def build_profile_summary(store: CareerProfileStore) -> str:
    """Build the CURRENT CAREER PROFILE FIELDS block for the diff prompt."""
    profiles = store.list_profiles()
    lines = []
    for meta in profiles:
        slug = meta["slug"]
        profile = store.get_profile(slug)
        if not profile:
            continue
        ep = first_sentence(str(profile.get("ep_sponsorship", "")))
        compass = first_sentence(str(profile.get("compass_score_typical", "")))
        timeline = first_sentence(str(profile.get("recruiting_timeline", "")))
        notes = first_sentence(str(profile.get("notes", "")))
        lines.append(
            f"{slug}: ep_sponsorship={ep} | compass={compass} | "
            f"recruiting_timeline={timeline} | notes={notes}"
        )
    return "\n".join(lines)


def build_employer_summary(store: EmployerEntityStore) -> str:
    """Build the CURRENT EMPLOYER FACTS block for the analyse diff prompt."""
    employers = store.list_employers()
    lines = []
    for emp in employers:
        slug = emp.get("slug", "")
        name = emp.get("employer_name", slug)
        ep = first_sentence(str(emp.get("ep_requirement", "")))
        seasons = ", ".join(emp.get("intake_seasons") or [])
        lines.append(f"{slug} ({name}): ep_requirement={ep} | intake_seasons={seasons}")
    return "\n".join(lines)


def extract_generation_input(
    text: str | None,
    source_type: str,
    file: UploadFile | None,
    *,
    error_context: str = "draft generation",
) -> tuple[str, str, str]:
    """Return counsellor input text plus normalized source metadata."""
    if source_type == "file" and file is not None:
        raw_bytes = file.file.read()
        fname = file.filename or "upload.txt"
        try:
            counsellor_input = parse_file(raw_bytes, fname)
        except Exception as exc:
            logger.warning("%s: failed to parse uploaded file %r: %s", error_context, fname, exc)
            raise HTTPException(status_code=422, detail="Could not extract text from the uploaded file.") from exc
        return counsellor_input, "file", fname

    if not text or not text.strip():
        raise HTTPException(status_code=422, detail="Provide either 'text' or a file upload.")
    return text.strip(), "note", "counsellor_note"


def retrieve_generation_chunks(
    counsellor_input: str,
    embedder: Embedder,
    store: VectorStore,
    *,
    top_k: int = 8,
    error_context: str = "draft generation",
) -> list[dict]:
    try:
        chunks_for_query = chunk_text(counsellor_input, max_tokens=256)
        query_text = chunks_for_query[0] if chunks_for_query else counsellor_input
        query_vec = embedder.encode(query_text)
        return store.search(query_vec, top_k=top_k)
    except Exception as exc:
        logger.error("%s: KB search failed: %s", error_context, exc)
        raise HTTPException(status_code=503, detail="KB unavailable") from exc


def merge_source_refs(existing_refs: list[dict] | list, source_type: str, source_label: str) -> list[SourceRef]:
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


def analyse_counsellor_input(
    *,
    text: str | None,
    source_type: str,
    file: UploadFile | None,
    embedder: Embedder,
    store: VectorStore,
    profile_store: CareerProfileStore,
    employer_store: EmployerEntityStore,
) -> KBAnalysisResult:
    """Analyse counsellor input and return a validated structured KB diff."""
    counsellor_input, _, source_label = extract_generation_input(
        text,
        source_type,
        file,
        error_context="analyse",
    )
    retrieved = retrieve_generation_chunks(
        counsellor_input,
        embedder,
        store,
        top_k=10,
        error_context="analyse",
    )

    profile_summary = build_profile_summary(profile_store)
    employer_summary = build_employer_summary(employer_store)

    try:
        raw = llm_service.analyse_kb_input(counsellor_input, retrieved, profile_summary, employer_summary)
    except ValueError as exc:
        logger.warning("analyse: Claude returned malformed JSON: %s", exc)
        raise HTTPException(
            status_code=422,
            detail="Analysis failed — please try again or rephrase your input.",
        ) from exc
    except Exception as exc:
        logger.error("analyse: LLM call failed: %s", exc)
        raise HTTPException(status_code=503, detail="Analysis service unavailable") from exc

    try:
        result = KBAnalysisResult(**raw)
    except Exception as exc:
        logger.warning("analyse: Pydantic validation failed: %s | raw=%r", exc, str(raw)[:300])
        raise HTTPException(
            status_code=422,
            detail="Analysis failed — please try again or rephrase your input.",
        ) from exc

    provenance_timestamp = datetime.now(timezone.utc).isoformat()
    safe_chunk_source_type = source_type if source_type in ("note", "file") else "note"
    for chunk in result.new_chunks:
        chunk.source_label = source_label
        chunk.source_type = safe_chunk_source_type
        chunk.source_timestamp = chunk.source_timestamp or provenance_timestamp
        content_key = chunk.text.strip()[:120]
        chunk.chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{source_label}::{content_key}"))

    for update_map in (result.profile_updates, result.employer_updates):
        for fields in update_map.values():
            for change in fields.values():
                change.source_type = change.source_type or source_type
                change.source_label = change.source_label or source_label
                change.source_timestamp = change.source_timestamp or provenance_timestamp

    return result
