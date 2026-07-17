"""Unit tests for ClaimContextService (api/services/claim_context.py) —
Milestone 2 grounded-answers claim injection.

`ClaimContextService` takes injectable `claim_store`/`entity_store`/
`employer_store` in its constructor, so most tests here pass lightweight
`unittest.mock.Mock`/`MagicMock` fakes rather than relying on the
file-backed stores' tmp-dir fixtures (those are still active via the
autouse `reset_ontology_stores` fixture in conftest.py, but unused directly
by most tests below). Real `Claim`/`Entity` Pydantic objects are built
directly, following the helper pattern in `test_claim_store.py`
(`_confidence()`/`_observation_time()`/`_window_payload()`/`_stage_payload()`).

Test run command:
    cd api && uv run --extra dev pytest tests/test_claim_context.py -q
"""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

from cfg import kb_cfg
from models_ontology import (
    ApplicationWindowPayload,
    Claim,
    ClaimConfidence,
    ClaimObservationTime,
    ClaimScope,
    ClaimValidTime,
    Entity,
    RecruitmentStagePayload,
)
from services.claim_context import ClaimContextService, claim_display_text, stale_caveat_year

NOW = datetime(2026, 7, 16, tzinfo=timezone.utc)
GOLDMAN_ENTITY_ID = "organization-goldman_sachs"


# ---------------------------------------------------------------------------
# Helpers (mirrors test_claim_store.py's builder-function pattern)
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
    base = dict(stage_name="HireVue video interview", stage_type="online_assessment")
    base.update(overrides)
    return RecruitmentStagePayload(**base)


def _claim(**overrides) -> Claim:
    base = dict(
        claim_id=f"claim-recruitment_stage-{overrides.get('_id_suffix', 'a')}",
        claim_type="recruitment_stage",
        subject_entity_id=GOLDMAN_ENTITY_ID,
        object_entity_id=None,
        payload=_stage_payload(),
        scope=ClaimScope(geography="SG"),
        valid_time=ClaimValidTime(),
        observation_time=_observation_time(),
        assertion_status="asserted",
        confidence=_confidence(),
        evidence_ids=["evidence-abc123"],
        lifecycle="active",
        review_status="approved",
    )
    overrides.pop("_id_suffix", None)
    base.update(overrides)
    return Claim(**base)


def _entity(**overrides) -> Entity:
    base = dict(
        entity_id=GOLDMAN_ENTITY_ID,
        entity_type="organization",
        canonical_name="Goldman Sachs",
        aliases=["GS"],
        created_at=NOW,
        updated_at=NOW,
    )
    base.update(overrides)
    return Entity(**base)


def _service(claim_store=None, entity_store=None, employer_store=None) -> ClaimContextService:
    if entity_store is None:
        entity_store = MagicMock()
        entity_store.list_entities.return_value = []
        entity_store.get_entity.return_value = None
    if employer_store is None:
        employer_store = MagicMock()
        employer_store.get_employer.return_value = None
    return ClaimContextService(
        claim_store=claim_store or MagicMock(),
        entity_store=entity_store,
        employer_store=employer_store,
    )


# ---------------------------------------------------------------------------
# 1. Success criterion 4 (GROUNDING-DESIGN.md) — high tier
# ---------------------------------------------------------------------------


def test_get_claim_context_returns_high_tier_for_three_strong_claims():
    claims = [
        _claim(_id_suffix=str(i), payload=_stage_payload(stage_name=f"Stage {i}", sequence=i))
        for i in range(3)
    ]
    claim_store = MagicMock()
    claim_store.list_claims_for_entity.return_value = claims
    employer_store = MagicMock()
    employer_store.get_employer.return_value = {"employer_name": "Goldman Sachs Singapore"}

    service = _service(claim_store=claim_store, employer_store=employer_store)
    context = service.get_claim_context(
        "Goldman SG interview process", "finance", employer_slug="goldman_sachs"
    )

    assert context.coverage_confidence == "high"
    assert context.entity_id == GOLDMAN_ENTITY_ID
    assert context.entity_name == "Goldman Sachs Singapore"
    assert len(context.claims) == 3


# ---------------------------------------------------------------------------
# 2. Field path regression (ENG-T1)
# ---------------------------------------------------------------------------


