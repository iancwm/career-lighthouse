"""Alumni entity service backed by canonical YAML files.

Alumni are stored as first-class entities under knowledge/alumni/, with
append-only company-link events under knowledge/alumni_company_links/ and
immutable history snapshots under knowledge/alumni_history/.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel

from cfg import model_cfg, prompts_cfg
from config import settings
from models import (
    AlumniCompanyLink,
    AlumniCompanyLinkInput,
    AlumniDetail,
    AlumniExtractionPreview,
    AlumniHistoryVersion,
    AlumniLinkVersion,
)
from services.employer_store import _default_employers_dir
from services.shared_yaml import (
    atomic_yaml_write,
    normalize_list,
    read_yaml,
    safe_slug,
    utc_now_iso,
    version_stamp,
)
from services import llm as llm_service

logger = logging.getLogger(__name__)

SCHOOL_NAME = model_cfg["school"]["name"]
_prompts = prompts_cfg.get("prompts", {})

_COMPLETENESS_REQUIRED: frozenset[str] = frozenset([
    "full_name",
    "current_company",
    "current_title",
    "last_confirmed_at",
])
_CAN_REFER_MIN_CONFIDENCE = 80
_ALLOWED_CAN_REFER = {"yes", "maybe", "no"}
_ALLOWED_NETWORK = {"low", "medium", "high"}
_ALLOWED_LINK_TYPES = {"current", "former", "advisory"}


def _default_alumni_dir() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "knowledge" / "alumni",
        Path(__file__).resolve().parent.parent.parent.parent / "knowledge" / "alumni",
    ]
    for path in candidates:
        if path.parent.exists():
            return path
    return candidates[0]


def _default_alumni_history_dir() -> Path:
    return _default_alumni_dir().parent / "alumni_history"


def _default_alumni_links_dir() -> Path:
    return _default_alumni_dir().parent / "alumni_company_links"


def _default_backfill_manifest_path() -> Path:
    return _default_alumni_dir() / "_backfill_manifest.yaml"


def _alumni_dir() -> Path:
    return Path(os.environ.get("ALUMNI_DIR", str(_default_alumni_dir())))


def _history_dir() -> Path:
    return Path(os.environ.get("ALUMNI_HISTORY_DIR", str(_default_alumni_history_dir())))


def _links_dir() -> Path:
    return Path(os.environ.get("ALUMNI_COMPANY_LINKS_DIR", str(_default_alumni_links_dir())))


def _manifest_path() -> Path:
    return Path(os.environ.get("ALUMNI_BACKFILL_MANIFEST_PATH", str(_default_backfill_manifest_path())))


def _slug_is_safe(slug: str) -> bool:
    return bool(slug) and slug.replace("_", "").replace("-", "").isalnum() and "/" not in slug and ".." not in slug


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "yes", "y", "1"}:
        return True
    if text in {"false", "no", "n", "0"}:
        return False
    return None


def _normalize_profile_payload(payload: dict[str, Any], *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge and normalize an alumni profile payload over an optional existing record.

    Handles field aliases (name→full_name, degree→graduation_program), coerces
    enums (can_refer, network_strength, lifecycle), validates referral consent rules,
    and strips transient display fields (company_links, completeness, company_link_count).
    """
    data = dict(existing or {})
    data.update({k: v for k, v in payload.items() if v is not None})

    if not data.get("full_name") and data.get("name"):
        data["full_name"] = data.pop("name")
    if not data.get("graduation_program") and data.get("degree"):
        data["graduation_program"] = data.get("degree")
    if not data.get("graduation_school") and data.get("school"):
        data["graduation_school"] = data.get("school")

    for key in (
        "full_name",
        "name",
        "degree",
        "school",
        "graduation_school",
        "graduation_program",
        "current_title",
        "current_company",
        "notes",
        "help_capacity",
        "available_for_mentoring",
        "can_refer_rationale",
        "communication_style",
        "consent_scope_notes",
        "source_type",
        "source_label",
        "source_timestamp",
        "trace_id",
        "last_confirmed_at",
        "last_updated",
        "superseded_by",
        "archived_at",
    ):
        if key in data:
            data[key] = _normalize_text(data.get(key))

    for key in ("career_goals_domains", "mentoring_modes", "preferred_student_traits", "common_interests", "can_refer_evidence"):
        data[key] = normalize_list(data.get(key))

    if data.get("graduation_year") is not None:
        year = data["graduation_year"]
        if isinstance(year, str):
            year = year.strip()
            if year.isdigit():
                year = int(year)
        data["graduation_year"] = year

    network_strength = _normalize_text(data.get("network_strength"))
    if network_strength is not None:
        network_strength = network_strength.lower()
        if network_strength in {"med", "moderate"}:
            network_strength = "medium"
        if network_strength not in _ALLOWED_NETWORK:
            network_strength = None
    data["network_strength"] = network_strength

    can_refer = _normalize_text(data.get("can_refer"))
    can_refer = can_refer.lower() if can_refer else "maybe"
    if can_refer not in _ALLOWED_CAN_REFER:
        can_refer = "maybe"
    data["can_refer"] = can_refer

    confidence = data.get("can_refer_confidence")
    try:
        confidence = int(confidence) if confidence is not None and str(confidence).strip() else None
    except (TypeError, ValueError):
        confidence = None
    data["can_refer_confidence"] = confidence

    if can_refer == "yes":
        evidence = [str(item).strip() for item in data.get("can_refer_evidence", []) if str(item).strip()]
        consent = data.get("consent_for_referrals")
        if consent is False or confidence is None or confidence < _CAN_REFER_MIN_CONFIDENCE or not evidence:
            data["can_refer"] = "maybe"
            data["can_refer_evidence"] = evidence
            data.setdefault(
                "can_refer_rationale",
                "Requires stronger evidence and explicit referral consent before can_refer=yes.",
            )

    consent = data.get("consent_for_referrals")
    if isinstance(consent, str):
        consent = consent.strip().lower()
        if consent in {"true", "yes", "y", "1"}:
            consent = True
        elif consent in {"false", "no", "n", "0"}:
            consent = False
        else:
            consent = None
    if consent not in {True, False, None}:
        consent = None
    available_for_mentoring = _normalize_bool(data.get("available_for_mentoring"))
    if consent is None and available_for_mentoring is not None:
        consent = available_for_mentoring
    data["consent_for_referrals"] = consent
    data["available_for_mentoring"] = available_for_mentoring

    lifecycle = _normalize_text(data.get("lifecycle"))
    if lifecycle not in {"active", "superseded", "archived"}:
        lifecycle = "active"
    data["lifecycle"] = lifecycle
    data["deleted"] = bool(data.get("deleted", False))

    for key in ("company_link_count", "completeness", "company_links"):
        data.pop(key, None)

    return data


