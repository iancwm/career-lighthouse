"""Validation tests for api/models_ontology.py — Milestone 1.

No runtime wiring is exercised here; these tests only check that the
Pydantic models accept well-formed records and reject malformed ones.
"""

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from models_ontology import (
    ApplicationWindowPayload,
    Claim,
    ClaimConfidence,
    ClaimObservationTime,
    ClaimScope,
    ClaimValidTime,
    Entity,
    Evidence,
    EvidenceLocator,
    RecruitmentStagePayload,
    SourceMetadata,
)

NOW = datetime(2026, 7, 16, tzinfo=timezone.utc)


def _confidence(**overrides):
    base = dict(extraction=0.9, evidence_strength=0.8, source_reliability=0.7)
    base.update(overrides)
    return ClaimConfidence(**base)


def _observation_time(**overrides):
    base = dict(observed_at=date(2026, 6, 1), recorded_at=NOW)
    base.update(overrides)
    return ClaimObservationTime(**base)


def _minimal_claim_kwargs(**overrides):
    base = dict(
        claim_id="claim-application_window-abc123",
        claim_type="application_window",
        subject_entity_id="organization-goldman_sachs_singapore",
        payload=ApplicationWindowPayload(intake_year=2026),
        observation_time=_observation_time(),
        confidence=_confidence(),
        evidence_ids=["evidence-abc123"],
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------


def test_entity_accepts_minimal_valid_record():
    entity = Entity(
        entity_id="organization-goldman_sachs_singapore",
        entity_type="organization",
        canonical_name="Goldman Sachs Singapore",
        created_at=NOW,
        updated_at=NOW,
    )
    assert entity.status == "active"
    assert entity.aliases == []
    assert entity.external_ids == {}


def test_entity_rejects_unknown_entity_type():
    with pytest.raises(ValidationError):
        Entity(
            entity_id="widget-1",
            entity_type="widget",
            canonical_name="Widget",
            created_at=NOW,
            updated_at=NOW,
        )


def test_entity_rejects_unknown_extra_field():
    with pytest.raises(ValidationError):
        Entity(
            entity_id="organization-x",
            entity_type="organization",
            canonical_name="X",
            created_at=NOW,
            updated_at=NOW,
            not_a_real_field="oops",
        )


def test_entity_rejects_empty_canonical_name():
    with pytest.raises(ValidationError):
        Entity(
            entity_id="organization-x",
            entity_type="organization",
            canonical_name="",
            created_at=NOW,
            updated_at=NOW,
        )


# ---------------------------------------------------------------------------
# SourceMetadata
# ---------------------------------------------------------------------------


def test_source_metadata_accepts_minimal_valid_record():
    meta = SourceMetadata(
        source_id="goldman-singapore-guide.txt",
        filename="goldman-singapore-guide.txt",
        retrieved_at=NOW,
    )
    assert meta.source_kind == "unknown"
    assert meta.authority_tier == "unknown"
    assert meta.contains_personal_data is False


def test_source_metadata_rejects_unknown_source_kind():
    with pytest.raises(ValidationError):
        SourceMetadata(
            source_id="x.txt",
            filename="x.txt",
            retrieved_at=NOW,
            source_kind="rumor",
        )


def test_source_metadata_rejects_unknown_authority_tier():
    with pytest.raises(ValidationError):
        SourceMetadata(
            source_id="x.txt",
            filename="x.txt",
            retrieved_at=NOW,
            authority_tier="trust_me_bro",
        )


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


def test_evidence_accepts_minimal_valid_record():
    evidence = Evidence(
        evidence_id="evidence-abc123",
        source_id="goldman-singapore-guide.txt",
        excerpt="September deadline for summer analyst applications.",
        support_type="directly_supports",
        extraction_confidence=0.85,
        created_at=NOW,
    )
    assert evidence.locator == EvidenceLocator()


def test_evidence_rejects_empty_excerpt():
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="evidence-abc123",
            source_id="src.txt",
            excerpt="   ",
            support_type="directly_supports",
            extraction_confidence=0.85,
            created_at=NOW,
        )


def test_evidence_rejects_excerpt_over_max_length():
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="evidence-abc123",
            source_id="src.txt",
            excerpt="x" * 2001,
            support_type="directly_supports",
            extraction_confidence=0.85,
            created_at=NOW,
        )


