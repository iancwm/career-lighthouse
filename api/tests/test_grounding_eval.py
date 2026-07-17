# api/tests/test_grounding_eval.py
"""Milestone 2 grounding eval — real-LLM check that a VERIFIED CLAIMS block
actually changes model behavior (citation, not just prompt construction).

Per docs/ontology/SPRINT-M2-TASKS.md Task 15 (ENG-T7) / GROUNDING-DESIGN.md's
"Eval test (required)": given a fixture of 3 approved Goldman SG
recruitment_stage claims, chat_with_context() should produce a response that
cites the knowledge base rather than answering purely from training data.

Marked @pytest.mark.eval (same shape as test_ai_eval.py's @pytest.mark.integration
tests) so it never runs in the standard CI suite — it makes a real Anthropic API
call and is skipped automatically when ANTHROPIC_API_KEY is not set.

Run locally:
    uv run --extra dev python -m pytest tests/test_grounding_eval.py -v -m eval
"""

from datetime import date, datetime, timezone

import pytest

pytestmark = pytest.mark.eval


def _confidence(**overrides):
    base = dict(extraction=0.9, evidence_strength=0.85, source_reliability=0.8)
    base.update(overrides)
    from models_ontology import ClaimConfidence

    return ClaimConfidence(**base)


def _observation_time(**overrides):
    from models_ontology import ClaimObservationTime

    base = dict(observed_at=date(2026, 6, 1), recorded_at=datetime(2026, 6, 1, tzinfo=timezone.utc))
    base.update(overrides)
    return ClaimObservationTime(**base)


def _goldman_sg_claim(claim_id: str, stage_name: str, sequence: int, stage_type: str, modality: str):
    from models_ontology import Claim, ClaimScope, RecruitmentStagePayload

    return Claim(
        claim_id=claim_id,
        claim_type="recruitment_stage",
        subject_entity_id="organization-goldman_sachs",
        payload=RecruitmentStagePayload(
            stage_name=stage_name,
            sequence=sequence,
            stage_type=stage_type,
            modality=modality,
        ),
        scope=ClaimScope(geography="SG"),
        observation_time=_observation_time(),
        assertion_status="asserted",
        confidence=_confidence(),
        evidence_ids=[f"evidence-{claim_id}"],
        review_status="approved",
    )


@pytest.fixture
def goldman_sg_claim_context():
    from models_ontology import ClaimContext

    claims = [
        _goldman_sg_claim(
            "claim-goldman-sg-1",
            "Online application",
            1,
            "application",
            "online",
        ),
        _goldman_sg_claim(
            "claim-goldman-sg-2",
            "HireVue video interview",
            2,
            "recruiter_screen",
            "video",
        ),
        _goldman_sg_claim(
            "claim-goldman-sg-3",
            "Superday final round",
            3,
            "assessment_centre",
            "onsite",
        ),
    ]
    return ClaimContext(
        entity_id="organization-goldman_sachs",
        entity_name="Goldman Sachs Singapore",
        claims=claims,
        coverage_confidence="high",
    )


@pytest.fixture(scope="module")
def real_llm_client():
    """Real Anthropic client (not mocked) — module-scoped so this fixture's
    `settings` import resolves BEFORE the function-scoped autouse
    `clear_env_secrets` fixture (conftest.py) monkeypatches ANTHROPIC_API_KEY
    to a dummy value for each test. Pytest sets up broader-scoped fixtures
    first, so this ordering reliably skips in sandboxes with no real key —
    mirroring test_ai_eval.py's `real_llm_client` fixture exactly. A
    function-scoped check here would import `config` too late (after the
    dummy key is already set) and attempt a real call that 401s instead of
    skipping.
    """
    from config import settings

    if not settings.anthropic_api_key:
        pytest.skip("Anthropic API key not set")


class TestGroundingEval:
    def test_verified_claims_block_produces_kb_attributed_response(
        self, goldman_sg_claim_context, real_llm_client
    ):
        """Gold query: 'What are Goldman's interview stages in Singapore?' with
        3 approved recruitment_stage claims injected should produce a response
        that attributes the answer to the knowledge base, not just general
        training-data knowledge.
        """
        from services.llm import chat_with_context

        response = chat_with_context(
            message="What are Goldman's interview stages in Singapore?",
            resume_text=None,
            chunks=[],
            history=[],
            claim_context=goldman_sg_claim_context,
        )

        lowered = response.lower()
        expected_phrases = ["knowledge base", "per our knowledge base", "based on our records"]
        assert any(phrase in lowered for phrase in expected_phrases), (
            "Expected the grounded response to cite the knowledge base. "
            f"Got: {response!r}"
        )

    def test_no_matching_claims_signals_general_knowledge(self, real_llm_client):
        """Success criterion 2: a question with no matching approved claims
        (claim_context=None, existing chat behavior) must not fabricate a KB
        citation — it should read as general knowledge, not KB-grounded.
        """
        from services.llm import chat_with_context

        response = chat_with_context(
            message="What are Goldman's interview stages in Singapore?",
            resume_text=None,
            chunks=[],
            history=[],
            claim_context=None,
        )

        lowered = response.lower()
        assert "per our knowledge base" not in lowered
        assert "based on our records" not in lowered
