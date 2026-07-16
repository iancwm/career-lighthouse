# api/tests/test_ontology_extraction.py
"""Unit tests for the ontology extraction pipeline (api/services/ontology_extraction.py).

Milestone 1, Phase 3. Covers Stages 1-4 per docs/ontology/ONTOLOGY-DESIGN.md §5
and docs/ontology/MILESTONE-1.md §3/§9. All LLM calls are mocked at
`services.ontology_extraction.call_structured_json` — the name as imported
into the module under test, not where it is defined in `services.llm` — so
this file makes zero real network/API calls even though `ANTHROPIC_API_KEY`
is set to a dummy value by the autouse `clear_env_secrets` fixture in
conftest.py.

Isolation for the entity/claim/evidence/source-ledger stores comes from the
autouse `reset_ontology_stores`/`reset_source_ledger` fixtures in conftest.py
(tmp-dir-backed, reset per test) — no manual setup needed here.
"""

from datetime import date
from unittest.mock import patch

import services.ontology_extraction as oe
from cfg import kb_cfg
from models_ontology import ApplicationWindowPayload
from services.entity_store import EntityStore


# ---------------------------------------------------------------------------
# Fixture source text
# ---------------------------------------------------------------------------

SOURCE_TEXT = (
    "Deloitte opens applications on 1 September 2026 for the summer analyst "
    "programme. Interviews follow a case-based format."
)
MENTION_TEXT = "Deloitte"
MENTION_START = SOURCE_TEXT.index(MENTION_TEXT)
MENTION_END = MENTION_START + len(MENTION_TEXT)

CLAIM_SPAN_TEXT = "opens applications on 1 September 2026"
CLAIM_SPAN_START = SOURCE_TEXT.index(CLAIM_SPAN_TEXT)
CLAIM_SPAN_END = CLAIM_SPAN_START + len(CLAIM_SPAN_TEXT)


def _stage1_mentions_and_spans() -> oe.MentionExtractionResult:
    return oe.MentionExtractionResult(
        mentions=[
            oe.MentionCandidate(
                text=MENTION_TEXT,
                entity_type="organization",
                character_start=MENTION_START,
                character_end=MENTION_END,
            )
        ],
        claim_spans=[
            oe.ClaimSpanCandidate(
                character_start=CLAIM_SPAN_START, character_end=CLAIM_SPAN_END
            )
        ],
    )


def _stage3_application_window_claim(
    subject_mention_ref: int = 0, evidence_span_refs: list[int] | None = None
) -> oe.ClaimExtractionResult:
    return oe.ClaimExtractionResult(
        claims=[
            oe.ClaimProposal(
                claim_type="application_window",
                subject_mention_ref=subject_mention_ref,
                payload=ApplicationWindowPayload(
                    opens_on=date(2026, 9, 1),
                    date_precision="exact_date",
                    intake_year=2026,
                ),
                extraction_confidence=0.8,
                evidence_span_refs=(
                    evidence_span_refs if evidence_span_refs is not None else [0]
                ),
            )
        ]
    )


def _stage1_stage3_side_effect(stage1_result, stage3_result, stage4_result=None):
    """Build a call_structured_json side_effect that dispatches on `operation`."""

    def _side_effect(*, operation, **kwargs):
        if operation == "ontology_mention_extraction":
            return stage1_result
        if operation == "ontology_claim_extraction":
            return stage3_result
        if operation == "ontology_claim_verification":
            return stage4_result if stage4_result is not None else oe.VerificationResult(
                verified=True, note="looks fine"
            )
        raise AssertionError(f"unexpected operation: {operation}")

    return _side_effect


# ---------------------------------------------------------------------------
# Stage 1 — offsets are sliced server-side from the exact source text
# ---------------------------------------------------------------------------


class TestStage1MentionExtraction:
    @patch("services.ontology_extraction.call_structured_json")
    def test_mentions_have_valid_offsets_into_source_text(self, mock_llm):
        mock_llm.return_value = _stage1_mentions_and_spans()

        result, timed_out = oe.run_stage1_mention_extraction(
            SOURCE_TEXT, timeout_seconds=5.0
        )

        assert timed_out is False
        assert result is not None
        assert len(result.mentions) == 1
        mention = result.mentions[0]
        # The server, not the LLM, is responsible for slicing the excerpt —
        # verify the offsets the LLM returned actually reproduce the mention
        # text when sliced from the exact source text it was given.
        assert (
            SOURCE_TEXT[mention.character_start : mention.character_end]
            == MENTION_TEXT
        )

    @patch("services.ontology_extraction.call_structured_json")
    def test_orchestrator_excerpt_matches_server_side_slice_exactly(self, mock_llm):
        """End-to-end: the Evidence record's excerpt must equal source_text[start:end],
        never anything the LLM might have echoed back as its own 'excerpt' field.
        """
        mock_llm.side_effect = _stage1_stage3_side_effect(
            _stage1_mentions_and_spans(), _stage3_application_window_claim()
        )

        result = oe.extract_claims_for_source(SOURCE_TEXT, "test-source-1")

        assert result.stage1_timed_out is False
        assert len(result.entity_resolutions) == 1
        resolution = result.entity_resolutions[0]
        assert resolution.excerpt == SOURCE_TEXT[MENTION_START:MENTION_END]
        assert resolution.excerpt == MENTION_TEXT


