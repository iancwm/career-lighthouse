"""Canonical write paths for KB-backed YAML entities and vector chunks."""
from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import HTTPException
from pydantic import ValidationError

from constants.profile_fields import ALLOWED_ALUMNI_FIELDS, ALLOWED_EMPLOYER_FIELDS, ALLOWED_PROFILE_FIELDS
from models_employers import AlumniDetail
from models_kb import NewChunk
from services.career_profiles import CareerProfileStore, _default_profiles_dir, _derive_structured_fields
from services.employer_store import EmployerEntityStore, _default_employers_dir
from services.alumni_store import _normalize_profile_payload, get_alumni_store
from services.shared_yaml import atomic_yaml_write, safe_slug_is_valid

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WriteResult:
    changed_fields: list[str]
    is_new: bool
    skipped_missing: bool = False


@dataclass(frozen=True)
class ChunkUpsertResult:
    chunks_added: int


def _change_value(change: object) -> object:
    return getattr(change, "new", change)


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    return payload if isinstance(payload, dict) else {}


def apply_profile_diff(
    slug: str,
    diff: dict[str, Any],
    *,
    create_missing: bool = True,
    skip_invalid: bool = False,
    source: str | None = None,
) -> WriteResult:
    """Apply allowed fields to a career profile YAML and invalidate the profile cache."""
    if not safe_slug_is_valid(slug):
        if skip_invalid:
            logger.warning("%s: unsafe profile slug %r — skipping", source or "kb_writer", slug)
            return WriteResult(changed_fields=[], is_new=False, skipped_missing=True)
        raise HTTPException(status_code=422, detail="Invalid slug format")

    profiles_dir = Path(os.environ.get("CAREER_PROFILES_DIR", str(_default_profiles_dir())))
    yaml_path = profiles_dir / f"{slug}.yaml"
    is_new = not yaml_path.exists()
    if is_new and not create_missing:
        logger.warning("%s: profile %r not found on disk — skipping", source or "kb_writer", slug)
        return WriteResult(changed_fields=[], is_new=False, skipped_missing=True)

    profile = {} if is_new else _read_yaml_mapping(yaml_path)
    changed_fields: list[str] = []
    for field, raw_value in diff.items():
        if field == "slug":
            continue
        if field not in ALLOWED_PROFILE_FIELDS:
            logger.warning("%s: profile field %r not in allowlist — skipping", source or "kb_writer", field)
            continue
        profile[field] = _change_value(raw_value)
        changed_fields.append(field)

    derived = _derive_structured_fields(profile)
    if derived:
        existing_structured = profile.get("structured") or {}
        for key, value in derived.items():
            existing_structured.setdefault(key, value)
        profile["structured"] = existing_structured

    if changed_fields:
        try:
            atomic_yaml_write(yaml_path, profile)
        except Exception as exc:
            logger.error("%s: failed to write profile %r: %s", source or "kb_writer", slug, exc)
            raise HTTPException(status_code=500, detail=f"Failed to write profile '{slug}'") from exc
        CareerProfileStore().invalidate()

    return WriteResult(changed_fields=changed_fields, is_new=is_new)


