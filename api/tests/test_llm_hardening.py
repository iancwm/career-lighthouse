import json
from unittest.mock import MagicMock, patch

from services.llm import _merge_intents, generate_session_intents


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

    result = generate_session_intents(large_input, existing_tracks=[], existing_employers=[])

    assert len(result["cards"]) == 2
    assert result["cards"][0]["card_id"] == "c1"
    assert result["cards"][1]["card_id"] != "c1"


def test_merge_intents_deduplication():
    """_merge_intents deduplicates based on normalized summary + slug + domain."""
    results = [
        {
            "cards": [
                {"domain": "employer", "summary": "Add Stripe", "diff": {"slug": "stripe"}, "card_id": "c1"}
            ]
        },
        {
            "cards": [
                {"domain": "employer", "summary": "Add Stripe (again)", "diff": {"slug": "stripe"}, "card_id": "c2"},
                {"domain": "track", "summary": "New Track", "diff": {"slug": "new_track"}, "card_id": "c3"},
            ]
        },
    ]

    merged = _merge_intents(results)
    assert len(merged["cards"]) == 3
    assert merged["cards"][0]["card_id"] == "c1"
    assert any(card["domain"] == "track" for card in merged["cards"])
    assert any(card["card_id"] != "c1" for card in merged["cards"])

    merged_identical = _merge_intents([
        {
            "cards": [
                {"domain": "employer", "summary": "Add Stripe", "diff": {"slug": "stripe"}, "card_id": "c1"}
            ]
        },
        {
            "cards": [
                {"domain": "employer", "summary": "Add Stripe", "diff": {"slug": "stripe"}, "card_id": "c2"}
            ]
        },
    ])
    assert len(merged_identical["cards"]) == 1
    assert merged_identical["cards"][0]["card_id"] == "c1"