# ---------------------------------------------------------------------------
# Stage 2 — ambiguous resolution must not reach Stage 3
# ---------------------------------------------------------------------------


class TestStage2EntityResolution:
    @patch("services.entity_store.EntityStore.find_candidates")
    @patch("services.ontology_extraction.call_structured_json")
    def test_ambiguous_mention_produces_no_claim_and_skips_stage3(
        self, mock_llm, mock_find_candidates
    ):
        # Two candidates -> ambiguous, per ONTOLOGY-DESIGN.md's deloitte.yaml /
        # deloitte_singapore.yaml discussion: the pipeline must not guess.
        from models_ontology import Entity
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        mock_find_candidates.return_value = [
            Entity(
                entity_id="organization-deloitte",
                entity_type="organization",
                canonical_name="Deloitte",
                created_at=now,
                updated_at=now,
            ),
            Entity(
                entity_id="organization-deloitte_singapore",
                entity_type="organization",
                canonical_name="Deloitte Singapore",
                created_at=now,
                updated_at=now,
            ),
        ]
        mock_llm.return_value = _stage1_mentions_and_spans()

        result = oe.extract_claims_for_source(SOURCE_TEXT, "test-source-2")

        assert len(result.entity_resolutions) == 1
        assert result.entity_resolutions[0].resolution_status == "ambiguous"
        assert result.entity_resolutions[0].candidate_entity_ids == [
            "organization-deloitte",
            "organization-deloitte_singapore",
        ]
        assert result.claim_proposals == []
        # Only Stage 1 should have been called — Stage 3 (claim extraction)
        # must never run when every mention is ambiguous.
        assert mock_llm.call_count == 1
        called_operation = mock_llm.call_args.kwargs["operation"]
        assert called_operation == "ontology_mention_extraction"

    def test_matched_and_proposed_new_resolution(self):
        store = EntityStore()
        store.create_entity("organization", "Deloitte")

        matched_status, matched_id, _, _ = oe.resolve_mention(
            oe.MentionCandidate(
                text="Deloitte",
                entity_type="organization",
                character_start=0,
                character_end=8,
            )
        )
        assert matched_status == "matched"
        assert matched_id == "organization-deloitte"

        new_status, new_id, _, draft = oe.resolve_mention(
            oe.MentionCandidate(
                text="Totally New Employer Pte Ltd",
                entity_type="organization",
                character_start=0,
                character_end=10,
            )
        )
        assert new_status == "proposed_new"
        assert new_id is None
        assert draft is not None
        assert draft["canonical_name"] == "Totally New Employer Pte Ltd"


# ---------------------------------------------------------------------------
# Claim proposals must carry evidence that is a literal substring of source
# ---------------------------------------------------------------------------


class TestEvidenceSubstringInvariant:
    @patch("services.ontology_extraction.call_structured_json")
    def test_every_claim_proposal_has_evidence_excerpt_substring_of_source(
        self, mock_llm
    ):
        mock_llm.side_effect = _stage1_stage3_side_effect(
            _stage1_mentions_and_spans(), _stage3_application_window_claim()
        )

        result = oe.extract_claims_for_source(SOURCE_TEXT, "test-source-3")

        assert len(result.claim_proposals) == 1
        proposal = result.claim_proposals[0]
        assert len(proposal.evidence_excerpts) >= 1
        assert any(excerpt in SOURCE_TEXT for excerpt in proposal.evidence_excerpts)
        assert proposal.verification_status == "verified"


# ---------------------------------------------------------------------------
# Stage 4 — deterministic substring check rejects fabricated evidence
# ---------------------------------------------------------------------------