def test_get_claim_context_does_not_raise_on_correct_field_paths():
    # This fixture would have raised AttributeError under the old buggy
    # paths (c.extraction_confidence, c.valid_until) since those attributes
    # don't exist on Claim — proves the code reads c.confidence.extraction /
    # c.valid_time.valid_until instead.
    claims = [
        _claim(_id_suffix="1", confidence=_confidence(extraction=0.95)),
        _claim(_id_suffix="2", confidence=_confidence(extraction=0.85)),
        _claim(_id_suffix="3", confidence=_confidence(extraction=0.75)),
    ]
    claim_store = MagicMock()
    claim_store.list_claims_for_entity.return_value = claims

    service = _service(claim_store=claim_store)
    context = service.get_claim_context("Goldman interview process", employer_slug="goldman_sachs")

    assert context.coverage_confidence == "high"


# ---------------------------------------------------------------------------
# 3. Coverage-confidence "low" tier + staleness caveat
# ---------------------------------------------------------------------------


def test_get_claim_context_low_tier_when_all_claims_stale():
    stale_claims = [
        _claim(_id_suffix="1", valid_time=ClaimValidTime(valid_until=date(2020, 1, 1))),
        _claim(_id_suffix="2", valid_time=ClaimValidTime(valid_until=date(2021, 6, 30))),
    ]
    claim_store = MagicMock()
    claim_store.list_claims_for_entity.return_value = stale_claims

    service = _service(claim_store=claim_store)
    context = service.get_claim_context("Goldman interview process", employer_slug="goldman_sachs")

    assert context.coverage_confidence == "low"
    assert stale_caveat_year(context.claims) == "2021"


# ---------------------------------------------------------------------------
# 4. All-valid_until=None staleness fallback (direct unit test of stale_caveat_year)
# ---------------------------------------------------------------------------


def test_stale_caveat_year_falls_back_to_outdated_when_all_valid_until_none():
    claims = [
        _claim(_id_suffix="1", valid_time=ClaimValidTime(valid_until=None)),
        _claim(_id_suffix="2", valid_time=ClaimValidTime(valid_until=None)),
    ]
    assert stale_caveat_year(claims) == "outdated"


# ---------------------------------------------------------------------------
# 5-6. Error rescue
# ---------------------------------------------------------------------------


def test_get_claim_context_error_rescue_on_generic_store_exception():
    claim_store = MagicMock()
    claim_store.list_claims_for_entity.side_effect = Exception("boom")

    service = _service(claim_store=claim_store)
    context = service.get_claim_context("Goldman interview process", employer_slug="goldman_sachs")

    assert context.coverage_confidence == "none"
    assert context.claims == []


def test_get_claim_context_error_rescue_on_file_not_found_error():
    claim_store = MagicMock()
    claim_store.list_claims_for_entity.side_effect = FileNotFoundError("missing dir")

    service = _service(claim_store=claim_store)
    context = service.get_claim_context("Goldman interview process", employer_slug="goldman_sachs")

    assert context.coverage_confidence == "none"
    assert context.claims == []


# ---------------------------------------------------------------------------
# 7. resolve_entity fast path
# ---------------------------------------------------------------------------


def test_resolve_entity_fast_path_uses_employer_slug_without_entity_store_lookup():
    entity_store = MagicMock()
    service = _service(entity_store=entity_store)

    entity_id = service.resolve_entity("goldman_sachs", "anything")

    assert entity_id == GOLDMAN_ENTITY_ID
    entity_store.list_entities.assert_not_called()


# ---------------------------------------------------------------------------
# 8. resolve_entity keyword fallback — exactly one match
# ---------------------------------------------------------------------------


def test_resolve_entity_keyword_fallback_single_match():
    entity_store = MagicMock()
    entity_store.list_entities.return_value = [
        _entity(canonical_name="Goldman Sachs", aliases=[])
    ]
    service = _service(entity_store=entity_store)

    entity_id = service.resolve_entity(None, "What is Goldman Sachs' interview process?")

    assert entity_id == GOLDMAN_ENTITY_ID


# ---------------------------------------------------------------------------
# 9. resolve_entity keyword fallback — zero or multiple matches -> None
# ---------------------------------------------------------------------------


def test_resolve_entity_keyword_fallback_zero_matches_returns_none():
    entity_store = MagicMock()
    entity_store.list_entities.return_value = [
        _entity(canonical_name="Goldman Sachs", aliases=["GS"])
    ]
    service = _service(entity_store=entity_store)

    entity_id = service.resolve_entity(None, "What is the weather like today?")

    assert entity_id is None


