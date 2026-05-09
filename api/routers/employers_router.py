"""Employer-record admin endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

import yaml
from fastapi import APIRouter, Depends, HTTPException

from dependencies import require_admin_key
from models_employers import EmployerDetail, EmployerHistoryVersion
from routers.kb_router_shared import build_employer_detail, employers_dir, logger
from services.employer_store import (
    EmployerEntityStore,
    compute_completeness,
    get_employer_store,
)
from services.llm import extract_facts_from_prose
from services.shared_yaml import safe_slug_is_valid

router = APIRouter(prefix="/api/kb", dependencies=[Depends(require_admin_key)])


@router.get("/employers", response_model=list[EmployerDetail])
def list_employers(
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
    return [build_employer_detail(emp) for emp in employer_store.list_employers()]


@router.get("/employers/{slug}", response_model=EmployerDetail)
def get_employer(
    slug: str,
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")
    emp = employer_store.get_employer(slug)
    if emp is None:
        raise HTTPException(status_code=404, detail=f"Employer '{slug}' not found.")
    return build_employer_detail({**emp, "slug": emp.get("slug", slug)})


@router.get("/employers/{slug}/history", response_model=list[EmployerHistoryVersion])
def get_employer_history(
    slug: str,
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")
    return employer_store.list_history(slug)


@router.post("/employers", response_model=EmployerDetail, status_code=201)
def create_employer(
    detail: EmployerDetail,
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
    slug = detail.slug
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")
    if not detail.employer_name or not detail.employer_name.strip():
        raise HTTPException(status_code=422, detail="employer_name is required.")

    edir = employers_dir()
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
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")

    edir = employers_dir()
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
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")

    edir = employers_dir()
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
    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")

    edir = employers_dir()
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
    return build_employer_detail(
        {**restored, "completeness": compute_completeness(restored)}
    )


@router.post("/employers/{slug}/extract-facts")
async def extract_facts_from_employer_notes(
    slug: str,
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
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