def test_evidence_rejects_out_of_range_confidence():
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="evidence-abc123",
            source_id="src.txt",
            excerpt="valid excerpt",
            support_type="directly_supports",
            extraction_confidence=1.5,
            created_at=NOW,
        )


def test_evidence_rejects_unknown_support_type():
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="evidence-abc123",
            source_id="src.txt",
            excerpt="valid excerpt",
            support_type="probably_true",
            extraction_confidence=0.5,
            created_at=NOW,
        )


# ---------------------------------------------------------------------------
# Claim — payloads
# ---------------------------------------------------------------------------


def test_application_window_payload_accepts_minimal_valid_record():
    payload = ApplicationWindowPayload(
        opens_on=date(2026, 8, 1),
        closes_on=date(2026, 9, 15),
        date_precision="exact_date",
        intake_year=2027,
    )
    assert payload.claim_type == "application_window"


def test_recruitment_stage_payload_requires_stage_name():
    with pytest.raises(ValidationError):
        RecruitmentStagePayload(stage_name="", stage_type="technical_interview")


def test_recruitment_stage_payload_rejects_unknown_stage_type():
    with pytest.raises(ValidationError):
        RecruitmentStagePayload(stage_name="First round", stage_type="vibe_check")


# ---------------------------------------------------------------------------
# Claim — envelope
# ---------------------------------------------------------------------------


def test_claim_accepts_minimal_valid_application_window_record():
    claim = Claim(**_minimal_claim_kwargs())
    assert claim.review_status == "proposed"
    assert claim.lifecycle == "active"
    assert claim.assertion_status == "inferred"


def test_claim_accepts_minimal_valid_recruitment_stage_record():
    claim = Claim(
        **_minimal_claim_kwargs(
            claim_id="claim-recruitment_stage-def456",
            claim_type="recruitment_stage",
            payload=RecruitmentStagePayload(
                stage_name="Technical interview",
                stage_type="technical_interview",
            ),
        )
    )
    assert claim.payload.stage_type == "technical_interview"


def test_claim_rejects_unknown_claim_type():
    with pytest.raises(ValidationError):
        Claim(**_minimal_claim_kwargs(claim_type="not_a_real_claim_type"))


def test_claim_rejects_missing_evidence_ids():
    with pytest.raises(ValidationError):
        Claim(**_minimal_claim_kwargs(evidence_ids=[]))


def test_claim_rejects_payload_claim_type_mismatch():
    # claim_type says application_window but payload is a RecruitmentStagePayload
    with pytest.raises(ValidationError):
        Claim(
            **_minimal_claim_kwargs(
                claim_type="application_window",
                payload=RecruitmentStagePayload(
                    stage_name="Technical interview",
                    stage_type="technical_interview",
                ),
            )
        )


def test_claim_rejects_out_of_range_confidence():
    with pytest.raises(ValidationError):
        Claim(**_minimal_claim_kwargs(confidence=_confidence(extraction=1.2)))


def test_claim_rejects_unknown_assertion_status():
    with pytest.raises(ValidationError):
        Claim(**_minimal_claim_kwargs(assertion_status="definitely_true"))


def test_claim_rejects_unknown_review_status():
    with pytest.raises(ValidationError):
        Claim(**_minimal_claim_kwargs(review_status="approved_by_vibes"))


def test_claim_rejects_malformed_payload_dict_missing_discriminator():
    # A raw dict payload with no recognizable claim_type field should fail
    # the discriminated union, not silently coerce to one branch.
    with pytest.raises(ValidationError):
        Claim(**_minimal_claim_kwargs(payload={"opens_on": "2026-08-01"}))


def test_claim_scope_round_trips_all_fields():
    scope = ClaimScope(
        geography="SG",
        organization_unit_id="organization_unit-gs_tmt",
        programme_id="programme-summer_analyst",
        role_id="role-analyst",
        seniority="entry_level",
        candidate_segment="undergraduate",
        academic_year="2026-2027",
    )
    claim = Claim(**_minimal_claim_kwargs(scope=scope))
    assert claim.scope == scope


def test_claim_valid_time_and_scope_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        ClaimScope(geography="SG", made_up_field="x")
    with pytest.raises(ValidationError):
        ClaimValidTime(valid_from=date(2026, 1, 1), made_up_field="x")
