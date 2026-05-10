from unittest.mock import MagicMock, patch

from services.llm import (
    MergeSpec,
    ListMergeRule,
    _merge_analysis_results,
    _merge_intents,
    _merge_track_drafts,
    generate_session_intents,
    merge_chunked_results,
)


def _make_claude_response(text):
    mock_resp = MagicMock()
    mock_content = MagicMock()
    mock_content.text = text
    mock_resp.content = [mock_content]
    return mock_resp


@patch("services.llm.get_client")
@patch("services.llm.chunk_text")
def test_multi_pass_triggered_for_large_doc(mock_chunk, mock_client):
    """Large documents trigger multi-pass extraction."""
    large_input = "A" * 30001
    mock_chunk.return_value = ["chunk1", "chunk2"]

    # Mock responses for two chunks.
    resp1 = """```json
{"cards": [{"card_id": "c1", "domain": "employer", "summary": "s1", "diff": {"slug": "e1"}, "raw_input_ref": "r1"}], "already_covered": []}
```"""
    resp2 = """```json
{"cards": [{"card_id": "c2", "domain": "employer", "summary": "s2", "diff": {"slug": "e2"}, "raw_input_ref": "r2"}], "already_covered": []}
```"""

    mock_client.return_value.messages.create.side_effect = [
        _make_claude_response(resp1),
        _make_claude_response(resp2),
    ]

    result = generate_session_intents(
        large_input, existing_tracks=[], existing_employers=[]
    )

    assert len(result["cards"]) == 2
    assert result["cards"][0]["card_id"] == "c1"
    assert result["cards"][1]["card_id"] != "c1"


def test_merge_intents_deduplication():
    """_merge_intents deduplicates based on normalized summary + slug + domain."""
    results = [
        {
            "cards": [
                {
                    "domain": "employer",
                    "summary": "Add Stripe",
                    "diff": {"slug": "stripe"},
                    "card_id": "c1",
                }
            ]
        },
        {
            "cards": [
                {
                    "domain": "employer",
                    "summary": "Add Stripe (again)",
                    "diff": {"slug": "stripe"},
                    "card_id": "c2",
                },
                {
                    "domain": "track",
                    "summary": "New Track",
                    "diff": {"slug": "new_track"},
                    "card_id": "c3",
                },
            ]
        },
    ]

    merged = _merge_intents(results)
    assert len(merged["cards"]) == 3
    assert merged["cards"][0]["card_id"] == "c1"
    assert any(card["domain"] == "track" for card in merged["cards"])
    assert any(card["card_id"] != "c1" for card in merged["cards"])

    merged_identical = _merge_intents(
        [
            {
                "cards": [
                    {
                        "domain": "employer",
                        "summary": "Add Stripe",
                        "diff": {"slug": "stripe"},
                        "card_id": "c1",
                    }
                ]
            },
            {
                "cards": [
                    {
                        "domain": "employer",
                        "summary": "Add Stripe",
                        "diff": {"slug": "stripe"},
                        "card_id": "c2",
                    }
                ]
            },
        ]
    )
    assert len(merged_identical["cards"]) == 1
    assert merged_identical["cards"][0]["card_id"] == "c1"


def test_merge_chunked_results_merges_declared_lists_and_dicts():
    merged = merge_chunked_results(
        [
            {
                "items": [{"slug": "a", "value": 1}],
                "nested": {"alpha": {"x": 1}},
                "status": "draft",
            },
            {
                "items": [{"slug": "a", "value": 99}, {"slug": "b", "value": 2}],
                "nested": {"alpha": {"y": 2}, "beta": {"z": 3}},
                "status": "published",
            },
        ],
        MergeSpec(
            initial={"items": [], "nested": {}},
            list_fields={
                "items": ListMergeRule(
                    dedupe_key=lambda item: (
                        item.get("slug") if isinstance(item, dict) else None
                    )
                )
            },
            dict_fields={"nested"},
        ),
    )

    assert merged["items"] == [{"slug": "a", "value": 1}, {"slug": "b", "value": 2}]
    assert merged["nested"] == {"alpha": {"x": 1, "y": 2}, "beta": {"z": 3}}
    assert merged["status"] == "published"


def test_merge_analysis_and_track_drafts_preserve_existing_semantics():
    analysis = _merge_analysis_results(
        [
            {
                "interpretation_bullets": [" Add Stripe headcount context "],
                "profile_updates": {"data_science": {"entry_paths": ["Internship"]}},
                "employer_updates": {"stripe": {"ep_requirement": "Yes"}},
                "new_chunks": [
                    {
                        "text": "Stripe hires SWE interns.",
                        "source_type": "note",
                        "source_label": "memo-1",
                        "career_type": "software_engineering",
                    }
                ],
                "already_covered": [
                    {"content": "Stripe hires interns", "reason": "KB"}
                ],
            },
            {
                "interpretation_bullets": ["Add Stripe headcount context"],
                "profile_updates": {"data_science": {"top_employers_smu": ["Stripe"]}},
                "employer_updates": {"stripe": {"headcount_estimate": "200+"}},
                "new_chunks": [
                    {
                        "text": "Stripe hires SWE interns.",
                        "source_type": "note",
                        "source_label": "memo-1",
                        "career_type": "software_engineering",
                    }
                ],
                "already_covered": [
                    {"excerpt": "Stripe hires interns", "source_doc": "KB"}
                ],
            },
        ]
    )

    assert analysis["interpretation_bullets"] == [" Add Stripe headcount context "]
    assert analysis["profile_updates"]["data_science"]["entry_paths"] == ["Internship"]
    assert analysis["profile_updates"]["data_science"]["top_employers_smu"] == [
        "Stripe"
    ]
    assert analysis["employer_updates"]["stripe"]["ep_requirement"] == "Yes"
    assert analysis["employer_updates"]["stripe"]["headcount_estimate"] == "200+"
    assert len(analysis["new_chunks"]) == 1
    assert len(analysis["already_covered"]) == 1

    draft = _merge_track_drafts(
        [
            {
                "match_keywords": ["sql", "python"],
                "structured": {"hiring_bar": "high"},
                "notes": "first pass",
            },
            {
                "match_keywords": ["python", "spark"],
                "structured": {"team_size": "mid"},
                "notes": "second pass",
            },
        ]
    )

    assert draft["match_keywords"] == ["sql", "python", "spark"]
    assert draft["structured"] == {"hiring_bar": "high", "team_size": "mid"}
    assert draft["notes"] == "second pass"
