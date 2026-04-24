"""Alumni admin endpoints.

Alumni are stored as first-class YAML entities with append-only company-link
events and counselor-facing extraction previews.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from dependencies import require_admin_key
from services.alumni_store import AlumniEntityStore, get_alumni_store
from services.shared_yaml import safe_slug

router = APIRouter(prefix="/api/kb", dependencies=[Depends(require_admin_key)])


def _slug_is_safe(slug: str) -> bool:
    return bool(slug) and slug.replace("_", "").replace("-", "").isalnum() and "/" not in slug and ".." not in slug


def _link_id_for_payload(alumni_slug: str, payload: dict[str, Any]) -> str:
    """Build a deterministic link ID from alumni slug + company/relationship fields for idempotent link upserts."""
    company_slug = str(payload.get("company_slug") or "").strip()
    company_name = str(payload.get("company_name") or "").strip()
    relationship = str(payload.get("relationship") or payload.get("role_title") or "").strip()
    start_date = str(payload.get("start_date") or "").strip()
    end_date = str(payload.get("end_date") or "").strip()
    link_type = str(payload.get("link_type") or "current").strip().lower() or "current"
    seed = "|".join([
        alumni_slug,
        company_slug or safe_slug(company_name),
        relationship,
        link_type,
        start_date,
        end_date,
    ])
    return safe_slug(seed) or f"{alumni_slug}-{company_slug or safe_slug(company_name) or 'link'}"


def _normalize_company_link(raw: Any) -> dict[str, Any] | None:
    """Coerce heterogeneous company link payloads (raw string or multi-alias dict) into a canonical dict.

    Handles camelCase/snake_case aliases from various frontend submissions. Returns None if company identity
    (name or slug) is absent after normalization.
    """
    if not isinstance(raw, dict):
        text = str(raw).strip()
        if not text:
            return None
        return {
            "company_name": text,
            "company_slug": safe_slug(text),
            "relationship": "",
            "role_title": "",
            "notes": "",
            "link_type": "current",
        }

    company_name = str(
        raw.get("company_name")
        or raw.get("companyName")
        or raw.get("employer_name")
        or raw.get("name")
        or ""
    ).strip()
    company_slug = str(
        raw.get("company_slug")
        or raw.get("companySlug")
        or raw.get("employer_slug")
        or raw.get("slug")
        or ""
    ).strip() or safe_slug(company_name)
    relationship = str(raw.get("relationship") or raw.get("role") or raw.get("connection") or raw.get("link_type") or "").strip()
    role_title = str(raw.get("role_title") or raw.get("position") or "").strip() or relationship
    notes = str(raw.get("notes") or raw.get("note") or raw.get("summary") or raw.get("rationale") or "").strip()
    link_type = str(raw.get("link_type") or "current").strip().lower() or "current"
    if link_type not in {"current", "former", "advisory"}:
        link_type = "current"

    if not company_name and not company_slug:
        return None

    return {
        "company_name": company_name or company_slug.replace("_", " ").title(),
        "company_slug": company_slug,
        "relationship": relationship,
        "role_title": role_title,
        "notes": notes,
        "start_date": str(raw.get("start_date") or "").strip() or None,
        "end_date": str(raw.get("end_date") or "").strip() or None,
        "link_type": link_type,
        "confidence": raw.get("confidence"),
        "evidence": raw.get("evidence") or [],
        "rationale": notes or str(raw.get("rationale") or "").strip() or None,
        "source_type": str(raw.get("source_type") or "").strip() or None,
        "source_label": str(raw.get("source_label") or "").strip() or None,
        "source_timestamp": str(raw.get("source_timestamp") or "").strip() or None,
    }


def _normalize_profile_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Alias legacy field names and strip company_links, which are managed as separate link events."""
    data = dict(payload)
    if not data.get("full_name") and data.get("name"):
        data["full_name"] = data["name"]
    if not data.get("graduation_program") and data.get("degree"):
        data["graduation_program"] = data["degree"]
    if not data.get("graduation_school") and data.get("school"):
        data["graduation_school"] = data["school"]
    if "consent_for_referrals" not in data and "available_for_mentoring" in data:
        data["consent_for_referrals"] = data["available_for_mentoring"]
    data.pop("company_links", None)
    return data