class TestStage4Verification:
    def _base_record(self, evidence_excerpts: list[str]) -> "oe.ClaimProposalResult":
        return oe.ClaimProposalResult(
            claim_type="application_window",
            subject_entity_id="organization-deloitte",
            subject_mention_text="Deloitte",
            subject_resolution_status="matched",
            payload=ApplicationWindowPayload(
                opens_on=date(2026, 9, 1), date_precision="exact_date"
            ),
            scope=oe.ClaimScope(),
            assertion_status="inferred",
            extraction_confidence=0.8,
            evidence_ids=["evidence-fake"],
            evidence_excerpts=evidence_excerpts,
            verification_status="rejected",
        )

    @patch("services.ontology_extraction.call_structured_json")
    def test_evidence_not_substring_of_source_is_rejected_without_llm_call(
        self, mock_llm
    ):
        record = self._base_record(["this text was never in the source document"])

        verified = oe.run_stage4_verification(
            record, SOURCE_TEXT, timeout_seconds=5.0
        )

        assert verified.verification_status == "rejected"
        assert verified.verification_note is not None
        # The deterministic check must short-circuit — no LLM call for a claim
        # whose evidence isn't real.
        mock_llm.assert_not_called()

    @patch("services.ontology_extraction.call_structured_json")
    def test_evidence_substring_of_source_passes_deterministic_check(self, mock_llm):
        mock_llm.return_value = oe.VerificationResult(verified=True, note=None)
        record = self._base_record([CLAIM_SPAN_TEXT])

        verified = oe.run_stage4_verification(
            record, SOURCE_TEXT, timeout_seconds=5.0
        )

        assert verified.verification_status == "verified"
        mock_llm.assert_called_once()

    @patch("services.ontology_extraction.call_structured_json")
    def test_soft_verification_false_rejects_claim(self, mock_llm):
        mock_llm.return_value = oe.VerificationResult(
            verified=False, note="date does not match evidence"
        )
        record = self._base_record([CLAIM_SPAN_TEXT])

        verified = oe.run_stage4_verification(
            record, SOURCE_TEXT, timeout_seconds=5.0
        )

        assert verified.verification_status == "rejected"
        assert verified.verification_note == "date does not match evidence"


# ---------------------------------------------------------------------------
# Timeout fallbacks — Stage 1 aborts extraction; Stage 4 never fails open
# ---------------------------------------------------------------------------


class TestTimeoutFallbacks:
    @patch("services.ontology_extraction.call_structured_json")
    def test_stage1_timeout_returns_safe_empty_result(self, mock_llm):
        mock_llm.side_effect = TimeoutError("simulated Stage 1 timeout")

        result = oe.extract_claims_for_source(SOURCE_TEXT, "test-source-4")

        assert result.stage1_timed_out is True
        assert result.entity_resolutions == []
        assert result.claim_proposals == []

    @patch("services.ontology_extraction.call_structured_json")
    def test_stage3_timeout_returns_safe_result_with_resolutions_but_no_claims(
        self, mock_llm
    ):
        def _side_effect(*, operation, **kwargs):
            if operation == "ontology_mention_extraction":
                return _stage1_mentions_and_spans()
            if operation == "ontology_claim_extraction":
                raise TimeoutError("simulated Stage 3 timeout")
            raise AssertionError(f"unexpected operation: {operation}")

        mock_llm.side_effect = _side_effect

        result = oe.extract_claims_for_source(SOURCE_TEXT, "test-source-5")

        assert result.stage3_timed_out is True
        assert len(result.entity_resolutions) == 1
        assert result.claim_proposals == []

    @patch("services.ontology_extraction.call_structured_json")
    def test_stage4_verification_timeout_is_not_silently_verified(self, mock_llm):
        record = TestStage4Verification()._base_record([CLAIM_SPAN_TEXT])
        mock_llm.side_effect = TimeoutError("simulated Stage 4 timeout")

        verified = oe.run_stage4_verification(
            record, SOURCE_TEXT, timeout_seconds=5.0
        )

        assert verified.verification_status == "unverified_timeout"
        assert verified.verification_status != "verified"

    @patch("services.ontology_extraction.call_structured_json")
    def test_end_to_end_stage4_timeout_surfaces_unverified_not_verified(
        self, mock_llm
    ):
        def _side_effect(*, operation, **kwargs):
            if operation == "ontology_mention_extraction":
                return _stage1_mentions_and_spans()
            if operation == "ontology_claim_extraction":
                return _stage3_application_window_claim()
            if operation == "ontology_claim_verification":
                raise TimeoutError("simulated Stage 4 timeout")
            raise AssertionError(f"unexpected operation: {operation}")

        mock_llm.side_effect = _side_effect

        result = oe.extract_claims_for_source(SOURCE_TEXT, "test-source-6")

        assert len(result.claim_proposals) == 1
        assert result.claim_proposals[0].verification_status == "unverified_timeout"


# ---------------------------------------------------------------------------
# Config: extraction must default to disabled
# ---------------------------------------------------------------------------


def test_ontology_extraction_disabled_by_default_in_checked_in_config():
    assert kb_cfg["ontology"]["extraction_enabled"] is False
