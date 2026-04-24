"""Fact loading, filtering, and grouping for the KB query surface."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml

from models import Fact
from services.career_profiles import _default_profiles_dir
from services.employer_store import _default_employers_dir

logger = logging.getLogger(__name__)

_FACT_TYPE_ALIASES = {
    "compensation_signal": "compensation",
}


def _default_fact_sources() -> list[tuple[str, Path, str]]:
    """Return the entity kinds, directories, and audit URL templates to scan."""
    employers_dir = Path(os.environ.get("EMPLOYERS_DIR", str(_default_employers_dir())))
    profiles_dir = Path(os.environ.get("CAREER_PROFILES_DIR", str(_default_profiles_dir())))
    return [
        ("employer", employers_dir, "/api/kb/employers/{slug}"),
        ("career_profile", profiles_dir, "/api/kb/career-profiles/{slug}"),
    ]


def _normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _yaml_mapping(path: Path) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
    except Exception as exc:
        logger.warning("Skipping unreadable fact source %s: %s", path, exc)
        return None
    if not isinstance(loaded, dict):
        return None
    return loaded


def _leaf_strings(value: object) -> list[str]:
    """Recursively collect all leaf scalar values from an arbitrary nested structure as strings."""
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(_leaf_strings(item))
        return items
    if isinstance(value, dict):
        items: list[str] = []
        for nested in value.values():
            items.extend(_leaf_strings(nested))
        return items
    return [str(value).strip()] if value is not None and str(value).strip() else []


def _collect_matching_values(payload: object, key_names: set[str]) -> list[object]:
    """Walk a nested payload and return all values whose key matches one of the given names (case-insensitive)."""
    values: list[object] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).lower() in key_names:
                values.append(value)
            if isinstance(value, (dict, list)):
                values.extend(_collect_matching_values(value, key_names))
    elif isinstance(payload, list):
        for item in payload:
            values.extend(_collect_matching_values(item, key_names))
    return values


def _payload_for_fact(raw_fact: dict[str, Any]) -> dict[str, Any]:
    """Unwrap the innermost data dict from a raw fact, handling single and double nesting."""
    payload = raw_fact.get("data")
    if not isinstance(payload, dict):
        return {}
    nested = payload.get("data")
    if isinstance(nested, dict):
        return nested
    return payload


def _build_fact(
    raw_fact: dict[str, Any],
    entity_kind: str,
    entity_slug: str,
    audit_url_template: str,
) -> Fact | None:
    """Construct a typed Fact from a raw YAML dict, returning None if required fields are missing or invalid."""
    payload = raw_fact.get("data")
    payload_map = payload if isinstance(payload, dict) else {}

    fact_type = str(raw_fact.get("type") or payload_map.get("type") or "").strip()
    fact_type = _FACT_TYPE_ALIASES.get(fact_type, fact_type)
    timestamp = str(raw_fact.get("timestamp") or payload_map.get("timestamp") or "").strip()
    source = str(raw_fact.get("source") or payload_map.get("source") or "").strip()

    if not fact_type or not timestamp or not source:
        return None

    try:
        confidence = int(raw_fact.get("confidence") or payload_map.get("confidence"))
    except (TypeError, ValueError):
        return None

    lifecycle = str(raw_fact.get("lifecycle") or payload_map.get("lifecycle") or "").strip().lower()
    if lifecycle not in {"active", "superseded", "archived"}:
        lifecycle = "superseded" if bool(raw_fact.get("deleted") or payload_map.get("deleted")) else "active"

    raw_data = _payload_for_fact(raw_fact)
    if not isinstance(raw_data, dict):
        raw_data = {}

    fact_kwargs = {
        "slug": str(raw_fact.get("slug") or payload_map.get("slug") or "").strip(),
        "type": fact_type,
        "timestamp": timestamp,
        "source": source,
        "confidence": confidence,
        "trace_id": raw_fact.get("trace_id") or payload_map.get("trace_id"),
        "lifecycle": lifecycle,
        "deleted": bool(raw_fact.get("deleted") or payload_map.get("deleted", False)),
        "last_updated": raw_fact.get("last_updated") or payload_map.get("last_updated"),
        "source_timestamp": raw_fact.get("source_timestamp") or payload_map.get("source_timestamp"),
        "source_label": str(raw_fact.get("source_label") or payload_map.get("source_label") or entity_slug).strip() or entity_slug,
        "source_type": str(raw_fact.get("source_type") or payload_map.get("source_type") or entity_kind).strip() or entity_kind,
        "superseded_by": raw_fact.get("superseded_by") or payload_map.get("superseded_by"),
        "audit_url": str(raw_fact.get("audit_url") or payload_map.get("audit_url") or audit_url_template.format(slug=entity_slug)).strip(),
        "data": raw_data,
    }
    if not fact_kwargs["slug"]:
        return None

    try:
        return Fact(**fact_kwargs)
    except Exception as exc:
        logger.warning(
            "Skipping invalid fact %s/%s (%s): %s",
            entity_kind,
            entity_slug,
            fact_kwargs["slug"],
            exc,
        )
        return None


def _read_fact_source(entity_kind: str, directory: Path, audit_url_template: str) -> list[Fact]:
    """Load all valid facts from the structured.facts list in every YAML file under directory."""
    if not directory.exists():
        return []

    facts: list[Fact] = []
    for yaml_path in sorted(directory.glob("*.yaml")):
        entity_slug = yaml_path.stem
        entity = _yaml_mapping(yaml_path)
        if not entity:
            continue
        structured = entity.get("structured")
        if not isinstance(structured, dict):
            continue
        raw_facts = structured.get("facts")
        if not isinstance(raw_facts, list):
            continue
        for raw_fact in raw_facts:
            if not isinstance(raw_fact, dict):
                continue
            fact = _build_fact(raw_fact, entity_kind, entity_slug, audit_url_template)
            if fact is not None:
                facts.append(fact)
    return facts


def _fact_is_active(fact: Fact) -> bool:
    return fact.lifecycle == "active" and not fact.deleted


def _fact_string_matches(fact: Fact, query: str, *, include_nested: bool = False) -> bool:
    """Return True if the normalized query appears in any of the fact's string fields (and optionally its data payload)."""
    needle = _normalize_text(query)
    if not needle:
        return True

    haystacks = [
        fact.slug,
        fact.type,
        fact.source,
        fact.source_label or "",
        fact.source_type or "",
        fact.audit_url or "",
    ]
    if include_nested:
        haystacks.extend(_leaf_strings(fact.data))

    return any(needle in _normalize_text(value) for value in haystacks if value)