def _compute_completeness(profile: dict[str, Any], *, company_link_count: int = 0) -> str:
    """Return 'green' when all required fields are populated, referral consent is set, and at least one company link exists; else 'amber'."""
    for field in _COMPLETENESS_REQUIRED:
        value = profile.get(field)
        if value is None:
            return "amber"
        if isinstance(value, str) and not value.strip():
            return "amber"
    if profile.get("can_refer") == "yes" and profile.get("consent_for_referrals") is not True:
        return "amber"
    if not company_link_count:
        return "amber"
    return "green"


def _profile_path(slug: str) -> Path:
    return _alumni_dir() / f"{slug}.yaml"


def _disabled_profile_path(slug: str) -> Path:
    return _alumni_dir() / f"{slug}.yaml.disabled"


def _profile_history_dir(slug: str) -> Path:
    return _history_dir() / slug


def _link_event_dir(slug: str) -> Path:
    return _links_dir() / slug


def _profile_history_payload(slug: str) -> list[dict[str, Any]]:
    history_dir = _profile_history_dir(slug)
    if not history_dir.exists():
        return []
    entries: list[dict[str, Any]] = []
    for yaml_path in sorted(history_dir.glob("*.yaml"), reverse=True):
        entries.append({
            "version": yaml_path.stem,
            "recorded_at": yaml_path.stem,
            "filename": yaml_path.name,
        })
    return entries


def _link_history_payload(slug: str) -> list[dict[str, Any]]:
    events_dir = _link_event_dir(slug)
    if not events_dir.exists():
        return []
    entries: list[dict[str, Any]] = []
    for yaml_path in sorted(events_dir.glob("*.yaml"), reverse=True):
        payload = read_yaml(yaml_path)
        if not isinstance(payload, dict):
            continue
        entries.append({
            "version": yaml_path.stem,
            "recorded_at": payload.get("recorded_at") or yaml_path.stem,
            "filename": yaml_path.name,
            "link_id": payload.get("link_id", ""),
            "lifecycle": payload.get("lifecycle", "active"),
        })
    return entries


