# api/tests/test_ontology_e2e_fixture.py
"""End-to-end fixture for Milestone 1 acceptance criterion 8
(docs/ontology/MILESTONE-1.md §4, row 8):

    "A fixture demonstrates extraction from source text through reviewed
    claim proposal ... runs one demo-data document (e.g.
    demo-data/goldman-singapore-guide.txt's 'September deadline for summer
    analyst' line) through Stage 1->4, produces an IntentCard(domain='claim'),
    and asserts committing it writes a Claim file with review_status='approved'
    and a resolvable evidence_id. A second fixture case, over a mention of
    'Deloitte,' asserts Stage 2 returns resolution_status='ambiguous' against
    the real deloitte.yaml/deloitte_singapore.yaml pair rather than proceeding
    to a claim."

Both cases drive the REAL Stage 1->4 orchestrator
(`services.ontology_extraction.extract_claims_for_source`) with real
`EntityStore`/`EvidenceStore`/`ClaimStore` and real Stage 2/Stage 4 logic.
Only the three LLM call sites are mocked, at the exact boundary
`services.ontology_extraction.call_structured_json` (the name as imported
into the module under test) -- the same patch target used by
`test_ontology_extraction.py`. Zero real network/API calls are made.

Fixture case 1 additionally drives the real HTTP-reachable commit endpoint
(`POST /api/kb/session/{session_id}/claims/{card_id}/commit`) via
`TestClient`, using a card built from the pipeline's own (real, not canned)
output -- the strongest available proof that "a counsellor could actually
trigger this" per the task brief. The session/card seeding pattern mirrors
`test_ontology_router.py`'s `_seed_session_with_claim_card` helper, since
`POST /extract-claims` deliberately does not persist cards into a session
itself (ONTOLOGY-DESIGN.md §7: "does not persist").
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import services.ontology_extraction as oe
from models_kb import IntentCard
from models_ontology import ApplicationWindowPayload
from routers.ontology_router import _claim_card_diff_for_proposal
from services.claim_store import ClaimStore
from services.entity_store import EntityStore
from services.evidence_store import EvidenceStore

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_client():
    """Minimal TestClient factory, mirroring test_ontology_router.py's
    make_client(): bypasses the admin-key dependency (also already bypassed
    by conftest.py's autouse clear_env_secrets setting ADMIN_KEY="", but the
    explicit override keeps this file independent of that fixture's default).
    """
    from fastapi.testclient import TestClient

    import dependencies
    from main import app

    app.dependency_overrides[dependencies.require_admin_key] = lambda: None
    client = TestClient(app)
    client.headers["X-Admin-Key"] = "test-key"
    return client


def _seed_session_with_card(tmp_path, monkeypatch, session_id: str, card: dict):
    """Persist a KnowledgeSession containing `card` so the real commit
    endpoint has something to operate on. Mirrors
    test_ontology_router.py::_seed_session_with_claim_card, generalized to
    accept an arbitrary already-built card dict (here, one produced by the
    real pipeline + _claim_card_diff_for_proposal, not a hand-typed canned
    diff).
    """
    import os

    from models_session import KnowledgeSession
    from services.session_store import SessionStore

    monkeypatch.setenv("SESSIONS_DIR", str(tmp_path / "sessions"))
    os.environ["SESSIONS_DIR"] = str(tmp_path / "sessions")
    SessionStore._instance = None

    now = datetime.now(timezone.utc).isoformat()
    session = KnowledgeSession(
        id=session_id,
        status="analyzed",
        raw_input="fixture",
        intent_cards=[card],
        created_by="counsellor",
        created_at=now,
        updated_at=now,
    )
    store = SessionStore()
    store.save_session(session)
    return store


# ---------------------------------------------------------------------------
# Fixture case 1 -- Goldman Sachs application-window claim:
# full extraction -> review -> commit
# ---------------------------------------------------------------------------


class TestGoldmanSachsApplicationWindowFixture:
    def test_extraction_through_reviewed_and_committed_claim(self, tmp_path, monkeypatch):
        # -- Arrange: the real demo-data document -----------------------------
        source_text = (
            REPO_ROOT / "demo-data" / "goldman-singapore-guide.txt"
        ).read_text(encoding="utf-8")

        mention_text = "Goldman Sachs"
        mention_start = source_text.index(mention_text)
        mention_end = mention_start + len(mention_text)

        claim_span_text = "September deadline for summer analyst"
        assert claim_span_text in source_text  # sanity: verbatim substring per the brief
        span_start = source_text.index(claim_span_text)
        span_end = span_start + len(claim_span_text)

        source_id = "demo-data:goldman-singapore-guide.txt"

        # Seed a single, unambiguous Goldman Sachs organization entity so
        # Stage 2 resolves "matched", not "proposed_new" (commit_claim_card
        # 400s on an unresolved subject_entity_id, per ontology_router.py).
        entity = EntityStore().create_entity("organization", "Goldman Sachs")

        stage1_result = oe.MentionExtractionResult(
            mentions=[
                oe.MentionCandidate(
                    text=mention_text,
                    entity_type="organization",
                    character_start=mention_start,
                    character_end=mention_end,
                )
            ],
            claim_spans=[
                oe.ClaimSpanCandidate(
                    character_start=span_start, character_end=span_end
                )
            ],
        )
        stage3_result = oe.ClaimExtractionResult(
            claims=[
                oe.ClaimProposal(
                    claim_type="application_window",
                    subject_mention_ref=0,
                    payload=ApplicationWindowPayload(
                        # Only a September deadline month is stated in the
                        # source, no exact day/date -- date_precision reflects
                        # that; intake_year=2026 matches the doc's own
                        # "2025-2026" SMU campus recruiting cycle heading
                        # (a September application deadline feeds the 2026
                        # summer analyst intake).
                        intake_year=2026,
                        date_precision="approximate",
                    ),
                    extraction_confidence=0.75,
                    evidence_span_refs=[0],
                )
            ]
        )
        stage4_result = oe.VerificationResult(verified=True, note=None)

        def _llm_side_effect(*, operation, **kwargs):
            if operation == "ontology_mention_extraction":
                return stage1_result
            if operation == "ontology_claim_extraction":
                return stage3_result
            if operation == "ontology_claim_verification":
                return stage4_result
            raise AssertionError(f"unexpected operation: {operation}")

        # -- Act: Stages 1-4, real orchestrator, LLM boundary mocked only ----
        with patch(
            "services.ontology_extraction.call_structured_json",
            side_effect=_llm_side_effect,
        ) as mock_llm:
            result = oe.extract_claims_for_source(
                source_text, source_id, employer_slug="goldman_sachs"
            )

        assert mock_llm.call_count == 3  # Stage 1, Stage 3, Stage 4 -- no more, no fewer

        assert len(result.claim_proposals) == 1
        proposal = result.claim_proposals[0]
        assert proposal.verification_status == "verified"
        assert proposal.subject_entity_id == entity.entity_id
        assert proposal.subject_entity_id is not None
        assert len(proposal.evidence_excerpts) >= 1
        assert any(
            excerpt in source_text for excerpt in proposal.evidence_excerpts
        )

        # -- Review: build the same IntentCard(domain="claim") the real
        # /extract-claims endpoint would build, using its own helper. -------
        diff = _claim_card_diff_for_proposal(proposal, source_id)
        card_id = "claim-goldman01"
        card = IntentCard(
            card_id=card_id,
            domain="claim",
            summary=f"{proposal.claim_type} claim for {proposal.subject_mention_text}",
            diff=diff,
            raw_input_ref=source_id,
            status="pending",
        )
        assert card.domain == "claim"

        # -- Commit: real HTTP-reachable endpoint, TestClient-driven. --------
        session_id = "sess-goldman-fixture"
        _seed_session_with_card(tmp_path, monkeypatch, session_id, card.model_dump())
        client = _make_client()

        response = client.post(
            f"/api/kb/session/{session_id}/claims/{card_id}/commit"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "committed"
        assert body["domain"] == "claim"
        claim_id = body["claim_id"]

        # -- Assert (the acceptance-criterion-8 payoff) ----------------------
        claim = ClaimStore().get_claim(claim_id)
        assert claim is not None
        assert claim.review_status == "approved"
        assert claim.evidence_ids  # non-empty
        assert claim.subject_entity_id == entity.entity_id

        evidence_store = EvidenceStore()
        for evidence_id in claim.evidence_ids:
            evidence = evidence_store.get_evidence(evidence_id)
            assert evidence is not None, f"evidence_id {evidence_id!r} did not resolve"
            assert evidence.excerpt in source_text


# ---------------------------------------------------------------------------
# Fixture case 2 -- Deloitte ambiguous resolution: no claim proceeds
# ---------------------------------------------------------------------------


class TestDeloitteAmbiguousResolutionFixture:
    def test_ambiguous_mention_does_not_proceed_to_a_claim(self):
        # -- Arrange: seed the two real, unreconciled Deloitte employer
        # records (knowledge/employers/deloitte.yaml and
        # deloitte_singapore.yaml) as two distinct Entity records, per
        # ONTOLOGY-DESIGN.md §5's discussion of this exact pair. Milestone 1
        # does NOT backfill employer YAML into Entity records automatically
        # (ONTOLOGY-DESIGN.md §4) -- this seeding is what a later,
        # out-of-scope backfill/merge step would eventually produce, done by
        # hand here so Stage 2 has real ambiguity to resolve against.
        #
        # canonical_names are deliberately distinct (create_entity is
        # idempotent on exact entity_type+canonical_name -- identical names
        # would silently return the SAME entity for both calls and defeat
        # the point of this fixture) and reflect each YAML file's own
        # tracks/notes content:
        #
        #  - deloitte.yaml (slug "deloitte"): tracks
        #    consulting/model_validation_risk/quantitative_finance/
        #    fintech_compliance, notes centered on "Deloitte model risk
        #    advisory practice ... primary exit option for banking model
        #    validators" -> "Deloitte Singapore (Model Risk Advisory)".
        #  - deloitte_singapore.yaml (slug "deloitte_singapore"): tracks
        #    management_consulting/sustainability_esg, no notes ->
        #    "Deloitte Singapore (Consulting & Sustainability)".
        entity_store = EntityStore()
        model_risk_entity = entity_store.create_entity(
            "organization",
            "Deloitte Singapore (Model Risk Advisory)",
            aliases=["Deloitte"],
            external_ids={"employer_slug": "deloitte"},
        )
        consulting_entity = entity_store.create_entity(
            "organization",
            "Deloitte Singapore (Consulting & Sustainability)",
            aliases=["Deloitte"],
            external_ids={"employer_slug": "deloitte_singapore"},
        )
        assert model_risk_entity.entity_id != consulting_entity.entity_id

        candidates = entity_store.find_candidates("organization", "Deloitte")
        assert {c.entity_id for c in candidates} == {
            model_risk_entity.entity_id,
            consulting_entity.entity_id,
        }

        source_text = (
            "Deloitte's Singapore office begins accepting summer analyst "
            "applications in September 2026."
        )
        mention_text = "Deloitte"
        mention_start = source_text.index(mention_text)
        mention_end = mention_start + len(mention_text)

        claim_span_text = "begins accepting summer analyst applications in September 2026"
        assert claim_span_text in source_text
        span_start = source_text.index(claim_span_text)
        span_end = span_start + len(claim_span_text)

        stage1_result = oe.MentionExtractionResult(
            mentions=[
                oe.MentionCandidate(
                    text=mention_text,
                    entity_type="organization",
                    character_start=mention_start,
                    character_end=mention_end,
                )
            ],
            claim_spans=[
                oe.ClaimSpanCandidate(
                    character_start=span_start, character_end=span_end
                )
            ],
        )

        # -- Act: real orchestrator, only the Stage 1 LLM call is ever
        # expected to fire -- if Stage 3 were invoked for an all-ambiguous
        # mention set, this side_effect raises and fails the test loudly
        # rather than silently mis-mocking a Stage 3 return value.
        def _llm_side_effect(*, operation, **kwargs):
            if operation == "ontology_mention_extraction":
                return stage1_result
            raise AssertionError(
                f"unexpected operation: {operation!r} -- Stage 3/4 must not "
                "run when every mention is ambiguous"
            )

        with patch(
            "services.ontology_extraction.call_structured_json",
            side_effect=_llm_side_effect,
        ) as mock_llm:
            result = oe.extract_claims_for_source(
                source_text, "fixture:deloitte-ambiguous"
            )

        # -- Assert: Stage 2 resolution is ambiguous, no claim proposal -----
        assert len(result.entity_resolutions) == 1
        resolution = result.entity_resolutions[0]
        assert resolution.resolution_status == "ambiguous"
        assert resolution.entity_id is None
        assert set(resolution.candidate_entity_ids) == {
            model_risk_entity.entity_id,
            consulting_entity.entity_id,
        }

        assert result.claim_proposals == []

        # Only Stage 1 ran -- confirms the pipeline's early-out
        # (`if not eligible or not span_records: return ...`) actually
        # short-circuits before Stage 3, rather than merely happening to
        # produce zero claims for some other reason.
        assert mock_llm.call_count == 1
        assert mock_llm.call_args.kwargs["operation"] == "ontology_mention_extraction"

        # No claim was written anywhere as a side effect of this run.
        assert ClaimStore().list_claims() == []