def _fact_matches_filters(
    fact: Fact,
    *,
    type: str | None = None,
    employer: str | None = None,
    school: str | None = None,
    graduation_year: int | str | None = None,
    confidence__gte: int | None = None,
    source: str | None = None,
    include_deleted: bool = False,
    lifecycle: str | None = None,
    trace_id: str | None = None,
    source_type: str | None = None,
    source_label: str | None = None,
    has_audit_url: bool | None = None,
) -> bool:
    """Return True if the fact satisfies all provided filter criteria; None filters are skipped."""
    if not include_deleted and not _fact_is_active(fact):
        return False
    if type and fact.type != type:
        return False
    if employer and not _fact_string_matches(fact, employer, include_nested=True):
        return False
    if school:
        school_values = _collect_matching_values(
            fact.data,
            {"school", "school_name", "graduation_school", "alma_mater", "institution"},
        )
        if not any(_normalize_text(value) == _normalize_text(school) or _normalize_text(school) in _normalize_text(value) for value in school_values):
            return False
    if graduation_year is not None:
        year_values = _collect_matching_values(fact.data, {"graduation_year", "year", "class_year", "cohort_year"})
        desired = _normalize_text(graduation_year)
        if not any(_normalize_text(value) == desired for value in year_values):
            return False
    if confidence__gte is not None and fact.confidence < confidence__gte:
        return False
    if source and fact.source != source:
        return False
    if lifecycle and fact.lifecycle != lifecycle:
        return False
    if trace_id and fact.trace_id != trace_id:
        return False
    if source_type and fact.source_type != source_type:
        return False
    if source_label and fact.source_label != source_label:
        return False
    if has_audit_url is True and not fact.audit_url:
        return False
    if has_audit_url is False and fact.audit_url:
        return False
    return True


def list_facts(
    *,
    type: str | None = None,
    employer: str | None = None,
    school: str | None = None,
    graduation_year: int | str | None = None,
    confidence__gte: int | None = None,
    source: str | None = None,
    include_deleted: bool = False,
    lifecycle: str | None = None,
    trace_id: str | None = None,
    source_type: str | None = None,
    source_label: str | None = None,
    has_audit_url: bool | None = None,
) -> list[Fact]:
    """Load and filter facts from employer and career-profile YAML sources."""
    facts: list[Fact] = []
    for entity_kind, directory, audit_url_template in _default_fact_sources():
        facts.extend(_read_fact_source(entity_kind, directory, audit_url_template))

    filtered = [
        fact
        for fact in facts
        if _fact_matches_filters(
            fact,
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
    ]
    filtered.sort(key=lambda fact: (fact.timestamp, fact.slug), reverse=True)
    return filtered


def group_facts(facts: list[Fact], by: str) -> dict[str, list[Fact]]:
    """Group facts by entity slug or fact type."""
    groups: dict[str, list[Fact]] = {}
    for fact in facts:
        if by == "type":
            key = fact.type
        else:
            key = fact.source_label or fact.slug
        groups.setdefault(key, []).append(fact)

    for key, grouped in groups.items():
        grouped.sort(key=lambda fact: (fact.timestamp, fact.slug), reverse=True)

    return dict(sorted(groups.items(), key=lambda item: item[0]))
