from pydantic import ValidationError

from models_kb import IntentCard, validate_intent_card_diff


def test_intent_card_accepts_alumni_domain():
    card = IntentCard(
        card_id="alumni-card-1",
        domain="alumni",
        summary="Create alumni profile for Maya Lim",
        diff={
            "slug": "maya-lim",
            "full_name": "Maya Lim",
            "name": "Maya Lim",
            "graduation_school": "SMU",
            "current_company": "Grab",
            "available_for_mentoring": "no",
            "career_goals_domains": "Product management, growth",
            "mentoring_modes": "coffee chat",
            "consent_for_referrals": "maybe",
            "can_refer_confidence": "low",
            "lifecycle": "active",
        },
        raw_input_ref="Maya now works at Grab.",
    )

    assert card.domain == "alumni"
    assert card.diff["available_for_mentoring"] == "no"
    assert card.diff["career_goals_domains"] == "Product management, growth"
    assert card.diff["graduation_school"] == "SMU"
    assert card.diff["lifecycle"] == "active"
    assert card.proposals == {}


def test_intent_card_accepts_singapore_headcount_estimate_for_employer_cards():
    card = IntentCard(
        card_id="employer-card-1",
        domain="employer",
        summary="Update Instacart Singapore",
        diff={
            "slug": "instacart_singapore",
            "employer_name": "Instacart Singapore",
            "singapore_headcount_estimate": "80-100",
        },
        raw_input_ref="Instacart expanded the Singapore credit risk team.",
    )

    assert card.diff["singapore_headcount_estimate"] == "80-100"


def test_validate_intent_card_diff_normalizes_legacy_headcount_estimate():
    diff = validate_intent_card_diff(
        "employer",
        {
            "slug": "instacart_singapore",
            "headcount_estimate": 120,
        },
    )

    assert diff["singapore_headcount_estimate"] == 120
    assert "headcount_estimate" not in diff


def test_validate_intent_card_diff_rejects_unknown_alumni_field():
    try:
        validate_intent_card_diff(
            "alumni",
            {
                "slug": "maya-lim",
                "full_name": "Maya Lim",
                "is_update": True,
            },
        )
    except ValidationError:
        return
    assert False, "Expected ValidationError for unexpected alumni diff field"


def test_intent_card_rejects_extra_alumni_diff_fields():
    try:
        IntentCard(
            card_id="alumni-card-2",
            domain="alumni",
            summary="Bad alumni diff",
            diff={
                "slug": "maya-lim",
                "full_name": "Maya Lim",
                "unexpected_field": "nope",
            },
            raw_input_ref="Maya note",
        )
    except ValidationError:
        return
    assert False, "Expected ValidationError for extra alumni diff field"
