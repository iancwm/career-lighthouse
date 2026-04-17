"""Tests for structured LLM observability logging."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _make_claude_response(text: str):
    mock_resp = MagicMock()
    mock_content = MagicMock()
    mock_content.text = text
    mock_resp.content = [mock_content]
    return mock_resp


@patch("services.llm.get_client")
def test_generate_brief_writes_structured_trace(mock_client, tmp_path):
    import services.llm as llm_module

    trace_path = tmp_path / "logs" / "llm_trace_log.jsonl"
    mock_client.return_value.messages.create.return_value = _make_claude_response("brief text")

    fake_settings = SimpleNamespace(
        anthropic_api_key="fake",
        llm_timeout_seconds=30.0,
        llm_trace_log_path=str(trace_path),
    )

    with patch.object(llm_module, "settings", fake_settings):
        result = llm_module.generate_brief("resume text", [])

    assert result == "brief text"
    with open(trace_path, encoding="utf-8") as handle:
        entry = json.loads(handle.readline())

    assert entry["operation"] == "generate_brief"
    assert entry["status"] == "ok"
    assert entry["model"] == "claude-sonnet-4-6"
    assert entry["output_preview"] == "brief text"
    assert entry["input_chars"] > 0


def test_llm_traces_endpoint_returns_recent_entries(tmp_path):
    from main import app

    trace_path = tmp_path / "logs" / "llm_trace_log.jsonl"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with open(trace_path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "trace_id": "trace-1",
            "ts": "2026-04-17T00:00:00+00:00",
            "operation": "chat_with_context",
            "status": "ok",
            "model": "claude-sonnet-4-6",
            "timeout_seconds": 30.0,
            "max_tokens": 2048,
            "latency_ms": 1234.5,
            "input_chars": 512,
            "output_chars": 128,
            "input_preview": "hello",
            "output_preview": "answer",
            "error": None,
        }) + "\n")
        handle.write(json.dumps({
            "trace_id": "trace-2",
            "ts": "2026-04-17T00:01:00+00:00",
            "operation": "generate_brief",
            "status": "error",
            "model": "claude-sonnet-4-6",
            "timeout_seconds": 30.0,
            "max_tokens": 2048,
            "latency_ms": 3210.0,
            "input_chars": 256,
            "output_chars": 0,
            "input_preview": "resume",
            "output_preview": "",
            "error": "LLM service timeout",
        }) + "\n")

    with patch("routers.kb_router.settings") as mock_settings:
        mock_settings.llm_trace_log_path = str(trace_path)
        client = TestClient(app)
        response = client.get("/api/kb/llm-traces?limit=1")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["trace_id"] == "trace-2"
    assert data[0]["status"] == "error"
