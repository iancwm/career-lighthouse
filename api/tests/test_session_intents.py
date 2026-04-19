"""Tests for generate_session_intents() — LLM-based intent extraction."""
import json
from types import SimpleNamespace
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
    """If Claude returns bad JSON, we repair the model output instead of replaying the full prompt."""
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
def test_malformed_json_recovers_on_second_repair_attempt(mock_client):
    """A bad repair response should get one more repair attempt before collapsing to empty."""
    raw_input = "Update McKinsey."

    bad_msg = MagicMock()
    bad_msg.content = [MagicMock(text="not json at all")]

    still_bad_msg = MagicMock()
    still_bad_msg.content = [MagicMock(text='{"cards": [')]

    good_msg = MagicMock()
    good_msg.content = [MagicMock(text=json.dumps({"cards": FAKE_CARDS, "already_covered": []}))]

    mock_client.return_value.messages.create.side_effect = [bad_msg, still_bad_msg, good_msg]

    result = generate_session_intents(raw_input, existing_tracks=[], existing_employers=[])

    assert mock_client.return_value.messages.create.call_count == 3
    assert len(result["cards"]) == 1


@patch("services.llm.get_client")
def test_session_intents_use_json_only_prompt(mock_client):
    """The repair pass should use a dedicated JSON-repair prompt, not the original system prompt."""
    raw_input = "Update McKinsey."

    bad_msg = MagicMock()
    bad_msg.content = [MagicMock(text="not json at all")]

    good_msg = MagicMock()
    good_msg.content = [MagicMock(text=json.dumps({"cards": FAKE_CARDS, "already_covered": []}))]

    mock_client.return_value.messages.create.side_effect = [bad_msg, good_msg]

    generate_session_intents(raw_input, existing_tracks=[], existing_employers=[])

    first_call_system = mock_client.return_value.messages.create.call_args_list[0].kwargs["system"]
    repair_call_system = mock_client.return_value.messages.create.call_args_list[1].kwargs["system"]

    assert "Return valid JSON with this structure" in first_call_system
    assert repair_call_system != first_call_system
    assert "You repair malformed JSON" in repair_call_system


@patch("services.llm.get_client")
def test_session_intents_prompt_forbids_nested_diff_objects(mock_client):
    """Session extraction prompts should require flat diff objects for UI/commit safety."""
    raw_input = "Update McKinsey."

    mock_resp = _make_claude_response(json.dumps({"cards": [], "already_covered": []}))
    mock_client.return_value.messages.create.return_value = mock_resp

    generate_session_intents(raw_input, existing_tracks=[], existing_employers=[])

    first_call_system = mock_client.return_value.messages.create.call_args_list[0].kwargs["system"]
    assert len(mock_client.return_value.messages.create.call_args_list) == 1

    assert "diff MUST be a flat object" in first_call_system
    assert "Never emit nested objects or arrays of objects" in first_call_system


@patch("services.llm.get_client")
def test_empty_result_on_total_failure(mock_client):
    """If both attempts fail, return empty result (no exception)."""
    raw_input = "test"
    mock_client.return_value.messages.create.side_effect = Exception("API down")

    result = generate_session_intents(raw_input, existing_tracks=[], existing_employers=[])

    assert result == {"cards": [], "already_covered": []}


@patch("services.llm.get_client")
def test_context_includes_existing_tracks_and_employers(mock_client):
    """Existing tracks and employers are included in the LLM context."""
    tracks = [{"career_type": "Finance", "match_description": "Banking track"}]
    employers = [{"slug": "gs", "tracks": ["finance"], "ep_requirement": "EP4"}]

    mock_resp = _make_claude_response(json.dumps({"cards": [], "already_covered": []}))
    mock_client.return_value.messages.create.return_value = mock_resp

    generate_session_intents("test", existing_tracks=tracks, existing_employers=employers)

    call_kwargs = mock_client.return_value.messages.create.call_args.kwargs
    messages = call_kwargs.get("messages", [])
    context_text = messages[0]["content"] if messages else ""
    assert "Finance" in context_text
    assert "gs" in context_text
    assert "EP4" in context_text


@patch("services.llm.get_client")
def test_missing_cards_key_returns_empty(mock_client):
    """If Claude returns valid JSON but without 'cards' key, return empty."""
    mock_resp = _make_claude_response(json.dumps({"already_covered": []}))
    mock_client.return_value.messages.create.return_value = mock_resp

    result = generate_session_intents("test", existing_tracks=[], existing_employers=[])

    assert result == {"cards": [], "already_covered": []}


