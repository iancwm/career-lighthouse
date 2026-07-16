# api/tests/test_entity_store.py
"""Unit tests for EntityStore (api/services/entity_store.py) — ontology Milestone 1.

Isolation is provided by the autouse `reset_ontology_stores` fixture in
conftest.py, which points ONTOLOGY_ENTITIES_DIR at a fresh tmp dir and resets
EntityStore._instance before/after each test. No manual setup is needed here.
"""

import os
from pathlib import Path

import pytest
import yaml

from services.entity_store import EntityStore
from services.runtime_paths import default_ontology_entities_dir


def _entities_root() -> Path:
    return Path(
        os.environ.get("ONTOLOGY_ENTITIES_DIR", str(default_ontology_entities_dir()))
    )


# ---------------------------------------------------------------------------
# create_entity + get_entity round-trip
# ---------------------------------------------------------------------------


class TestCreateAndGetEntity:
    def test_create_entity_writes_yaml_under_entity_type_subdir(self):
        store = EntityStore()
        entity = store.create_entity("organization", "Stripe Singapore")

        expected_path = _entities_root() / "organization" / f"{entity.entity_id}.yaml"
        assert expected_path.exists()
        assert entity.entity_type == "organization"
        assert entity.canonical_name == "Stripe Singapore"
        assert entity.entity_id == "organization-stripe_singapore"

    def test_created_entity_round_trips_through_get_entity(self):
        store = EntityStore()
        created = store.create_entity(
            "organization",
            "Goldman Sachs",
            aliases=["GS"],
            geography="SG",
            external_ids={"employer_slug": "goldman_sachs"},
        )

        fetched = store.get_entity("organization", created.entity_id)
        assert fetched is not None
        assert fetched.entity_id == created.entity_id
        assert fetched.canonical_name == "Goldman Sachs"
        assert fetched.aliases == ["GS"]
        assert fetched.geography == "SG"
        assert fetched.external_ids == {"employer_slug": "goldman_sachs"}
        assert fetched.created_at == created.created_at

    def test_get_entity_returns_none_for_missing_record(self):
        store = EntityStore()
        assert store.get_entity("organization", "organization-does_not_exist") is None


# ---------------------------------------------------------------------------
# entity_id determinism / idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_same_type_and_name_returns_existing_entity_not_a_duplicate(self):
        store = EntityStore()
        first = store.create_entity("organization", "Deloitte Singapore")
        second = store.create_entity("organization", "Deloitte Singapore")

        assert first.entity_id == second.entity_id
        assert first.created_at == second.created_at

        type_dir = _entities_root() / "organization"
        files = list(type_dir.glob("*.yaml"))
        assert len(files) == 1

    def test_entity_id_is_deterministic_across_calls(self):
        store = EntityStore()
        first = store.create_entity("programme", "Summer Analyst Programme")
        EntityStore._instance = None
        store2 = EntityStore()
        second = store2.get_entity("programme", first.entity_id)
        assert second is not None
        assert second.entity_id == first.entity_id


# ---------------------------------------------------------------------------
# Collision handling
# ---------------------------------------------------------------------------


class TestCollisionHandling:
    def test_different_names_with_same_base_slug_get_different_ids(self):
        store = EntityStore()
        first = store.create_entity("organization", "Deloitte!")
        second = store.create_entity("organization", "Deloitte?")

        assert first.canonical_name != second.canonical_name
        assert first.entity_id != second.entity_id
        # Both records must be independently retrievable and correct.
        assert store.get_entity("organization", first.entity_id).canonical_name == "Deloitte!"
        assert store.get_entity("organization", second.entity_id).canonical_name == "Deloitte?"

    def test_collision_escalates_with_geography_when_provided(self):
        store = EntityStore()
        first = store.create_entity("organization", "Deloitte SG")
        second = store.create_entity(
            "organization", "Deloitte HK", geography="HK"
        )

        assert first.entity_id != second.entity_id
        assert second.entity_id.endswith("_hk")


# ---------------------------------------------------------------------------
# list_entities
# ---------------------------------------------------------------------------


class TestListEntities:
    def test_filters_by_entity_type(self):
        store = EntityStore()
        store.create_entity("organization", "Stripe")
        store.create_entity("programme", "Summer Analyst")

        orgs = store.list_entities(entity_type="organization")
        assert {e.canonical_name for e in orgs} == {"Stripe"}

        programmes = store.list_entities(entity_type="programme")
        assert {e.canonical_name for e in programmes} == {"Summer Analyst"}

        all_entities = store.list_entities()
        assert len(all_entities) == 2

    def test_filters_by_status(self):
        store = EntityStore()
        active = store.create_entity("organization", "Active Co")
        archived = store.create_entity("organization", "Archived Co")

        # Directly rewrite the archived record's status on disk, since
        # create_entity always stamps status="active" and there is no
        # update method in Milestone 1 scope.
        path = _entities_root() / "organization" / f"{archived.entity_id}.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload["status"] = "archived"
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

        active_only = store.list_entities(entity_type="organization", status="active")
        assert {e.entity_id for e in active_only} == {active.entity_id}

        archived_only = store.list_entities(entity_type="organization", status="archived")
        assert {e.entity_id for e in archived_only} == {archived.entity_id}


# ---------------------------------------------------------------------------
# find_candidates
# ---------------------------------------------------------------------------


class TestFindCandidates:
    def test_matches_canonical_name_case_and_whitespace_insensitively(self):
        store = EntityStore()
        entity = store.create_entity("organization", "Goldman Sachs")

        matches = store.find_candidates("organization", "  GOLDMAN   sachs  ")
        assert [m.entity_id for m in matches] == [entity.entity_id]

    def test_matches_alias(self):
        store = EntityStore()
        entity = store.create_entity(
            "organization", "Goldman Sachs", aliases=["GS", "Goldman"]
        )

        matches = store.find_candidates("organization", "gs")
        assert [m.entity_id for m in matches] == [entity.entity_id]

    def test_returns_empty_list_for_no_match(self):
        store = EntityStore()
        store.create_entity("organization", "Goldman Sachs")

        assert store.find_candidates("organization", "Morgan Stanley") == []
        assert store.find_candidates("programme", "Goldman Sachs") == []


# ---------------------------------------------------------------------------
# Defensive handling of corrupt files
# ---------------------------------------------------------------------------


class TestCorruptFileHandling:
    def test_malformed_yaml_file_is_skipped_by_list_entities(self):
        store = EntityStore()
        good = store.create_entity("organization", "Stripe")

        type_dir = _entities_root() / "organization"
        type_dir.mkdir(parents=True, exist_ok=True)
        (type_dir / "organization-broken.yaml").write_text(
            "canonical_name: [unterminated\n", encoding="utf-8"
        )

        results = store.list_entities(entity_type="organization")
        assert [e.entity_id for e in results] == [good.entity_id]

    def test_invalid_entity_payload_is_skipped_by_list_entities(self):
        store = EntityStore()
        good = store.create_entity("organization", "Stripe")

        type_dir = _entities_root() / "organization"
        type_dir.mkdir(parents=True, exist_ok=True)
        (type_dir / "organization-invalid.yaml").write_text(
            yaml.safe_dump({"entity_type": "organization"}, sort_keys=False),
            encoding="utf-8",
        )

        results = store.list_entities(entity_type="organization")
        assert [e.entity_id for e in results] == [good.entity_id]
