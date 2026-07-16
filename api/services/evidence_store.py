"""Evidence store — file-backed YAML records under ``knowledge/evidence/``.

One YAML file per evidence record, keyed by a deterministic ``evidence_id``.
See ``docs/ontology/ONTOLOGY-DESIGN.md`` §1.3 (Evidence model), §2 (storage
layout), and §3 (identifier strategy).
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from models_ontology import Evidence, EvidenceLocator, SupportType
from services.runtime_paths import default_ontology_evidence_dir
from services.shared_yaml import Singleton, atomic_yaml_write, read_yaml

logger = logging.getLogger(__name__)


def _evidence_dir() -> Path:
    """Resolve the evidence directory live from the environment on every call.

    Not cached on the singleton instance — mirrors
    ``services.source_ledger._ledger_dir()`` so tests can monkeypatch
    ``ONTOLOGY_EVIDENCE_DIR`` per-test via the autouse ``reset_ontology_stores``
    fixture in ``api/tests/conftest.py``.
    """
    return Path(
        os.environ.get("ONTOLOGY_EVIDENCE_DIR", str(default_ontology_evidence_dir()))
    )


def _evidence_path(evidence_id: str) -> Path:
    return _evidence_dir() / f"{evidence_id}.yaml"


def _compute_evidence_id(
    source_id: str, excerpt: str, locator: EvidenceLocator | None
) -> str:
    """Deterministic id: evidence-{sha1(source_id|character_start|character_end|excerpt)[:16]}.

    ``character_start``/``character_end`` come from ``locator`` when present;
    absent locator (or absent offset fields on it) contribute empty-string
    placeholders to the hash input, so the id is still fully deterministic.
    """
    character_start = ""
    character_end = ""
    if locator is not None:
        if locator.character_start is not None:
            character_start = str(locator.character_start)
        if locator.character_end is not None:
            character_end = str(locator.character_end)
    seed = f"{source_id}|{character_start}|{character_end}|{excerpt}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]
    return f"evidence-{digest}"


def _load_evidence_file(path: Path) -> Evidence | None:
    """Parse a single evidence YAML file, returning ``None`` (and logging) on any failure.

    Defensive pattern mirrors ``services.source_ledger._load_yaml``: a corrupt
    YAML file or a record that fails Pydantic validation must not crash a
    directory scan, it should just be skipped.
    """
    try:
        payload = read_yaml(path)
    except Exception:
        logger.warning("Skipping unreadable evidence file: %s", path, exc_info=True)
        return None
    if not isinstance(payload, dict):
        return None
    try:
        return Evidence.model_validate(payload)
    except Exception:
        logger.warning("Skipping invalid evidence record: %s", path, exc_info=True)
        return None


class EvidenceStore(Singleton):
    """Singleton, file-backed store for ``Evidence`` records (one YAML file per record)."""

    _instance = None
    _lock = Lock()

    def _init_singleton(self) -> None:
        # Stateless: every operation re-resolves the directory and hits the
        # filesystem directly, so there is no in-memory cache to initialize.
        pass

    def create_evidence(
        self,
        source_id: str,
        excerpt: str,
        support_type: SupportType,
        extraction_confidence: float,
        *,
        locator: EvidenceLocator | None = None,
        trace_id: str | None = None,
    ) -> Evidence:
        """Create (or idempotently return) the Evidence record for this source excerpt.

        Re-running extraction over the same source text with the same locator
        offsets and excerpt must not create a duplicate file: the evidence_id
        is deterministic, and if a file for it already exists we return the
        existing parsed record unchanged rather than rewriting it.
        """
        resolved_locator = locator if locator is not None else EvidenceLocator()
        evidence_id = _compute_evidence_id(source_id, excerpt, resolved_locator)
        path = _evidence_path(evidence_id)

        if path.exists():
            existing = _load_evidence_file(path)
            if existing is not None:
                return existing
            # A file with this id exists but is corrupt/unreadable — fall
            # through and overwrite it with a freshly validated record.

        evidence = Evidence(
            evidence_id=evidence_id,
            source_id=source_id,
            excerpt=excerpt,
            locator=resolved_locator,
            support_type=support_type,
            extraction_confidence=extraction_confidence,
            created_at=datetime.now(timezone.utc),
            trace_id=trace_id,
        )
        atomic_yaml_write(path, evidence.model_dump(mode="json"))
        return evidence

    def get_evidence(self, evidence_id: str) -> Evidence | None:
        if not evidence_id:
            return None
        return _load_evidence_file(_evidence_path(evidence_id))

    def list_evidence(self, source_id: str | None = None) -> list[Evidence]:
        """Directory scan, optionally filtered to a given source_id.

        Files that fail to parse or fail Pydantic validation are skipped
        (and logged) rather than raising.
        """
        directory = _evidence_dir()
        if not directory.exists():
            return []
        records: list[Evidence] = []
        for yaml_path in sorted(directory.glob("*.yaml")):
            evidence = _load_evidence_file(yaml_path)
            if evidence is None:
                continue
            if source_id is not None and evidence.source_id != source_id:
                continue
            records.append(evidence)
        return records


def get_evidence_store() -> EvidenceStore:
    return EvidenceStore()
