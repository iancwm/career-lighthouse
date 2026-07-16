# api/tests/test_source_ledger_ontology_extension.py
"""Regression tests for the Milestone-1 ontology extension of SourceLedgerStore.

Covers:
  - `_normalize_record()` defaults the new SourceMetadata-shaped fields when
    absent, and preserves them when present.
  - `SourceLedgerStore.upsert_record()` (pre-existing kwargs only) still
    round-trips correctly, and `to_source_metadata()` returns a valid
    `SourceMetadata` with the new fields defaulted.
  - `to_source_metadata()` returns None for an unknown filename.
  - Acceptance criterion #7 (docs/ontology/MILESTONE-1.md §4): the real
    `knowledge/employers/stripe_singapore.yaml` fixture (with its
    double-nested `data.data` fact) still loads through
    `services.fact_store.list_facts()` unchanged, guarding against any
    accidental coupling introduced by the source_ledger.py changes above,
    even though those changes don't touch the fact_store code path directly.

Test run command:
    cd api && uv run pytest tests/test_source_ledger_ontology_extension.py -q
"""

from pathlib import Path

import pytest

from models_ontology import SourceMetadata
from services.source_ledger import SourceLedgerStore, _normalize_record


# ---------------------------------------------------------------------------
# _normalize_record() default / preservation behavior
# ---------------------------------------------------------------------------


def test_normalize_record_defaults_new_ontology_fields_when_absent():
    record = _normalize_record({"filename": "some-doc.pdf"})

    assert record["source_kind"] == "unknown"
    assert record["publisher_name"] is None
    assert record["publisher_entity_id"] is None
    assert record["published_at"] is None
    assert record["jurisdiction"] is None
    assert record["coverage_geographies"] == []
    assert record["coverage_entity_ids"] == []
    assert record["authority_tier"] == "unknown"
    assert record["contains_personal_data"] is False
    assert record["content_hash"] is None

    # Pre-existing fields are untouched by the extension.
    assert record["filename"] == "some-doc.pdf"
    assert record["lifecycle"] == "active"
    assert record["chunk_count"] == 0


def test_normalize_record_preserves_new_ontology_fields_when_present():
    payload = {
        "filename": "official-page.pdf",
        "source_kind": "official_employer_page",
        "publisher_name": "Stripe",
        "publisher_entity_id": "organization-stripe_singapore",
        "published_at": "2025-01-15",
        "jurisdiction": "SG",
        "coverage_geographies": ["SG", "global"],
        "coverage_entity_ids": ["organization-stripe_singapore"],
        "authority_tier": "official_primary",
        "contains_personal_data": True,
        "content_hash": "abc123",
    }
    record = _normalize_record(payload)

    assert record["source_kind"] == "official_employer_page"
    assert record["publisher_name"] == "Stripe"
    assert record["publisher_entity_id"] == "organization-stripe_singapore"
    assert record["published_at"] == "2025-01-15"
    assert record["jurisdiction"] == "SG"
    assert record["coverage_geographies"] == ["SG", "global"]
    assert record["coverage_entity_ids"] == ["organization-stripe_singapore"]
    assert record["authority_tier"] == "official_primary"
    assert record["contains_personal_data"] is True
    assert record["content_hash"] == "abc123"


# ---------------------------------------------------------------------------
# upsert_record() round-trip + to_source_metadata()
# ---------------------------------------------------------------------------


def test_upsert_record_with_only_legacy_kwargs_still_round_trips():
    """Existing callers that pass none of the new fields keep working unchanged."""
    store = SourceLedgerStore()
    written = store.upsert_record(
        filename="legacy-doc.pdf",
        chunk_count=12,
        uploaded_by="counsellor-1",
        linked_knowledge_object="employer:stripe_singapore",
    )

    assert written["filename"] == "legacy-doc.pdf"
    assert written["chunk_count"] == 12
    assert written["uploaded_by"] == "counsellor-1"
    assert written["lifecycle"] == "active"

    reloaded = store.get_record("legacy-doc.pdf")
    assert reloaded is not None
    assert reloaded["chunk_count"] == 12
    assert reloaded["uploaded_by"] == "counsellor-1"


def test_to_source_metadata_returns_valid_model_with_defaults():
    store = SourceLedgerStore()
    store.upsert_record(filename="legacy-doc-2.pdf", chunk_count=3)

    metadata = store.to_source_metadata("legacy-doc-2.pdf")

    assert metadata is not None
    assert isinstance(metadata, SourceMetadata)
    assert metadata.source_id == "legacy-doc-2.pdf"
    assert metadata.filename == "legacy-doc-2.pdf"
    assert metadata.source_kind == "unknown"
    assert metadata.authority_tier == "unknown"
    assert metadata.contains_personal_data is False
    assert metadata.coverage_geographies == []
    assert metadata.coverage_entity_ids == []
    assert metadata.lifecycle == "active"
    # retrieved_at is derived from the ledger's uploaded_at, not a separate field.
    assert metadata.retrieved_at is not None


def test_to_source_metadata_returns_none_for_unknown_filename():
    store = SourceLedgerStore()
    assert store.to_source_metadata("does-not-exist.pdf") is None
    assert store.to_source_metadata(None) is None


# ---------------------------------------------------------------------------
# Acceptance criterion #7: existing YAML records remain readable.
# ---------------------------------------------------------------------------


def test_stripe_singapore_employer_yaml_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "knowledge" / "employers" / "stripe_singapore.yaml"
    assert path.exists(), f"expected fixture file missing: {path}"


def test_stripe_singapore_facts_still_load_through_fact_store_list_facts(monkeypatch):
    """Guards against any accidental coupling from the source_ledger.py ontology
    extension, even though that change doesn't touch the fact_store code path.

    `knowledge/employers/stripe_singapore.yaml` has a double-nested `data.data`
    fact shape (see docs/ontology/ONTOLOGY-DESIGN.md §1.2's reference to it) and
    must continue to parse via the real, unmodified employers directory.

    EMPLOYERS_DIR is pinned explicitly here because at least one pre-existing
    test (test_kb_router.py) sets it via `os.environ[...]` directly rather than
    `monkeypatch`, which can otherwise leak a stale directory into this test
    depending on suite ordering — unrelated to this change, but this test must
    not be flaky because of it.
    """
    from services import fact_store

    repo_root = Path(__file__).resolve().parents[2]
    fixture_path = repo_root / "knowledge" / "employers" / "stripe_singapore.yaml"
    assert fixture_path.exists()

    monkeypatch.setenv("EMPLOYERS_DIR", str(repo_root / "knowledge" / "employers"))

    all_facts = fact_store.list_facts()
    facts = [fact for fact in all_facts if fact.source_label == "stripe_singapore"]

    assert facts, "expected at least one fact for Stripe Singapore to load"
    slugs = {fact.slug for fact in facts}
    assert "stripe-singapore-capstone-recruitment" in slugs
    assert "stripe-jane-teoh-smu-mitb" in slugs
    assert "stripe-singapore-capstone-event-attendance" in slugs

    for fact in facts:
        assert fact.confidence == 80
        assert fact.lifecycle == "active"
