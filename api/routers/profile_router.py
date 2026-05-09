"""Career-profile admin endpoints."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException

from cfg import career_profiles_cfg
from dependencies import require_admin_key
from routers.kb_router_shared import logger
from services import llm as llm_service
from services.career_profiles import (
    CareerProfileStore,
    default_profiles_dir,
    get_career_profile_store,
)

router = APIRouter(prefix="/api/kb", dependencies=[Depends(require_admin_key)])


@router.get("/career-profiles")
def career_profiles(
    profile_store: CareerProfileStore = Depends(get_career_profile_store),
):
    """List all loaded career profiles with metadata (admin use only)."""
    return profile_store.list_profiles()


@router.get("/career-profiles/broken")
def broken_career_profiles(
    profile_store: CareerProfileStore = Depends(get_career_profile_store),
):
    """List career profiles that failed validation due to missing required fields."""
    return profile_store.list_broken_profiles()


@router.post("/career-profiles/{slug}/auto-complete", response_model=dict)
async def auto_complete_profile(
    slug: str,
    profile_store: CareerProfileStore = Depends(get_career_profile_store),
):
    """Use the LLM to fill in missing required fields for a broken career profile."""
    broken = profile_store.get_broken_profile(slug)
    if broken is None:
        raise HTTPException(
            status_code=404, detail=f"Broken profile '{slug}' not found"
        )

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

    for field, value in filled.items():
        if field in missing:
            broken[field] = value

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

    profile_store.invalidate()
    return {"slug": slug, "completed_fields": list(filled.keys()), "profile": broken}
