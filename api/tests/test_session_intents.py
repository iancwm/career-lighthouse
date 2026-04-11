"""Tests for generate_session_intents() — LLM-based intent extraction."""
import json
from unittest.mock import patch, MagicMock
from services.llm import generate_session_intents


def _make_claude_response(json_text):
    """Mock Claude response with structured JSON."""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json_text)]
    return mock_msg


FAKE_CARDS = [
    {
        "card_id": "card-1",
        "domain": "employer",
        "summary": "Update Goldman Sachs EP requirement from EP3 to EP4",
        "diff": {"ep_requirement": "EP4 (raised from EP3 per April 2026 counsellor meeting)"},
        "raw_input_ref": "Goldman raised their EP bar..."
    }
]


@patch("services.llm.get_client")
def test_single_intent_extracted(mock_client):
    """Claude extracts one employer intent from raw notes."""
    raw_input = "Met with Goldman Sachs reps. They raised their EP requirement from EP3 to EP4 starting next intake."

    mock_resp = _make_claude_response(json.dumps({"cards": FAKE_CARDS, "already_covered": []}))
    mock_client.return_value.messages.create.return_value = mock_resp

    result = generate_session_intents(raw_input, existing_tracks=[], existing_employers=[])

    assert len(result["cards"]) == 1
    assert result["cards"][0]["domain"] == "employer"
    assert result["cards"][0]["card_id"] == "card-1"


@patch("services.llm.get_client")
def test_already_covered_returned(mock_client):
    """Claude returns already_covered when content is redundant."""
    raw_input = "Consulting is still competitive this year."

    mock_resp = _make_claude_response(json.dumps({
        "cards": [],
        "already_covered": [{"content": "Consulting competitive", "reason": "Already in profile"}]
    }))
    mock_client.return_value.messages.create.return_value = mock_resp

    result = generate_session_intents(raw_input, existing_tracks=[], existing_employers=[])

    assert len(result["already_covered"]) == 1


@patch("services.llm.get_client")
def test_malformed_json_retries_once(mock_client):
    """If Claude returns bad JSON, we retry with error feedback."""
    raw_input = "Update McKinsey."

    bad_msg = MagicMock()
    bad_msg.content = [MagicMock(text="not json at all")]

    good_msg = MagicMock()
    good_msg.content = [MagicMock(text=json.dumps({"cards": FAKE_CARDS, "already_covered": []}))]

    mock_client.return_value.messages.create.side_effect = [bad_msg, good_msg]

    result = generate_session_intents(raw_input, existing_tracks=[], existing_employers=[])

    assert mock_client.return_value.messages.create.call_count == 2
    assert len(result["cards"]) == 1


@patch("services.llm.get_client")
def test_empty_result_on_total_failure(mock_client):
    """If both attempts fail, return empty result (no exception)."""
    raw_input = "test"
    mock_client.return_value.messages.create.side_effect = Exception("API down")

    result = generate_session_intents(raw_input, existing_tracks=[], existing_employers=[])

    assert result == {"cards": [], "already_covered": []}