@patch("services.llm.get_client")
def test_session_intents_uses_extended_timeout(mock_client):
    """Session extraction should use a longer timeout and skip client retries."""
    mock_resp = _make_claude_response(json.dumps({"cards": [], "already_covered": []}))
    mock_client.return_value.messages.create.return_value = mock_resp

    generate_session_intents("test", existing_tracks=[], existing_employers=[])

    assert mock_client.call_args.kwargs["max_retries"] == 0
    call_kwargs = mock_client.return_value.messages.create.call_args.kwargs
    assert call_kwargs["timeout"] == 180.0


@patch("services.llm.get_client")
def test_session_intents_trace_carries_session_metadata(mock_client, tmp_path):
    """Session extraction traces should identify the session and phase."""
    import services.llm as llm_module

    trace_path = tmp_path / "logs" / "llm_trace_log.jsonl"
    mock_client.return_value.messages.create.return_value = _make_claude_response(
        json.dumps({"cards": [], "already_covered": []})
    )
    fake_settings = SimpleNamespace(
        anthropic_api_key="fake",
        allowed_origins="http://localhost:3000",
        qdrant_url="",
        data_path=llm_module.settings.data_path,
        query_log_path=llm_module.settings.query_log_path,
        llm_trace_log_path=str(trace_path),
        max_upload_bytes=llm_module.settings.max_upload_bytes,
        admin_key="",
        llm_timeout_seconds=30.0,
        llm_session_timeout_seconds=90.0,
    )

    with patch.object(llm_module, "settings", fake_settings):
        generate_session_intents(
            "test",
            existing_tracks=[],
            existing_employers=[],
            session_id="session-123",
        )

    with open(trace_path, encoding="utf-8") as handle:
        entries = [json.loads(line) for line in handle if line.strip()]

    assert entries[0]["session_id"] == "session-123"
    assert entries[0]["phase"] == "session_analysis"
    assert entries[1]["session_id"] == "session-123"
    assert entries[1]["phase"] == "session_analysis"


@patch("services.llm.get_client")
@patch("services.llm.chunk_text")
def test_session_intents_multi_pass_trace_metadata(mock_chunk, mock_client, tmp_path):
    """Multi-pass session extraction should label each chunk in the trace."""
    import services.llm as llm_module

    trace_path = tmp_path / "logs" / "llm_trace_log.jsonl"
    mock_chunk.return_value = ["a", "b"]
    mock_client.return_value.messages.create.return_value = _make_claude_response(
        json.dumps(
            {
                "cards": [{
                    "card_id": "card-1",
                    "domain": "track",
                    "summary": "Chunk output",
                    "diff": {"slug": "chunk_output"},
                    "raw_input_ref": "chunk-one",
                }],
                "already_covered": [],
            }
        )
    )
    fake_settings = SimpleNamespace(
        anthropic_api_key="fake",
        allowed_origins="http://localhost:3000",
        qdrant_url="",
        data_path=llm_module.settings.data_path,
        query_log_path=llm_module.settings.query_log_path,
        llm_trace_log_path=str(trace_path),
        max_upload_bytes=llm_module.settings.max_upload_bytes,
        admin_key="",
        llm_timeout_seconds=30.0,
        llm_session_timeout_seconds=90.0,
        llm_session_multi_pass_threshold_chars=1,
        llm_session_multi_pass_chunk_tokens=1,
        llm_session_multi_pass_overlap_tokens=0,
    )

    with patch.object(llm_module, "settings", fake_settings):
        generate_session_intents(
            "x" * 3,
            existing_tracks=[],
            existing_employers=[],
            session_id="session-456",
        )

    with open(trace_path, encoding="utf-8") as handle:
        entries = [json.loads(line) for line in handle if line.strip()]

    phases = {(entry["phase"], entry.get("chunk_index"), entry.get("chunk_count")) for entry in entries}
    assert ("multi_pass_chunk", 1, 2) in phases
    assert ("multi_pass_chunk", 2, 2) in phases
    assert all(entry["multi_pass_threshold_chars"] == 1 for entry in entries)
    assert all(entry["feature"] == "generate_session_intents" for entry in entries)
    assert all(entry["input_chars_pre_trim"] > 0 for entry in entries)
    assert all(entry["parse_attempt"] == 1 for entry in entries)
    assert all(entry["repair_attempt"] == 0 for entry in entries)
