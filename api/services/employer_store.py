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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# Required fields that must be present for completeness = "green"
_COMPLETENESS_REQUIRED: frozenset = frozenset([
    "employer_name",
    "tracks",
    "ep_requirement",
    "intake_seasons",
])

# Fields writable via commit-analysis (allowlist prevents hallucinated field writes)
ALLOWED_EMPLOYER_FIELDS: frozenset = frozenset([
    "ep_requirement",
    "intake_seasons",
    "singapore_headcount_estimate",
    "application_process",
    "counsellor_contact",
    "notes",
])


def _compute_completeness(employer: dict) -> str:
    """Return 'green' if all required fields are non-empty, else 'amber'."""
    for field in _COMPLETENESS_REQUIRED:
        val = employer.get(field)
        if not val:
            return "amber"
        if isinstance(val, list) and len(val) == 0:
            return "amber"
        if isinstance(val, str) and not val.strip():
            return "amber"
    return "green"


def employer_to_context_block(employer: dict, max_notes: int = 150, max_process: int = 100) -> str:
    """Format a single employer dict as a structured context entry for LLM injection."""
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
    return "\n".join(lines)


class EmployerEntityStore:
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

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._employers: dict[str, dict] = {}   # slug → employer dict (active only)
        self._load_employers()
        self._loaded = True

    def _load_employers(self) -> None:
        employers_dir = Path(os.environ.get(
            "EMPLOYERS_DIR",
            str(Path(__file__).parent.parent.parent / "knowledge" / "employers"),
        ))
        if not employers_dir.exists():
            logger.warning(
                "Employers directory not found: %s — employer injection disabled", employers_dir
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
                        "Employer %s: not a valid YAML mapping — skipping", yaml_path.name
                    )
                    continue
                if not employer.get("employer_name"):
                    logger.warning(
                        "Employer %s: missing employer_name — skipping", yaml_path.name
                    )
                    continue
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
            loaded, len(yaml_files), employers_dir,
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

    def to_context_block(self, active_career_type: Optional[str] = None) -> str:
        """Build the employer context block for LLM injection.

        Filters to employers whose 'tracks' list includes active_career_type.
        If active_career_type is None, includes all active employers.
        Returns empty string if no employers match (safe to skip injection).

        Token budget: ~6 lines per employer × 12 chars/line ≈ 72 tokens per employer.
        At 15 employers per track, that's ~1080 tokens — acceptable at pilot scale.
        See TODOS.md: "Employer context token budget" for >20 employers per track.
        """
        self._ensure_loaded()
        employers = list(self._employers.values())
        if active_career_type:
            employers = [
                e for e in employers
                if active_career_type in (e.get("tracks") or [])
            ]
        if not employers:
            return ""

        lines = ["=== EMPLOYER FACTS (authoritative structured data — supersedes KB chunks) ==="]
        for emp in employers:
            lines.append(employer_to_context_block(emp))
        lines.append("=== END EMPLOYER FACTS ===")
        return "\n".join(lines)

    def invalidate(self) -> None:
        """Reset loaded flag so employers are reloaded on next access."""
        self._loaded = False


def get_employer_store() -> "EmployerEntityStore":
    """FastAPI dependency — returns the EmployerEntityStore singleton."""
    return EmployerEntityStore()