def _load_manifest() -> dict[str, Any]:
    payload = read_yaml(_manifest_path())
    if isinstance(payload, dict):
        payload.setdefault("source_signatures", [])
        return payload
    return {"source_signatures": []}


def _save_manifest(payload: dict[str, Any]) -> None:
    atomic_yaml_write(_manifest_path(), payload)


def _manifest_signature_set() -> set[str]:
    manifest = _load_manifest()
    return {str(item) for item in manifest.get("source_signatures", []) if str(item).strip()}


def _record_manifest_signature(signature: str) -> None:
    manifest = _load_manifest()
    signatures = {str(item) for item in manifest.get("source_signatures", []) if str(item).strip()}
    signatures.add(signature)
    manifest["source_signatures"] = sorted(signatures)
    manifest["migrated_at"] = utc_now_iso()
    _save_manifest(manifest)


def _normalise_name_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


def _resolve_company(company_slug: str | None = None, company_name: str | None = None) -> tuple[str, str | None]:
    """Derive a canonical (slug, display_name) pair for a company, cross-referencing the EmployerEntityStore for known slugs."""
    slug = _normalize_text(company_slug)
    name = _normalize_text(company_name)
    if slug:
        slug = safe_slug(slug)

    employer_names: dict[str, str] = {}
    try:
        from services.employer_store import get_employer_store

        store = get_employer_store()
        for employer in store.list_employers():
            employer_slug = str(employer.get("slug") or "").strip()
            employer_name = str(employer.get("employer_name") or "").strip()
            if employer_slug:
                employer_names[_normalise_name_key(employer_slug)] = employer_slug
            if employer_name:
                employer_names[_normalise_name_key(employer_name)] = employer_slug or safe_slug(employer_name)
    except Exception:
        pass

    if slug and not name:
        name = slug.replace("_", " ").title()

    if not slug and name:
        slug = employer_names.get(_normalise_name_key(name), safe_slug(name))

    if slug and not name:
        name = slug.replace("_", " ").title()
    return slug or "", name


def _load_profile_file(path: Path) -> dict[str, Any] | None:
    payload = read_yaml(path)
    if not isinstance(payload, dict):
        return None
    payload.setdefault("slug", path.stem)
    payload = _normalize_profile_payload(payload)
    return payload


def _current_active_link_for_id(events: list[dict[str, Any]], link_id: str) -> dict[str, Any] | None:
    """Return the first event matching link_id with lifecycle='active', or None if archived/absent."""
    for event in events:
        if str(event.get("link_id") or "") != link_id:
            continue
        if str(event.get("lifecycle") or "active") != "active":
            return None
        return event
    return None


def _event_signature(source_signature: str) -> str:
    return hashlib.sha1(source_signature.encode("utf-8")).hexdigest()[:12]


def _event_path(slug: str, link_id: str) -> Path:
    stamp = version_stamp()
    return _link_event_dir(slug) / f"{stamp}-{safe_slug(link_id)}.yaml"


def _profile_response(profile: dict[str, Any], *, company_link_count: int) -> dict[str, Any]:
    response = dict(profile)
    response["company_link_count"] = company_link_count
    response["completeness"] = _compute_completeness(profile, company_link_count=company_link_count)
    return response


def _preferred_profile_slug(full_name: str, existing: dict[str, str]) -> str:
    """Derive a unique YAML-safe slug for an alumni profile, appending a disambiguating suffix when the base slug is already taken by a different person."""
    base = safe_slug(full_name)
    if not base:
        base = safe_slug(full_name.replace(" ", "_")) or "alumni"
    if base not in existing:
        return base
    if _normalise_name_key(existing.get(base, "")) == _normalise_name_key(full_name):
        return base
    for suffix_source in ("graduation_year", "current_company", "current_title"):
        candidate = existing.get(f"{base}:{suffix_source}")
        if candidate:
            return candidate
    candidate = f"{base}_{hashlib.sha1(full_name.encode('utf-8')).hexdigest()[:8]}"
    existing[f"{base}:graduation_year"] = candidate
    return candidate