def _serialize_company_link(link: dict[str, Any]) -> dict[str, Any]:
    """Normalize a stored company link event for JSON serialization, ensuring relationship and role_title are always strings."""
    relationship = str(link.get("relationship") or link.get("role_title") or "").strip()
    notes = str(link.get("notes") or link.get("rationale") or "").strip()
    return {
        **link,
        "relationship": relationship,
        "role_title": str(link.get("role_title") or relationship).strip(),
        "notes": notes,
        "company_name": str(link.get("company_name") or link.get("company_slug") or "").strip(),
    }


def _serialize_profile(profile: dict[str, Any], links: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Assemble the full API response for an alumni profile, resolving field aliases and computing mentoring availability."""
    company_links = [_serialize_company_link(link) for link in (links or [])]
    available = profile.get("available_for_mentoring")
    if available is None:
        available = profile.get("consent_for_referrals")
    if available is None:
        available = profile.get("can_refer") == "yes"

    graduation_year = profile.get("graduation_year")
    if graduation_year in ("", None):
        graduation_year = None
    elif not isinstance(graduation_year, str):
        graduation_year = str(graduation_year)

    return {
        **profile,
        "name": profile.get("full_name") or profile.get("name") or "",
        "degree": profile.get("graduation_program") or profile.get("degree") or "",
        "school": profile.get("graduation_school") or profile.get("school") or "",
        "graduation_year": graduation_year,
        "available_for_mentoring": bool(available),
        "notes": profile.get("notes") or profile.get("help_capacity") or profile.get("consent_scope_notes") or "",
        "company_links": company_links,
        "company_link_count": len(company_links) or int(profile.get("company_link_count") or 0),
    }


def _proposal_value_to_text(proposal: Any) -> str:
    """Extract the text value from an LLM proposal dict (with a 'value' key) or a raw scalar."""
    if isinstance(proposal, dict):
        value = proposal.get("value")
    else:
        value = proposal
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)


def _sync_company_links(store: AlumniEntityStore, slug: str, submitted_links: list[dict[str, Any]]) -> None:
    """Reconcile submitted company links against stored links: upsert desired links and archive links absent from the submission."""
    desired_ids: list[str] = []
    seen_ids: set[str] = set()
    for raw in submitted_links:
        normalized = _normalize_company_link(raw)
        if not normalized:
            continue
        link_id = _link_id_for_payload(slug, normalized)
        if link_id in seen_ids:
            continue
        seen_ids.add(link_id)
        desired_ids.append(link_id)
        store.append_link(slug, normalized, link_id=link_id)

    existing_ids = {str(link.get("link_id") or "").strip() for link in store.list_links(slug) if str(link.get("link_id") or "").strip()}
    for link_id in sorted(existing_ids - set(desired_ids)):
        store.delete_link(slug, link_id)


@router.get("/alumni")
def list_alumni(store: AlumniEntityStore = Depends(get_alumni_store)):
    return [_serialize_profile(profile, store.list_links(str(profile.get("slug") or ""))) for profile in store.list_alumni()]


@router.get("/alumni/{slug}")
def get_alumni(slug: str, store: AlumniEntityStore = Depends(get_alumni_store)):
    if not _slug_is_safe(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")
    profile = store.get_alumni(slug)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Alumni '{slug}' not found.")
    return _serialize_profile(profile, store.list_links(slug))


@router.get("/alumni/{slug}/history")
def get_alumni_history(slug: str, store: AlumniEntityStore = Depends(get_alumni_store)):
    if not _slug_is_safe(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")
    profile = store.get_alumni(slug)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Alumni '{slug}' not found.")
    return store.list_history(slug)


@router.post("/alumni")
def create_alumni(payload: dict[str, Any] = Body(default_factory=dict), store: AlumniEntityStore = Depends(get_alumni_store)):
    normalized = _normalize_profile_payload(payload)
    slug = str(normalized.get("slug") or normalized.get("full_name") or normalized.get("name") or "").strip()
    slug = safe_slug(slug)
    if not _slug_is_safe(slug):
        raise HTTPException(status_code=422, detail="Invalid or missing slug.")
    if not normalized.get("full_name"):
        raise HTTPException(status_code=422, detail="full_name is required.")

    normalized["slug"] = slug
    company_links = list(payload.get("company_links") or payload.get("companyLinks") or [])
    try:
        profile = store.create_alumni(normalized)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _sync_company_links(store, slug, company_links)
    return _serialize_profile(store.get_alumni(slug) or profile, store.list_links(slug))


@router.put("/alumni/{slug}")
def update_alumni(
    slug: str,
    payload: dict[str, Any] = Body(default_factory=dict),
    store: AlumniEntityStore = Depends(get_alumni_store),
):
    if not _slug_is_safe(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")
    if store.get_alumni(slug) is None:
        raise HTTPException(status_code=404, detail=f"Alumni '{slug}' not found.")

    normalized = _normalize_profile_payload(payload)
    normalized["slug"] = slug
    company_links = list(payload.get("company_links") or payload.get("companyLinks") or [])
    try:
        profile = store.update_alumni(slug, normalized)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _sync_company_links(store, slug, company_links)
    return _serialize_profile(store.get_alumni(slug) or profile, store.list_links(slug))


@router.post("/alumni/extract-preview")
def extract_preview(
    payload: dict[str, Any] = Body(default_factory=dict),
    store: AlumniEntityStore = Depends(get_alumni_store),
):
    notes = str(payload.get("notes") or payload.get("text") or "").strip()
    if not notes:
        raise HTTPException(status_code=422, detail="notes are required.")

    alumni_slug = str(payload.get("alumni_slug") or payload.get("alumniSlug") or "").strip() or None
    source_type = str(payload.get("source_type") or payload.get("sourceType") or "note").strip() or "note"
    source_label = str(payload.get("source_label") or payload.get("sourceLabel") or "counsellor_note").strip() or "counsellor_note"

    preview = store.preview_from_notes(
        notes,
        source_label=source_label,
        source_type=source_type,
        alumni_slug=alumni_slug,
    )

    profile_updates = preview.get("profile_updates")
    if not isinstance(profile_updates, dict):
        profile_updates = {}
        for field, proposal in (preview.get("profile_proposals") or {}).items():
            profile_updates[field] = {
                "old": None,
                "new": _proposal_value_to_text(proposal),
            }

    company_links_source = preview.get("company_links")
    if not isinstance(company_links_source, list):
        company_links_source = preview.get("company_link_proposals") or []
    company_link_proposals = [_serialize_company_link(link) for link in company_links_source if isinstance(link, dict)]

    bullets = list(preview.get("interpretation_bullets") or preview.get("summary_bullets") or [])

    facts_source = preview.get("facts")
    if isinstance(facts_source, list) and facts_source:
        facts = facts_source
    else:
        fit_triad = preview.get("fit_triad") or {}
        facts = []
        for field, proposal in fit_triad.items():
            if not isinstance(proposal, dict):
                continue
            facts.append({
                "slug": f"{alumni_slug or 'alumni'}-{safe_slug(field)}",
                "type": field,
                "confidence": proposal.get("confidence", 0),
                "source": source_type,
                "data": {
                    "value": proposal.get("value"),
                    "evidence": proposal.get("evidence", []),
                    "rationale": proposal.get("rationale"),
                },
            })

    return {
        **preview,
        "interpretation_bullets": bullets,
        "summary_bullets": bullets,
        "profile_updates": profile_updates,
        "company_links": company_link_proposals,
        "facts": facts,
        "raw": preview,
    }


@router.post("/alumni/backfill-legacy")
def backfill_legacy_alumni(store: AlumniEntityStore = Depends(get_alumni_store)):
    return store.backfill_legacy_alumni()
