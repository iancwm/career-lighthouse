"""Tests for the evidence store (api/services/evidence_store.py).

Isolation note: the autouse ``reset_ontology_stores`` fixture in
``api/tests/conftest.py`` points ``ONTOLOGY_EVIDENCE_DIR`` at a fresh
``tmp_path`` for every test and resets ``EvidenceStore._instance`` before and
after each test, so no per-test setup is needed here beyond that fixture
already being autouse.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def _evidence_dir() -> Path:
    return Path(os.environ["ONTOLOGY_EVIDENCE_DIR"])


def test_create_evidence_writes_file_and_roundtrips_through_get_evidence():
    from models_ontology import EvidenceLocator
    from services.evidence_store import EvidenceStore

    store = EvidenceStore()
    evidence = store.create_evidence(
        source_id="goldman-singapore-guide.txt",
        excerpt="Applications open in September for the summer analyst programme.",
        support_type="directly_supports",
        extraction_confidence=0.9,
        locator=EvidenceLocator(character_start=100, character_end=168),
        trace_id="trace-abc",
    )

    assert evidence.evidence_id.startswith("evidence-")
    path = _evidence_dir() / f"{evidence.evidence_id}.yaml"
    assert path.exists()

    fetched = store.get_evidence(evidence.evidence_id)
    assert fetched is not None
    assert fetched.evidence_id == evidence.evidence_id
    assert fetched.source_id == "goldman-singapore-guide.txt"
    assert fetched.excerpt == evidence.excerpt
    assert fetched.support_type == "directly_supports"
    assert fetched.extraction_confidence == pytest.approx(0.9)
    assert fetched.locator.character_start == 100
    assert fetched.locator.character_end == 168
    assert fetched.trace_id == "trace-abc"
    assert fetched.created_at is not None


def test_evidence_id_is_deterministic_and_create_is_idempotent():
    from models_ontology import EvidenceLocator
    from services.evidence_store import EvidenceStore

    store = EvidenceStore()
    kwargs = dict(
        source_id="src-1",
        excerpt="Some excerpt text copied verbatim from the source.",
        support_type="directly_supports",
        extraction_confidence=0.5,
        locator=EvidenceLocator(character_start=10, character_end=61),
    )

    first = store.create_evidence(**kwargs)
    second = store.create_evidence(**kwargs)

    assert first.evidence_id == second.evidence_id
    files = list(_evidence_dir().glob("*.yaml"))
    assert len(files) == 1


def test_different_excerpt_produces_different_evidence_id():
    from services.evidence_store import EvidenceStore

    store = EvidenceStore()
    first = store.create_evidence(
        source_id="src-1",
        excerpt="Excerpt one.",
        support_type="directly_supports",
        extraction_confidence=0.5,
    )
    second = store.create_evidence(
        source_id="src-1",
        excerpt="Excerpt two.",
        support_type="directly_supports",
        extraction_confidence=0.5,
    )

    assert first.evidence_id != second.evidence_id
    files = list(_evidence_dir().glob("*.yaml"))
    assert len(files) == 2


def test_different_offsets_produce_different_evidence_id():
    from models_ontology import EvidenceLocator
    from services.evidence_store import EvidenceStore

    store = EvidenceStore()
    first = store.create_evidence(
        source_id="src-1",
        excerpt="Same excerpt text.",
        support_type="directly_supports",
        extraction_confidence=0.5,
        locator=EvidenceLocator(character_start=0, character_end=18),
    )
    second = store.create_evidence(
        source_id="src-1",
        excerpt="Same excerpt text.",
        support_type="directly_supports",
        extraction_confidence=0.5,
        locator=EvidenceLocator(character_start=5, character_end=23),
    )

    assert first.evidence_id != second.evidence_id
    files = list(_evidence_dir().glob("*.yaml"))
    assert len(files) == 2


def test_list_evidence_filters_by_source_id():
    from services.evidence_store import EvidenceStore

    store = EvidenceStore()
    store.create_evidence(
        source_id="src-a",
        excerpt="Excerpt from source a.",
        support_type="directly_supports",
        extraction_confidence=0.5,
    )
    store.create_evidence(
        source_id="src-b",
        excerpt="Excerpt from source b.",
        support_type="context_only",
        extraction_confidence=0.3,
    )

    all_records = store.list_evidence()
    assert len(all_records) == 2

    only_a = store.list_evidence(source_id="src-a")
    assert len(only_a) == 1
    assert only_a[0].source_id == "src-a"

    only_b = store.list_evidence(source_id="src-b")
    assert len(only_b) == 1
    assert only_b[0].source_id == "src-b"


def test_list_evidence_skips_malformed_yaml_file_without_raising():
    from services.evidence_store import EvidenceStore

    store = EvidenceStore()
    store.create_evidence(
        source_id="src-a",
        excerpt="A valid excerpt that should survive the scan.",
        support_type="directly_supports",
        extraction_confidence=0.5,
    )

    evidence_dir = _evidence_dir()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    corrupt_path = evidence_dir / "evidence-0000000000000000.yaml"
    corrupt_path.write_text("{ this is not: valid yaml [", encoding="utf-8")

    records = store.list_evidence()
    assert len(records) == 1
    assert records[0].source_id == "src-a"


def test_list_evidence_skips_file_failing_pydantic_validation():
    from services.evidence_store import EvidenceStore

    store = EvidenceStore()
    store.create_evidence(
        source_id="src-a",
        excerpt="A valid excerpt that should survive the scan.",
        support_type="directly_supports",
        extraction_confidence=0.5,
    )

    evidence_dir = _evidence_dir()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    invalid_path = evidence_dir / "evidence-1111111111111111.yaml"
    # Valid YAML, but missing required fields (e.g. support_type) so it
    # fails Evidence validation rather than YAML parsing.
    invalid_path.write_text("source_id: src-z\nexcerpt: incomplete\n", encoding="utf-8")

    records = store.list_evidence()
    assert len(records) == 1
    assert records[0].source_id == "src-a"


def test_create_evidence_with_blank_excerpt_raises():
    from services.evidence_store import EvidenceStore

    store = EvidenceStore()
    with pytest.raises(Exception):
        store.create_evidence(
            source_id="src-a",
            excerpt="   ",
            support_type="directly_supports",
            extraction_confidence=0.5,
        )

    # No file should have been written for the rejected record.
    assert list(_evidence_dir().glob("*.yaml")) == []
