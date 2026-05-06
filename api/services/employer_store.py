# api/services/employer_store.py
"""Employer entity service — YAML loading and LLM context formatting.

Mirrors CareerProfileStore. One YAML per employer in knowledge/employers/.
Active employers (*.yaml) are injected into the LLM context when a career type
matches their 'tracks' list. Disabled employers (*.yaml.disabled) are excluded.

Usage:
    store = EmployerEntityStore()
    employers = store.list_employers()         # for admin endpoint
    block     = store.to_context_block("investment_banking")  # for LLM injection
    store.invalidate()                         # force reload on next access
"""

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from cfg import kb_cfg
from services.runtime_paths import knowledge_dir
from services.shared_yaml import (
    Singleton,
    atomic_yaml_write,
    fact_lifecycle,
    fact_payload,
    version_stamp,
)

logger = logging.getLogger(__name__)

# Required fields that must be present for completeness = "green"
_COMPLETENESS_REQUIRED: frozenset = frozenset(
    kb_cfg["employers"]["completeness_required"]
)

# Fields writable via commit-analysis (allowlist prevents hallucinated field writes)
ALLOWED_EMPLOYER_FIELDS: frozenset = frozenset(
    kb_cfg["employers"]["allowed_update_fields"]
)
_FACTS_PREVIEW_LIMIT = 6
_FACT_PREVIEW_CHARS = 120


def _default_employer_history_dir() -> Path:
    employers_dir = Path(os.environ.get("EMPLOYERS_DIR", str(_default_employers_dir())))
    return employers_dir.parent / "employers_history"


