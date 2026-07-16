"""Unit tests for ClaimStore — ontology & metadata layer, Milestone 1.

Isolation (fresh `ONTOLOGY_CLAIMS_DIR` tmp dir + `ClaimStore._instance` reset
per test) is provided by the autouse `reset_ontology_stores` fixture in
`api/tests/conftest.py` — no local fixture is needed for that.

Test run command:
    cd api && uv run pytest tests/test_claim_store.py -q
"""

import os
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from models_ontology import (
    ApplicationWindowPayload,
    ClaimConfidence,
    ClaimObservationTime,
    ClaimScope,
    RecruitmentStagePayload,
)
from services.claim_store import ClaimStore

NOW = datetime(2026, 7, 16, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _confidence(**overrides):
    base = dict(extraction=0.9, evidence_strength=0.8, source_reliability=0.7)
    base.update(overrides)
    return ClaimConfidence(**base)


def _observation_time(**overrides):
    base = dict(observed_at=date(2026, 6, 1), recorded_at=NOW)
    base.update(overrides)
    return ClaimObservationTime(**base)


def _window_payload(**overrides):
    base = dict(
        opens_on=date(2026, 8, 1),
        closes_on=date(2026, 9, 15),
        date_precision="exact_date",
        intake_year=2027,
    )
    base.update(overrides)
    return ApplicationWindowPayload(**base)


def _stage_payload(**overrides):
    base = dict(stage_name="Technical interview", stage_type="technical_interview")
    base.update(overrides)
    return RecruitmentStagePayload(**base)


def _minimal_kwargs(**overrides):
    base = dict(
        claim_type="application_window",
        subject_entity_id="organization-goldman_sachs_singapore",
        payload=_window_payload(),
        observation_time=_observation_time(),
        confidence=_confidence(),
        evidence_ids=["evidence-abc123"],
    )
    base.update(overrides)
    return base


def _claims_dir() -> Path:
    return Path(os.environ["ONTOLOGY_CLAIMS_DIR"])


# ---------------------------------------------------------------------------
# create_claim / get_claim round trip
# ---------------------------------------------------------------------------


def test_create_claim_writes_yaml_file_and_round_trips():
    store = ClaimStore()
    claim = store.create_claim(**_minimal_kwargs())

    path = _claims_dir() / f"{claim.claim_id}.yaml"
    assert path.exists()

    fetched = store.get_claim(claim.claim_id)
    assert fetched is not None
    assert fetched.claim_id == claim.claim_id
    assert fetched.subject_entity_id == claim.subject_entity_id
    assert fetched.payload == claim.payload
    assert fetched.lifecycle == "active"
    assert fetched.review_status == "proposed"


def test_get_claim_returns_none_for_missing_claim():
    store = ClaimStore()
    assert store.get_claim("claim-application_window-doesnotexist") is None


# ---------------------------------------------------------------------------
# claim_id determinism / idempotency
# ---------------------------------------------------------------------------


def test_claim_id_is_deterministic_and_idempotent_across_metadata_variation():
    store = ClaimStore()

    first = store.create_claim(
        **_minimal_kwargs(
            confidence=_confidence(extraction=0.9),
            evidence_ids=["evidence-aaa"],
            observation_time=_observation_time(observed_at=date(2026, 6, 1)),
        )
    )
    second = store.create_claim(
        **_minimal_kwargs(
            confidence=_confidence(extraction=0.2),
            evidence_ids=["evidence-bbb", "evidence-ccc"],
            observation_time=_observation_time(observed_at=date(2026, 6, 30)),
        )
    )

    assert first.claim_id == second.claim_id
    # The store must not have overwritten/re-created a second file; exactly
    # one claim file exists for this deterministic id.
    yaml_files = list(_claims_dir().glob("*.yaml"))
    assert len(yaml_files) == 1
    # Idempotent-return semantics: the second call's metadata (confidence,
    # evidence_ids) must NOT have clobbered the first claim on disk.
    persisted = store.get_claim(first.claim_id)
    assert persisted.evidence_ids == ["evidence-aaa"]
    assert persisted.confidence.extraction == 0.9


def test_different_payload_produces_different_claim_id():
    store = ClaimStore()
    a = store.create_claim(**_minimal_kwargs(payload=_window_payload(intake_year=2027)))
    b = store.create_claim(**_minimal_kwargs(payload=_window_payload(intake_year=2028)))
    assert a.claim_id != b.claim_id
    assert len(list(_claims_dir().glob("*.yaml"))) == 2


def test_different_scope_produces_different_claim_id():
    store = ClaimStore()
    a = store.create_claim(**_minimal_kwargs(scope=ClaimScope(geography="SG")))
    b = store.create_claim(**_minimal_kwargs(scope=ClaimScope(geography="US")))
    assert a.claim_id != b.claim_id


# ---------------------------------------------------------------------------
# evidence_ids defense-in-depth
# ---------------------------------------------------------------------------


def test_create_claim_rejects_empty_evidence_ids_before_touching_disk():
    store = ClaimStore()
    with pytest.raises(ValueError):
        store.create_claim(**_minimal_kwargs(evidence_ids=[]))

    # Never reaches disk: the claims directory must not have been created,
    # or if it was pre-created by the fixture, it must contain no files.
    claims_dir = _claims_dir()
    if claims_dir.exists():
        assert list(claims_dir.glob("*.yaml")) == []


# ---------------------------------------------------------------------------
# list_claims filters
# ---------------------------------------------------------------------------


def test_list_claims_filters_by_claim_type():
    store = ClaimStore()
    window = store.create_claim(**_minimal_kwargs())
    stage = store.create_claim(
        **_minimal_kwargs(claim_type="recruitment_stage", payload=_stage_payload())
    )

    windows = store.list_claims(claim_type="application_window")
    assert [c.claim_id for c in windows] == [window.claim_id]

    stages = store.list_claims(claim_type="recruitment_stage")
    assert [c.claim_id for c in stages] == [stage.claim_id]


def test_list_claims_filters_by_subject_entity_id():
    store = ClaimStore()
    gs = store.create_claim(
        **_minimal_kwargs(subject_entity_id="organization-goldman_sachs_singapore")
    )
    store.create_claim(
        **_minimal_kwargs(
            subject_entity_id="organization-mckinsey_singapore",
            payload=_window_payload(intake_year=2099),
        )
    )

    results = store.list_claims(subject_entity_id="organization-goldman_sachs_singapore")
    assert [c.claim_id for c in results] == [gs.claim_id]


def test_list_claims_filters_by_review_status():
    store = ClaimStore()
    approved = store.create_claim(**_minimal_kwargs(review_status="approved"))
    store.create_claim(
        **_minimal_kwargs(review_status="proposed", payload=_window_payload(intake_year=2030))
    )

    results = store.list_claims(review_status="approved")
    assert [c.claim_id for c in results] == [approved.claim_id]


def test_list_claims_filters_by_lifecycle():
    store = ClaimStore()
    old = store.create_claim(**_minimal_kwargs())
    store.supersede_claim(
        old.claim_id,
        _minimal_kwargs(payload=_window_payload(intake_year=2031)),
    )

    active = store.list_claims(lifecycle="active")
    superseded = store.list_claims(lifecycle="superseded")

    assert old.claim_id not in [c.claim_id for c in active]
    assert old.claim_id in [c.claim_id for c in superseded]


# ---------------------------------------------------------------------------
# list_claims_for_entity
# ---------------------------------------------------------------------------


def test_list_claims_for_entity_matches_subject_or_object():
    store = ClaimStore()
    as_subject = store.create_claim(
        **_minimal_kwargs(
            subject_entity_id="organization-goldman_sachs_singapore",
            object_entity_id=None,
        )
    )
    as_object = store.create_claim(
        **_minimal_kwargs(
            subject_entity_id="person-jane_teoh",
            object_entity_id="organization-goldman_sachs_singapore",
            payload=_window_payload(intake_year=2040),
        )
    )
    unrelated = store.create_claim(
        **_minimal_kwargs(
            subject_entity_id="organization-mckinsey_singapore",
            payload=_window_payload(intake_year=2041),
        )
    )

    results = store.list_claims_for_entity("organization-goldman_sachs_singapore")
    ids = {c.claim_id for c in results}
    assert ids == {as_subject.claim_id, as_object.claim_id}
    assert unrelated.claim_id not in ids


# ---------------------------------------------------------------------------
# supersede_claim
# ---------------------------------------------------------------------------


def test_supersede_claim_marks_old_and_activates_new():
    store = ClaimStore()
    old = store.create_claim(**_minimal_kwargs())

    new = store.supersede_claim(
        old.claim_id,
        _minimal_kwargs(payload=_window_payload(intake_year=2099)),
    )

    assert new.claim_id != old.claim_id
    assert new.lifecycle == "active"

    refreshed_old = store.get_claim(old.claim_id)
    assert refreshed_old.superseded_by == new.claim_id
    assert refreshed_old.lifecycle == "superseded"

    active_ids = {c.claim_id for c in store.list_claims(lifecycle="active")}
    assert old.claim_id not in active_ids
    assert new.claim_id in active_ids

    # Old claim remains retrievable directly even though excluded from the
    # active-lifecycle listing.
    assert store.get_claim(old.claim_id) is not None


def test_supersede_claim_raises_for_unknown_old_claim_id():
    store = ClaimStore()
    with pytest.raises(ValueError):
        store.supersede_claim(
            "claim-application_window-doesnotexist",
            _minimal_kwargs(),
        )


# ---------------------------------------------------------------------------
# update_review_status
# ---------------------------------------------------------------------------


def test_update_review_status_changes_and_persists_field():
    store = ClaimStore()
    claim = store.create_claim(**_minimal_kwargs())
    assert claim.review_status == "proposed"

    updated = store.update_review_status(claim.claim_id, "approved")
    assert updated.review_status == "approved"

    refetched = store.get_claim(claim.claim_id)
    assert refetched.review_status == "approved"


def test_update_review_status_raises_for_unknown_claim_id():
    store = ClaimStore()
    with pytest.raises(ValueError):
        store.update_review_status("claim-application_window-doesnotexist", "approved")


def test_update_review_status_raises_for_invalid_status():
    store = ClaimStore()
    claim = store.create_claim(**_minimal_kwargs())
    with pytest.raises(ValueError):
        store.update_review_status(claim.claim_id, "not_a_real_status")


# ---------------------------------------------------------------------------
# Corrupt file resilience
# ---------------------------------------------------------------------------


def test_list_claims_skips_malformed_yaml_file():
    store = ClaimStore()
    good = store.create_claim(**_minimal_kwargs())

    claims_dir = _claims_dir()
    claims_dir.mkdir(parents=True, exist_ok=True)
    corrupt_path = claims_dir / "claim-application_window-corrupt.yaml"
    corrupt_path.write_text("{ this is: not valid yaml: [", encoding="utf-8")

    results = store.list_claims()
    ids = {c.claim_id for c in results}
    assert good.claim_id in ids
    assert "claim-application_window-corrupt" not in ids


def test_list_claims_skips_valid_yaml_that_fails_claim_validation():
    store = ClaimStore()
    good = store.create_claim(**_minimal_kwargs())

    claims_dir = _claims_dir()
    claims_dir.mkdir(parents=True, exist_ok=True)
    bad_path = claims_dir / "claim-application_window-badschema.yaml"
    bad_path.write_text("claim_id: claim-application_window-badschema\n", encoding="utf-8")

    results = store.list_claims()
    ids = {c.claim_id for c in results}
    assert good.claim_id in ids
    assert "claim-application_window-badschema" not in ids