def test_resolve_entity_keyword_fallback_multiple_matches_returns_none():
    entity_store = MagicMock()
    entity_store.list_entities.return_value = [
        _entity(
            entity_id="organization-goldman_sachs",
            canonical_name="Goldman Sachs",
            aliases=[],
        ),
        _entity(
            entity_id="organization-morgan_stanley",
            canonical_name="Morgan Stanley",
            aliases=[],
        ),
    ]
    service = _service(entity_store=entity_store)

    entity_id = service.resolve_entity(
        None, "Compare Goldman Sachs and Morgan Stanley interview processes"
    )

    assert entity_id is None


# ---------------------------------------------------------------------------
# 10. max_injected_claims cap
# ---------------------------------------------------------------------------


def test_max_injected_claims_cap_truncates_preserving_order(monkeypatch):
    monkeypatch.setitem(kb_cfg["ontology"], "max_injected_claims", 2)

    claims = [
        _claim(_id_suffix=str(i), payload=_stage_payload(stage_name=f"Stage {i}", sequence=i))
        for i in range(5)
    ]
    claim_store = MagicMock()
    claim_store.list_claims_for_entity.return_value = claims

    service = _service(claim_store=claim_store)
    context = service.get_claim_context("Goldman interview process", employer_slug="goldman_sachs")

    assert len(context.claims) == 2
    assert [c.claim_id for c in context.claims] == [claims[0].claim_id, claims[1].claim_id]


# ---------------------------------------------------------------------------
# 11. Scope filter
# ---------------------------------------------------------------------------


def test_get_claims_filters_by_scope_geography_and_includes_unscoped():
    sg_claim = _claim(_id_suffix="sg", scope=ClaimScope(geography="SG"))
    us_claim = _claim(_id_suffix="us", scope=ClaimScope(geography="US"))
    unscoped_claim = _claim(_id_suffix="none", scope=ClaimScope(geography=None))

    claim_store = MagicMock()
    claim_store.list_claims_for_entity.return_value = [sg_claim, us_claim, unscoped_claim]

    service = _service(claim_store=claim_store)
    results = service.get_claims(GOLDMAN_ENTITY_ID, scope_geography="SG")

    ids = {c.claim_id for c in results}
    assert sg_claim.claim_id in ids
    assert unscoped_claim.claim_id in ids
    assert us_claim.claim_id not in ids


# ---------------------------------------------------------------------------
# 12. assertion_status exclusion
# ---------------------------------------------------------------------------


def test_get_claims_excludes_contradicted_and_superseded():
    good = _claim(_id_suffix="good", assertion_status="asserted")
    contradicted = _claim(_id_suffix="contradicted", assertion_status="contradicted")
    superseded = _claim(_id_suffix="superseded", assertion_status="superseded")

    claim_store = MagicMock()
    claim_store.list_claims_for_entity.return_value = [good, contradicted, superseded]

    service = _service(claim_store=claim_store)
    results = service.get_claims(GOLDMAN_ENTITY_ID, scope_geography="SG")

    ids = {c.claim_id for c in results}
    assert ids == {good.claim_id}


# ---------------------------------------------------------------------------
# 13. claim_display_text
# ---------------------------------------------------------------------------


def test_claim_display_text_application_window():
    claim = _claim(
        claim_type="application_window",
        payload=_window_payload(opens_on=date(2026, 8, 1), closes_on=date(2026, 9, 15)),
    )
    text = claim_display_text(claim)

    assert "[application_window]" in text
    assert "2026-08-01" in text
    assert "2026-09-15" in text


def test_claim_display_text_recruitment_stage():
    claim = _claim(
        payload=_stage_payload(
            stage_name="HireVue video interview",
            sequence=2,
            stage_type="online_assessment",
            modality="video",
        )
    )
    text = claim_display_text(claim)

    assert "[recruitment_stage]" in text
    assert "HireVue video interview" in text
    assert "stage 2" in text
    assert "online_assessment" in text
    assert "video" in text


def test_claim_display_text_appends_evidence_excerpt_when_found():
    claim = _claim(evidence_ids=["evidence-abc123"])
    evidence_store = MagicMock()
    fake_evidence = MagicMock()
    fake_evidence.excerpt = "candidates complete a 15-minute HireVue"
    evidence_store.get_evidence.return_value = fake_evidence

    text = claim_display_text(claim, evidence_store)

    assert 'Evidence: "candidates complete a 15-minute HireVue"' in text
    evidence_store.get_evidence.assert_called_once_with("evidence-abc123")


def test_claim_display_text_no_evidence_store_no_crash_no_suffix():
    claim = _claim(evidence_ids=["evidence-abc123"])

    text = claim_display_text(claim, None)

    assert "Evidence:" not in text