class AlumniEntityStore:
    """Singleton YAML store for alumni profiles and append-only company links."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._profiles: dict[str, dict[str, Any]] = {}
        self._load_profiles()
        self._loaded = True

    def _load_profiles(self) -> None:
        alumni_dir = _alumni_dir()
        if not alumni_dir.exists():
            logger.info("Alumni directory not found: %s", alumni_dir)
            return

        yaml_files = sorted(alumni_dir.glob("*.yaml"))
        loaded = 0
        for yaml_path in yaml_files:
            if yaml_path.name.startswith("_"):
                continue
            profile = _load_profile_file(yaml_path)
            if not profile or not profile.get("full_name"):
                continue
            slug = yaml_path.stem
            profile["slug"] = slug
            profile["company_link_count"] = len(self.list_links(slug))
            profile["completeness"] = _compute_completeness(profile, company_link_count=profile["company_link_count"])
            self._profiles[slug] = profile
            loaded += 1
        logger.info("AlumniEntityStore: loaded %d profile(s) from %s", loaded, alumni_dir)

    def invalidate(self) -> None:
        self._loaded = False

    def list_alumni(self) -> list[dict[str, Any]]:
        self._ensure_loaded()
        profiles = []
        for slug, profile in self._profiles.items():
            enriched = dict(profile)
            enriched["company_link_count"] = len(self.list_links(slug))
            enriched["completeness"] = _compute_completeness(enriched, company_link_count=enriched["company_link_count"])
            profiles.append(enriched)
        return sorted(profiles, key=lambda item: (str(item.get("full_name") or "").lower(), item.get("slug", "")))

    def get_alumni(self, slug: str | None) -> dict[str, Any] | None:
        if not slug:
            return None
        self._ensure_loaded()
        profile = self._profiles.get(slug)
        if profile is None:
            return None
        enriched = dict(profile)
        enriched["company_link_count"] = len(self.list_links(slug))
        enriched["completeness"] = _compute_completeness(enriched, company_link_count=enriched["company_link_count"])
        return enriched

    def list_history(self, slug: str) -> list[dict[str, Any]]:
        return _profile_history_payload(slug)

    def list_link_history(self, slug: str) -> list[dict[str, Any]]:
        return _link_history_payload(slug)

    def snapshot_history(self, slug: str, payload: dict[str, Any]) -> str:
        version = version_stamp()
        history_path = _profile_history_dir(slug) / f"{version}.yaml"
        atomic_yaml_write(history_path, payload)
        return version

    def _write_profile(self, slug: str, payload: dict[str, Any]) -> dict[str, Any]:
        profile_path = _profile_path(slug)
        atomic_yaml_write(profile_path, payload)
        self.invalidate()
        return payload

    def create_alumni(self, payload: dict[str, Any]) -> dict[str, Any]:
        slug = _normalize_text(payload.get("slug")) or ""
        if not _slug_is_safe(slug):
            raise ValueError("Invalid alumni slug")
        profile_path = _profile_path(slug)
        disabled_path = _disabled_profile_path(slug)
        if profile_path.exists() or disabled_path.exists():
            raise FileExistsError(f"Alumni '{slug}' already exists")

        profile = _normalize_profile_payload({**payload, "slug": slug})
        if not profile.get("full_name"):
            raise ValueError("full_name is required")
        profile.setdefault("source_timestamp", utc_now_iso())
        profile.setdefault("last_confirmed_at", profile["source_timestamp"])
        profile.setdefault("last_updated", utc_now_iso())
        profile["slug"] = slug
        profile["company_link_count"] = 0
        profile["completeness"] = _compute_completeness(profile, company_link_count=0)
        self._write_profile(slug, profile)
        return profile

    def update_alumni(self, slug: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not _slug_is_safe(slug):
            raise ValueError("Invalid alumni slug")
        profile_path = _profile_path(slug)
        if not profile_path.exists():
            raise FileNotFoundError(f"Alumni '{slug}' not found")

        existing = _load_profile_file(profile_path)
        if not existing:
            raise FileNotFoundError(f"Alumni '{slug}' not found")

        self.snapshot_history(slug, existing)
        merged = _normalize_profile_payload(payload, existing=existing)
        merged["slug"] = slug
        merged.setdefault("source_timestamp", existing.get("source_timestamp") or utc_now_iso())
        merged.setdefault("last_confirmed_at", utc_now_iso())
        merged["last_updated"] = utc_now_iso()
        merged["company_link_count"] = len(self.list_links(slug))
        merged["completeness"] = _compute_completeness(merged, company_link_count=merged["company_link_count"])
        self._write_profile(slug, merged)
        return merged

    def delete_alumni(self, slug: str) -> None:
        if not _slug_is_safe(slug):
            raise ValueError("Invalid alumni slug")
        profile_path = _profile_path(slug)
        if not profile_path.exists():
            raise FileNotFoundError(f"Alumni '{slug}' not found")
        existing = _load_profile_file(profile_path) or {}
        self.snapshot_history(slug, existing)
        profile_path.rename(_disabled_profile_path(slug))
        self.invalidate()

    def list_links(self, slug: str) -> list[dict[str, Any]]:
        events = self.list_link_events(slug)
        seen: set[str] = set()
        resolved: list[dict[str, Any]] = []
        for event in events:
            link_id = str(event.get("link_id") or "").strip()
            if not link_id or link_id in seen:
                continue
            seen.add(link_id)
            if str(event.get("lifecycle") or "active") != "active":
                continue
            resolved.append(event)
        return resolved

    def list_link_events(self, slug: str) -> list[dict[str, Any]]:
        events_dir = _link_event_dir(slug)
        if not events_dir.exists():
            return []
        records: list[dict[str, Any]] = []
        for yaml_path in sorted(events_dir.glob("*.yaml"), reverse=True):
            payload = read_yaml(yaml_path)
            if not isinstance(payload, dict):
                continue
            payload.setdefault("version", yaml_path.stem)
            payload.setdefault("filename", yaml_path.name)
            records.append(payload)
        return records

    def get_link(self, slug: str, link_id: str) -> dict[str, Any] | None:
        for event in self.list_link_events(slug):
            if str(event.get("link_id") or "") == link_id and str(event.get("lifecycle") or "active") == "active":
                return event
        return None

    def append_link(self, slug: str, payload: dict[str, Any], link_id: str | None = None) -> dict[str, Any]:
        if not _slug_is_safe(slug):
            raise ValueError("Invalid alumni slug")
        profile = self.get_alumni(slug)
        if profile is None:
            raise FileNotFoundError(f"Alumni '{slug}' not found")

        data = self._normalize_link_payload(slug, payload, link_id=link_id)
        event_dir = _link_event_dir(slug)
        event_dir.mkdir(parents=True, exist_ok=True)
        event_path = _event_path(slug, data["link_id"])
        atomic_yaml_write(event_path, data)
        self.invalidate()
        return data

    def update_link(self, slug: str, link_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.get_link(slug, link_id)
        if current is None:
            raise FileNotFoundError(f"Link '{link_id}' not found for alumni '{slug}'")
        payload = {**current, **payload, "link_id": link_id}
        payload.pop("version", None)
        payload.pop("filename", None)
        return self.append_link(slug, payload, link_id=link_id)

    def delete_link(self, slug: str, link_id: str) -> dict[str, Any]:
        current = self.get_link(slug, link_id)
        if current is None:
            raise FileNotFoundError(f"Link '{link_id}' not found for alumni '{slug}'")
        payload = dict(current)
        payload["lifecycle"] = "archived"
        payload["deleted"] = True
        payload["archived_at"] = utc_now_iso()
        payload["superseded_by"] = None
        payload.pop("version", None)
        payload.pop("filename", None)
        return self.append_link(slug, payload, link_id=link_id)

    def _normalize_link_payload(self, slug: str, payload: dict[str, Any], *, link_id: str | None = None) -> dict[str, Any]:
        data = dict(payload)
        company_slug, company_name = _resolve_company(data.get("company_slug"), data.get("company_name"))
        if not company_slug:
            raise ValueError("company_slug or company_name is required")
        relationship = _normalize_text(data.get("relationship"))
        role_title = _normalize_text(data.get("role_title")) or relationship
        notes = _normalize_text(data.get("notes")) or _normalize_text(data.get("rationale"))

        link_id = _normalize_text(link_id or data.get("link_id"))
        if not link_id:
            signature_seed = "|".join([
                slug,
                company_slug,
                _normalize_text(role_title) or "",
                _normalize_text(data.get("link_type")) or "current",
                _normalize_text(data.get("start_date")) or "",
                _normalize_text(data.get("end_date")) or "",
            ])
            link_id = safe_slug(signature_seed) or f"{slug}-{company_slug}-{version_stamp()}"
        confidence = data.get("confidence")
        try:
            confidence = int(confidence) if confidence is not None and str(confidence).strip() else None
        except (TypeError, ValueError):
            confidence = None

        evidence = [str(item).strip() for item in normalize_list(data.get("evidence")) if str(item).strip()]
        link_type = _normalize_text(data.get("link_type")) or "current"
        link_type = link_type.lower()
        if link_type not in _ALLOWED_LINK_TYPES:
            link_type = "current"

        source_timestamp = _normalize_text(data.get("source_timestamp")) or utc_now_iso()
        source_signature = _normalize_text(data.get("source_signature"))
        if not source_signature:
            signature_seed = "|".join([
                slug,
                company_slug,
                link_type,
                _normalize_text(role_title) or "",
                _normalize_text(data.get("start_date")) or "",
                _normalize_text(data.get("end_date")) or "",
                _normalize_text(notes) or "",
                source_timestamp,
            ])
            source_signature = _event_signature(signature_seed)

        event = AlumniCompanyLink(
            link_id=link_id,
            alumni_slug=slug,
            company_slug=company_slug,
            company_name=company_name,
            relationship=relationship,
            role_title=role_title,
            notes=notes,
            start_date=_normalize_text(data.get("start_date")),
            end_date=_normalize_text(data.get("end_date")),
            link_type=link_type,  # type: ignore[arg-type]
            confidence=confidence,
            evidence=evidence,
            rationale=_normalize_text(data.get("rationale")),
            source_type=_normalize_text(data.get("source_type")) or "manual",
            source_label=_normalize_text(data.get("source_label")),
            source_timestamp=source_timestamp,
            source_signature=source_signature,
            lifecycle=str(_normalize_text(data.get("lifecycle")) or "active"),
            deleted=bool(data.get("deleted", False)),
            superseded_by=_normalize_text(data.get("superseded_by")),
            recorded_at=_normalize_text(data.get("recorded_at")) or utc_now_iso(),
            last_updated=utc_now_iso(),
            archived_at=_normalize_text(data.get("archived_at")),
        )
        if event.deleted and event.lifecycle != "archived":
            event.lifecycle = "archived"
            event.archived_at = event.archived_at or utc_now_iso()
        return event.model_dump(exclude_none=True)

    def backfill_legacy_alumni(self) -> dict[str, int]:
        """Deterministically backfill alumni files from legacy employer alumni facts."""
        self._ensure_loaded()
        employers_dir = Path(os.environ.get("EMPLOYERS_DIR", str(_default_employers_dir())))
        if not employers_dir.exists():
            return {"employers_scanned": 0, "facts_scanned": 0, "profiles_written": 0, "links_written": 0, "facts_migrated": 0}

        manifest_signatures = _manifest_signature_set()
        stats = {
            "employers_scanned": 0,
            "facts_scanned": 0,
            "profiles_written": 0,
            "links_written": 0,
            "facts_migrated": 0,
        }
        existing_profiles = {slug: profile for slug, profile in self._profiles.items()}
        name_index = {_normalise_name_key(profile.get("full_name", "")): slug for slug, profile in existing_profiles.items() if profile.get("full_name")}

        for yaml_path in sorted(employers_dir.glob("*.yaml")):
            stats["employers_scanned"] += 1
            employer = read_yaml(yaml_path)
            if not isinstance(employer, dict):
                continue
            employer_slug = str(employer.get("slug") or yaml_path.stem).strip()
            employer_name = str(employer.get("employer_name") or employer_slug).strip()
            facts = employer.get("structured", {}).get("facts") if isinstance(employer.get("structured"), dict) else []
            if not isinstance(facts, list):
                continue
            for fact in facts:
                if not isinstance(fact, dict) or str(fact.get("type") or "") != "alumni":
                    continue
                stats["facts_scanned"] += 1
                payload = fact.get("data") if isinstance(fact.get("data"), dict) else fact
                inner = payload.get("data") if isinstance(payload.get("data"), dict) else payload
                if not isinstance(inner, dict):
                    continue

                full_name = _normalize_text(inner.get("full_name") or inner.get("student_name") or inner.get("name"))
                if not full_name:
                    continue

                source_signature = f"profile:{employer_slug}:{fact.get('slug') or safe_slug(full_name)}"
                if source_signature in manifest_signatures:
                    continue

                profile_slug = name_index.get(_normalise_name_key(full_name))
                if not profile_slug:
                    candidate = safe_slug(full_name)
                    profile_slug = candidate if candidate and candidate not in existing_profiles else f"{candidate}_{hashlib.sha1(full_name.encode('utf-8')).hexdigest()[:8]}"
                    name_index[_normalise_name_key(full_name)] = profile_slug

                current_company = _normalize_text(inner.get("current_company") or inner.get("next_employer") or inner.get("company") or employer_name)
                current_title = _normalize_text(inner.get("current_title") or inner.get("next_role") or inner.get("role"))
                school = _normalize_text(inner.get("graduation_school") or inner.get("school"))
                program = _normalize_text(inner.get("graduation_program") or inner.get("program"))
                year = inner.get("graduation_year") or inner.get("year")
                prior_company = _normalize_text(inner.get("prior_employer") or inner.get("former_employer"))
                prior_title = _normalize_text(inner.get("prior_role") or inner.get("former_role"))
                source_text = json.dumps(inner, ensure_ascii=False)
                evidence_hits: list[str] = []
                if re.search(r"available for mentoring|open to referrals|open to engagement|willing to mentor|available for guest lecture", source_text, re.I):
                    evidence_hits.append("explicit referral availability in source note")
                if re.search(r"alumni contact|alumni mentor", source_text, re.I):
                    evidence_hits.append("alumni contact/mentor explicitly mentioned")

                profile_payload = {
                    "slug": profile_slug,
                    "full_name": full_name,
                    "graduation_school": school,
                    "graduation_program": program,
                    "graduation_year": year,
                    "current_title": current_title,
                    "current_company": current_company,
                    "career_goals_domains": normalize_list(inner.get("career_goals_domains") or inner.get("mentor_for")),
                    "help_capacity": _normalize_text(inner.get("help_capacity")),
                    "can_refer": "yes" if evidence_hits else "maybe",
                    "can_refer_confidence": 90 if evidence_hits else 70,
                    "can_refer_evidence": evidence_hits,
                    "can_refer_rationale": _normalize_text(inner.get("rationale") or inner.get("details")),
                    "network_strength": _normalize_text(inner.get("network_strength")),
                    "mentoring_modes": normalize_list(inner.get("mentoring_modes")),
                    "communication_style": _normalize_text(inner.get("communication_style")),
                    "preferred_student_traits": normalize_list(inner.get("preferred_student_traits")),
                    "common_interests": normalize_list(inner.get("common_interests")),
                    "consent_for_referrals": True if evidence_hits else None,
                    "consent_scope_notes": _normalize_text(inner.get("consent_scope_notes")),
                    "source_type": "legacy_backfill",
                    "source_label": f"{employer_slug}:{fact.get('slug') or safe_slug(full_name)}",
                    "source_timestamp": _normalize_text(fact.get("timestamp") or inner.get("timestamp")) or utc_now_iso(),
                    "trace_id": _normalize_text(fact.get("trace_id")),
                    "lifecycle": "active",
                    "deleted": False,
                    "superseded_by": None,
                    "archived_at": None,
                    "last_confirmed_at": _normalize_text(fact.get("timestamp") or inner.get("timestamp")) or utc_now_iso(),
                    "last_updated": utc_now_iso(),
                }

                existing = existing_profiles.get(profile_slug)
                if existing:
                    merged = _normalize_profile_payload(profile_payload, existing=existing)
                else:
                    merged = _normalize_profile_payload(profile_payload)
                merged["slug"] = profile_slug
                merged["company_link_count"] = len(self.list_links(profile_slug))
                merged["completeness"] = _compute_completeness(merged, company_link_count=merged["company_link_count"])
                atomic_yaml_write(_profile_path(profile_slug), merged)
                self.invalidate()
                existing_profiles[profile_slug] = merged
                self._profiles[profile_slug] = merged
                stats["profiles_written"] += 1

                link_targets: list[tuple[str, str | None, str]] = []
                if current_company:
                    link_targets.append((current_company, current_title, "current"))
                if prior_company and prior_company != current_company:
                    link_targets.append((prior_company, prior_title, "former"))

                for company_name, role_title, link_type in link_targets:
                    company_slug, resolved_name = _resolve_company(company_name=company_name)
                    if not company_slug:
                        continue
                    link_signature = f"link:{profile_slug}:{employer_slug}:{fact.get('slug') or safe_slug(full_name)}:{company_slug}:{link_type}"
                    if link_signature in manifest_signatures:
                        continue
                    link_payload = {
                        "company_slug": company_slug,
                        "company_name": resolved_name,
                        "role_title": role_title,
                        "link_type": link_type,
                        "confidence": 90 if evidence_hits else 75,
                        "evidence": evidence_hits or [f"Backfilled from {employer_name} legacy alumni fact {fact.get('slug') or safe_slug(full_name)}"],
                        "rationale": _normalize_text(inner.get("details") or inner.get("value")),
                        "source_type": "legacy_backfill",
                        "source_label": f"{employer_slug}:{fact.get('slug') or safe_slug(full_name)}",
                        "source_timestamp": _normalize_text(fact.get("timestamp") or inner.get("timestamp")) or utc_now_iso(),
                        "source_signature": link_signature,
                    }
                    self.append_link(profile_slug, link_payload)
                    stats["links_written"] += 1
                    _record_manifest_signature(link_signature)
                    manifest_signatures.add(link_signature)
                _record_manifest_signature(source_signature)
                manifest_signatures.add(source_signature)
                stats["facts_migrated"] += 1

        self.invalidate()
        return stats

    def preview_from_notes(
        self,
        notes: str,
        *,
        source_label: str = "counsellor_note",
        source_type: str = "note",
        alumni_slug: str | None = None,
    ) -> dict[str, Any]:
        if not notes or not notes.strip():
            raise ValueError("notes are required")

        current_profile = self.get_alumni(alumni_slug) if alumni_slug else None
        current_links = self.list_links(alumni_slug) if alumni_slug else []

        system = _prompts["alumni_extraction"].format(
            school_name=SCHOOL_NAME,
            allowed_alumni_fields=", ".join(sorted([
                "full_name",
                "graduation_school",
                "graduation_program",
                "graduation_year",
                "current_title",
                "current_company",
                "career_goals_domains",
                "help_capacity",
                "can_refer",
                "can_refer_confidence",
                "can_refer_evidence",
                "can_refer_rationale",
                "network_strength",
                "mentoring_modes",
                "communication_style",
                "preferred_student_traits",
                "common_interests",
                "consent_for_referrals",
                "consent_scope_notes",
                "source_type",
                "source_label",
                "source_timestamp",
                "trace_id",
                "lifecycle",
                "deleted",
                "superseded_by",
                "archived_at",
                "last_confirmed_at",
            ])),
            allowed_alumni_link_fields=", ".join(sorted([
                "company_slug",
                "company_name",
                "role_title",
                "start_date",
                "end_date",
                "link_type",
                "confidence",
                "evidence",
                "rationale",
                "source_type",
                "source_label",
                "source_timestamp",
            ])),
        )
        profile_context = json.dumps(current_profile or {}, ensure_ascii=False, indent=2)
        link_context = json.dumps(current_links or [], ensure_ascii=False, indent=2)
        user = (
            f"MEETING NOTES:\n{notes.strip()}\n\n"
            f"CURRENT ALUMNI PROFILE (if editing existing alumni):\n{profile_context}\n\n"
            f"CURRENT COMPANY LINKS:\n{link_context}\n\n"
            f"SOURCE LABEL: {source_label}\n"
            f"SOURCE TYPE: {source_type}\n"
        )
        schema_hint = (
            "JSON object with summary_bullets, profile_proposals, company_link_proposals, "
            "and fit_triad. Each proposal includes value, confidence, evidence, and rationale."
        )
        result = llm_service.call_structured_json(
            operation="extract_alumni_preview",
            model=_llm_model(),
            system=system,
            user=user,
            schema_name="AlumniExtractionPreview",
            schema_hint=schema_hint,
            max_tokens=3000,
            timeout_seconds=settings.llm_timeout_seconds,
            trace_metadata={
                "feature": "extract_alumni_preview",
                "source_type": source_type,
                "source_label": source_label,
                "alumni_slug": alumni_slug,
                "input_chars_pre_trim": len(notes),
            },
            validator=AlumniExtractionPreview,
        )
        if isinstance(result, BaseModel):
            return result.model_dump()
        return result


def _llm_model() -> str:
    return llm_service.get_model_name()


def get_alumni_store() -> "AlumniEntityStore":
    return AlumniEntityStore()