def as_list(value) -> list:
    """Normalize legacy scalar/list YAML fields into a list.

    Handles None, lists, tuples, and strings. Strips whitespace from strings.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        value = value.strip()
        return [value] if value else []
    return [value]


# Alias for compatibility
_as_list = as_list


def default_employers_dir() -> Path:
    """Resolve the default employers dir across local repo and Docker layouts."""
    return knowledge_dir("employers")


# Alias for compatibility
_default_employers_dir = default_employers_dir


def _history_dir() -> Path:
    return Path(
        os.environ.get("EMPLOYER_HISTORY_DIR", str(default_employers_dir().parent / "employers_history"))
    )


def compute_completeness(employer: dict) -> str:
    """Assess employer profile completeness.

    Returns 'green' if all required fields (from kb.yaml employers.completeness_required)
    are non-empty; else 'amber'. Used to flag incomplete profiles in the admin panel.
    """
    for field in _COMPLETENESS_REQUIRED:
        val = employer.get(field)
        if not val:
            return "amber"
        if isinstance(val, list) and len(val) == 0:
            return "amber"
        if isinstance(val, str) and not val.strip():
            return "amber"
    return "green"


# Alias for compatibility
_compute_completeness = compute_completeness


def employer_to_context_block(
    employer: dict, max_notes: int = None, max_process: int = None
) -> str:
    """Format a single employer dict as a structured context entry for LLM injection.

    Truncates long notes and process fields to fit into context windows.

    Args:
        employer: employer profile dict
        max_notes: max chars for notes field (defaults to kb.yaml context_block.max_notes_chars)
        max_process: max chars for application_process (defaults to kb.yaml context_block.max_process_chars)

    Returns:
        Formatted text block ready for LLM injection.
    """
    if max_notes is None:
        max_notes = kb_cfg["employers"]["context_block"]["max_notes_chars"]
    if max_process is None:
        max_process = kb_cfg["employers"]["context_block"]["max_process_chars"]

    name = employer.get("employer_name", "Unknown")
    ep = employer.get("ep_requirement") or "Not specified"
    seasons = ", ".join(employer.get("intake_seasons") or []) or "Not specified"
    headcount = employer.get("singapore_headcount_estimate") or "Not specified"
    process = str(employer.get("application_process") or "").strip()
    if len(process) > max_process:
        process = process[:max_process] + "..."
    notes = str(employer.get("notes") or "").strip()
    if len(notes) > max_notes:
        notes = notes[:max_notes] + "..."
    facts = _format_structured_facts(employer.get("structured") or {})

    lines = [
        f"  {name}:",
        f"    EP requirement: {ep}",
        f"    Intake seasons: {seasons}",
        f"    SG headcount: {headcount}",
    ]
    if process:
        lines.append(f"    Application: {process}")
    if notes:
        lines.append(f"    Notes: {notes}")
    if facts:
        lines.append("    Structured facts:")
        lines.extend(f"      - {fact}" for fact in facts)
    return "\n".join(lines)


def _fact_is_active(fact: object) -> bool:
    return fact_lifecycle(fact) == "active"


def _fact_key_field(fact: dict) -> str:
    """Return the most human-readable identifying field value for a fact, based on its type."""
    payload = fact_payload(fact)
    fact_type = str(fact.get("type") or payload.get("type") or "").strip()
    candidates: list[str] = []
    if fact_type == "alumni":
        candidates = ["full_name", "name"]
    elif fact_type == "timeline_phase":
        candidates = ["phase_name", "name"]
    elif fact_type == "interview_stage":
        candidates = ["name", "phase_name"]
    elif fact_type == "compensation":
        candidates = ["role_level", "phase_name"]
    elif fact_type == "skill_requirement":
        candidates = ["phase_name", "name"]

    for key in candidates:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key in ("value", "summary", "description", "notes"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _format_structured_fact(fact: object) -> str:
    """Render a single structured fact as a truncated pipe-delimited preview string for LLM context blocks."""
    if not isinstance(fact, dict):
        return str(fact)

    slug = str(fact.get("slug") or fact_payload(fact).get("slug") or "").strip()
    fact_type = str(
        fact.get("type") or fact_payload(fact).get("type") or "fact"
    ).strip()
    key_field = _fact_key_field(fact)
    preview_parts = [fact_type]
    if slug:
        preview_parts.append(slug)
    if key_field:
        preview_parts.append(key_field)
    else:
        preview_parts.append("(unnamed)")

    payload = fact_payload(fact)
    detail_candidates = [
        payload.get("value"),
        payload.get("notes"),
        payload.get("reason"),
        payload.get("description"),
    ]
    detail = next(
        (
            str(value).strip()
            for value in detail_candidates
            if isinstance(value, str) and str(value).strip()
        ),
        "",
    )
    if detail and detail not in preview_parts:
        preview_parts.append(detail)

    preview = " | ".join(preview_parts)
    if len(preview) > _FACT_PREVIEW_CHARS:
        preview = preview[: _FACT_PREVIEW_CHARS - 1].rstrip() + "…"
    return preview


def _format_structured_facts(structured: dict) -> list[str]:
    """Return preview strings for active structured facts, capped at _FACTS_PREVIEW_LIMIT with a trailing count line."""
    facts = structured.get("facts") if isinstance(structured, dict) else None
    if not isinstance(facts, list) or not facts:
        return []
    active_facts = [fact for fact in facts if _fact_is_active(fact)]
    lines = [
        _format_structured_fact(fact) for fact in active_facts[:_FACTS_PREVIEW_LIMIT]
    ]
    remaining = len(active_facts) - len(lines)
    if remaining > 0:
        lines.append(f"... and {remaining} more fact(s)")
    return lines


def _normalized_terms(text: str) -> set[str]:
    """Return lowercase alphanumeric tokens for lightweight name matching."""
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _employer_matches_query(employer: dict, query_text: str) -> bool:
    """Return True when the query explicitly mentions the employer by name/slug.

    Also matches when query terms appear in the employer's notes or
    application_process fields — e.g. "NGO" in query matches WWF's notes
    containing "NGO" even if "WWF" is not mentioned by name.
    """
    if not query_text or not query_text.strip():
        return False

    query_lower = query_text.lower()
    query_terms = _normalized_terms(query_text)
    name = str(employer.get("employer_name") or "").strip().lower()
    slug = str(employer.get("slug") or "").strip().lower()

    if name and name in query_lower:
        return True
    if slug and slug.replace("_", " ") in query_lower:
        return True

    employer_terms = _normalized_terms(name) | _normalized_terms(slug.replace("_", " "))
    if not employer_terms:
        return False

    # Acronym-style employers like DBS or UBS are represented as a single token.
    if len(employer_terms) == 1:
        return next(iter(employer_terms)) in query_terms

    # For multi-word names, require all salient terms to appear somewhere in the query.
    if employer_terms.issubset(query_terms):
        return True

    # Broadened: also match when query terms appear in notes or application_process.
    # This catches sector-level queries like "NGO" matching WWF's notes.
    for field in ("notes", "application_process"):
        field_text = str(employer.get(field) or "").lower()
        field_terms = _normalized_terms(field_text)
        if not field_terms:
            continue
        # Require at least 2 query terms to appear in the field text (reduces false positives).
        matching = query_terms & field_terms
        if len(matching) >= 2:
            return True
        # Single-term match is enough for acronyms.
        if len(employer_terms) == 1 and next(iter(employer_terms)) in matching:
            return True

    return False


class EmployerEntityStore(Singleton):
    """Singleton that loads employer entity YAMLs from knowledge/employers/.

    Disabled employers (*.yaml.disabled) are excluded from active lists.
    Completeness is computed at load time from required field presence.

    Dependency graph: no external services (no embedder, no Qdrant).

    Usage:
        store = EmployerEntityStore()
        store.list_employers()                       # all active employers
        store.get_employer("goldman_sachs")          # single employer or None
        store.to_context_block("investment_banking") # LLM context string
        store.invalidate()                           # reload on next access
    """

    _instance = None

    def _init_singleton(self) -> None:
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._employers: dict[str, dict] = {}  # slug → employer dict (active only)
        self._load_employers()
        self._loaded = True

    def _load_employers(self) -> None:
        employers_dir = Path(
            os.environ.get(
                "EMPLOYERS_DIR",
                str(_default_employers_dir()),
            )
        )
        if not employers_dir.exists():
            logger.warning(
                "Employers directory not found: %s — employer injection disabled",
                employers_dir,
            )
            return

        yaml_files = sorted(employers_dir.glob("*.yaml"))
        loaded = 0
        for yaml_path in yaml_files:
            slug = yaml_path.stem
            try:
                with open(yaml_path, encoding="utf-8") as f:
                    employer = yaml.safe_load(f)
                if not isinstance(employer, dict):
                    logger.warning(
                        "Employer %s: not a valid YAML mapping — skipping",
                        yaml_path.name,
                    )
                    continue
                if not employer.get("employer_name"):
                    logger.warning(
                        "Employer %s: missing employer_name — skipping", yaml_path.name
                    )
                    continue
                employer["tracks"] = _as_list(employer.get("tracks"))
                employer["intake_seasons"] = _as_list(employer.get("intake_seasons"))
                employer["slug"] = slug
                employer["completeness"] = _compute_completeness(employer)
                self._employers[slug] = employer
                loaded += 1
                logger.info("Loaded employer: %s (%s)", slug, employer["employer_name"])
            except yaml.YAMLError as exc:
                logger.warning(
                    "Employer %s: YAML parse error — skipping: %s", yaml_path.name, exc
                )
            except Exception as exc:
                logger.warning(
                    "Employer %s: failed to load — skipping: %s", yaml_path.name, exc
                )

        logger.info(
            "EmployerEntityStore: loaded %d/%d employers from %s",
            loaded,
            len(yaml_files),
            employers_dir,
        )

    def get_employer(self, slug: Optional[str]) -> Optional[dict]:
        """Return the employer dict for a slug, or None if not found."""
        if not slug:
            return None
        self._ensure_loaded()
        return self._employers.get(slug)

    def list_employers(self) -> list[dict]:
        """Return all active employer dicts (for admin endpoint)."""
        self._ensure_loaded()
        return list(self._employers.values())

    def list_history(self, slug: str) -> list[dict]:
        """Return saved employer history snapshots, newest first."""
        history_dir = _history_dir() / slug
        if not history_dir.exists():
            return []
        entries: list[dict] = []
        for yaml_path in sorted(history_dir.glob("*.yaml"), reverse=True):
            version = yaml_path.stem
            entries.append(
                {
                    "version": version,
                    "recorded_at": version,
                    "filename": yaml_path.name,
                }
            )
        return entries

    def snapshot_history(self, slug: str, payload: dict) -> str:
        """Persist the current employer YAML into the history directory."""
        version = version_stamp()
        history_path = _history_dir() / slug / f"{version}.yaml"
        atomic_yaml_write(history_path, payload)
        return version

    def to_context_block(
        self,
        active_career_type: Optional[str] = None,
        query_text: Optional[str] = None,
        profile_top_employers: Optional[list[str]] = None,
    ) -> str:
        """Build the employer context block for LLM injection.

        Filters to employers whose 'tracks' list includes active_career_type.
        If query_text explicitly mentions an employer, include that employer even
        when the active track is absent or different. This preserves relevance
        for queries like "Tell me about DBS" without globally injecting every
        employer into general chat.

        If profile_top_employers is provided (from the career profile's
        top_employers_smu), also inject employers whose name is a case-insensitive
        substring match. This bridges the gap between career profiles that list
        employers and employer entities that may not share the exact track tag.

        Returns empty string if no employers match (safe to skip injection).

        Token budget: ~6 lines per employer × 12 chars/line ≈ 72 tokens per employer.
        At 15 employers per track, that's ~1080 tokens — acceptable at pilot scale.
        See TODOS.md: "Employer context token budget" for >20 employers per track.
        """
        self._ensure_loaded()
        employers = list(self._employers.values())
        selected: list[dict] = []
        seen_slugs: set[str] = set()

        if active_career_type:
            for employer in employers:
                if active_career_type in _as_list(employer.get("tracks")):
                    selected.append(employer)
                    seen_slugs.add(employer.get("slug", ""))

        # Inject employers listed in the career profile's top_employers_smu.
        # Case-insensitive substring match catches variants like "WWF" → "WWF Singapore".
        if profile_top_employers:
            for employer in employers:
                slug = employer.get("slug", "")
                if slug in seen_slugs:
                    continue
                emp_name = str(employer.get("employer_name") or "").strip().lower()
                for top_name in profile_top_employers:
                    top_lower = top_name.strip().lower()
                    if top_lower and (top_lower in emp_name or emp_name in top_lower):
                        selected.append(employer)
                        seen_slugs.add(slug)
                        break

        if query_text:
            for employer in employers:
                slug = employer.get("slug", "")
                if slug in seen_slugs:
                    continue
                if _employer_matches_query(employer, query_text):
                    selected.append(employer)
                    seen_slugs.add(slug)

        employers = selected
        if not employers:
            return ""

        lines = [
            "=== EMPLOYER FACTS (authoritative structured data — supersedes KB chunks) ==="
        ]
        for emp in employers:
            lines.append(employer_to_context_block(emp))
        lines.append("=== END EMPLOYER FACTS ===")
        return "\n".join(lines)

    def append_source_document(self, slug: str, filename: str, raw_text: str) -> bool:
        """Append a parsed document's text to the employer's source_documents list.

        Reads the YAML, appends the entry, writes back, then invalidates the cache.
        Returns False if the employer file does not exist.
        """
        employers_dir = Path(
            os.environ.get("EMPLOYERS_DIR", str(_default_employers_dir()))
        )
        yaml_path = employers_dir / f"{slug}.yaml"
        if not yaml_path.exists():
            logger.warning("append_source_document: %s not found", yaml_path)
            return False

        with open(yaml_path, encoding="utf-8") as f:
            employer = yaml.safe_load(f)
        if not isinstance(employer, dict):
            return False

        docs = employer.get("source_documents") or []
        docs.append(
            {
                "filename": filename,
                "raw_text": raw_text,
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        employer["source_documents"] = docs

        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(
                employer,
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )

        self.invalidate()
        logger.info(
            "append_source_document: added %r to %s (%d docs total)",
            filename,
            slug,
            len(docs),
        )
        return True

    def invalidate(self) -> None:
        """Reset loaded flag so employers are reloaded on next access."""
        self._loaded = False


def get_employer_store() -> "EmployerEntityStore":
    """FastAPI dependency — returns the EmployerEntityStore singleton."""
    return EmployerEntityStore()