def apply_employer_diff(
    slug: str,
    diff: dict[str, Any],
    *,
    create_missing: bool = True,
    snapshot: bool = False,
    skip_invalid: bool = False,
    source: str | None = None,
) -> WriteResult:
    """Apply allowed fields to an employer YAML and invalidate the employer cache."""
    if not safe_slug_is_valid(slug):
        if skip_invalid:
            logger.warning("%s: unsafe employer slug %r — skipping", source or "kb_writer", slug)
            return WriteResult(changed_fields=[], is_new=False, skipped_missing=True)
        raise HTTPException(status_code=422, detail="Invalid slug format")

    employers_dir = Path(os.environ.get("EMPLOYERS_DIR", str(_default_employers_dir())))
    yaml_path = employers_dir / f"{slug}.yaml"
    is_new = not yaml_path.exists()
    if is_new and not create_missing:
        logger.warning("%s: employer %r not found on disk — skipping", source or "kb_writer", slug)
        return WriteResult(changed_fields=[], is_new=False, skipped_missing=True)

    employer = {"slug": slug} if is_new else _read_yaml_mapping(yaml_path)
    store = EmployerEntityStore()
    if snapshot and not is_new:
        store.snapshot_history(slug, employer)

    changed_fields: list[str] = []
    for field, raw_value in diff.items():
        if field == "slug":
            continue
        if field not in ALLOWED_EMPLOYER_FIELDS:
            logger.warning("%s: employer field %r not in allowlist — skipping", source or "kb_writer", field)
            continue
        employer[field] = _change_value(raw_value)
        changed_fields.append(field)

    if changed_fields:
        employer["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            atomic_yaml_write(yaml_path, employer)
        except Exception as exc:
            logger.error("%s: failed to write employer %r: %s", source or "kb_writer", slug, exc)
            raise HTTPException(status_code=500, detail=f"Failed to write employer '{slug}'") from exc
        store.invalidate()

    return WriteResult(changed_fields=changed_fields, is_new=is_new)


def apply_alumni_diff(slug: str, diff: dict[str, Any], *, source: str | None = None) -> WriteResult:
    """Apply a validated alumni card diff using the alumni entity store."""
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format")

    store = get_alumni_store()
    existing = store.get_alumni(slug)
    has_company_links = "company_links" in diff
    company_links = diff.get("company_links") if has_company_links else None

    candidate_fields = {field: value for field, value in diff.items() if field != "slug" and field != "company_links"}
    unknown_fields = sorted(field for field in candidate_fields if field not in ALLOWED_ALUMNI_FIELDS)
    if unknown_fields:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid alumni card diff: unknown fields {', '.join(unknown_fields)}",
        )

    normalized = _normalize_profile_payload({"slug": slug, **candidate_fields}, existing=existing)
    normalized["slug"] = slug
    normalized["company_links"] = store.list_links(slug) if existing else []
    normalized["company_link_count"] = len(normalized["company_links"])
    normalized["completeness"] = existing.get("completeness", "amber") if existing else "amber"
    try:
        AlumniDetail.model_validate(normalized)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid alumni profile: {exc}") from exc

    changed_fields = list(candidate_fields.keys())
    if existing is None:
        if not normalized.get("full_name"):
            raise HTTPException(status_code=422, detail="Invalid alumni profile: full_name is required")
        store.create_alumni({"slug": slug, **candidate_fields})
        is_new = True
    else:
        store.update_alumni(slug, candidate_fields)
        is_new = False

    if has_company_links:
        store.sync_company_links(slug, company_links or [])
        changed_fields.append("company_links")

    return WriteResult(changed_fields=changed_fields, is_new=is_new)


def upsert_kb_chunks(
    chunks: list[NewChunk],
    *,
    vector_store: Any,
    embedder: Any,
    source: str | None = None,
) -> ChunkUpsertResult:
    """Validate, embed, and upsert new KB chunks into the vector store."""
    timestamp = datetime.now(timezone.utc).isoformat()
    points: list[dict[str, Any]] = []
    file_source_filenames: set[str] = set()

    for chunk in chunks:
        if not chunk.text.strip():
            continue
        if not chunk.chunk_id:
            chunk.chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{chunk.source_label}-{id(chunk)}"))
        if chunk.source_type == "note":
            date_suffix = datetime.now(timezone.utc).strftime("%Y%m%d")
            source_filename = f"counsellor_note_{date_suffix}"
        else:
            source_filename = chunk.source_label
            file_source_filenames.add(source_filename)

        try:
            vector = embedder.encode(chunk.text)
        except Exception as exc:
            logger.warning("%s: embed failed for chunk %r: %s", source or "kb_writer", chunk.chunk_id, exc)
            raise HTTPException(status_code=503, detail="Embedding service unavailable") from exc

        points.append({
            "id": chunk.chunk_id,
            "vector": vector,
            "payload": {
                "source_filename": source_filename,
                "chunk_index": 0,
                "upload_timestamp": timestamp,
                "text": chunk.text,
                "career_type": chunk.career_type,
            },
        })

    if points:
        for filename in file_source_filenames:
            try:
                vector_store.delete_by_filename(filename)
            except Exception as exc:
                logger.warning("%s: delete_by_filename(%r) failed: %s", source or "kb_writer", filename, exc)
        try:
            vector_store.upsert(points)
        except Exception as exc:
            logger.error("%s: Qdrant upsert failed: %s", source or "kb_writer", exc)
            raise HTTPException(status_code=503, detail="KB unavailable") from exc

    return ChunkUpsertResult(chunks_added=len(points))
