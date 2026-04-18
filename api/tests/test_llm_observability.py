"""Tests for structured LLM observability logging."""
from __future__ import annotations

import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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
        entries = [json.loads(line) for line in handle if line.strip()]

    assert len(entries) == 2
    assert entries[0]["operation"] == "generate_brief"
    assert entries[0]["status"] == "started"
    assert entries[1]["operation"] == "generate_brief"
    assert entries[1]["status"] == "ok"
    assert entries[0]["trace_id"] == entries[1]["trace_id"]
    assert entries[1]["model"] == "claude-sonnet-4-6"
    assert entries[1]["output_preview"] == "brief text"
    assert entries[1]["input_chars"] > 0


def test_llm_traces_endpoint_returns_recent_entries(tmp_path):
    from routers.kb_router import _read_llm_trace_log

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
        data = _read_llm_trace_log(limit=1)

    assert len(data) == 1
    assert data[0].trace_id == "trace-2"
    assert data[0].status == "error"


def test_llm_traces_endpoint_filters_by_session_and_status(tmp_path):
    from routers.kb_router import _read_llm_trace_log

    trace_path = tmp_path / "logs" / "llm_trace_log.jsonl"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with open(trace_path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "trace_id": "trace-1",
            "ts": "2026-04-17T00:00:00+00:00",
            "operation": "generate_brief",
            "status": "started",
            "model": "claude-sonnet-4-6",
            "session_id": "session-a",
            "timeout_seconds": 30.0,
            "max_tokens": 2048,
            "latency_ms": 0.0,
            "input_chars": 100,
            "output_chars": 0,
            "input_preview": "resume",
            "output_preview": "",
            "error": None,
        }) + "\n")
        handle.write(json.dumps({
            "trace_id": "trace-2",
            "ts": "2026-04-17T00:01:00+00:00",
            "operation": "generate_brief",
            "status": "ok",
            "model": "claude-sonnet-4-6",
            "session_id": "session-a",
            "timeout_seconds": 30.0,
            "max_tokens": 2048,
            "latency_ms": 3210.0,
            "input_chars": 256,
            "output_chars": 80,
            "input_preview": "resume",
            "output_preview": "brief",
            "error": None,
        }) + "\n")
        handle.write(json.dumps({
            "trace_id": "trace-3",
            "ts": "2026-04-17T00:02:00+00:00",
            "operation": "chat_with_context",
            "status": "error",
            "model": "claude-sonnet-4-6",
            "session_id": "session-b",
            "timeout_seconds": 30.0,
            "max_tokens": 2048,
            "latency_ms": 111.0,
            "input_chars": 42,
            "output_chars": 0,
            "input_preview": "hello",
            "output_preview": "",
            "error": "LLM service timeout",
        }) + "\n")

    with patch("routers.kb_router.settings") as mock_settings:
        mock_settings.llm_trace_log_path = str(trace_path)
        data = _read_llm_trace_log(limit=10, session_id="session-a", status="ok")

    assert len(data) == 1
    assert data[0].trace_id == "trace-2"
    assert data[0].session_id == "session-a"
    assert data[0].status == "ok"


@patch("services.llm.get_client")
def test_generate_brief_writes_langfuse_observation(mock_client):
    import services.llm as llm_module

    class FakeSpan:
        def __init__(self):
            self.updates = []

        def update(self, **kwargs):
            self.updates.append(kwargs)

    class FakeLangfuseClient:
        def __init__(self):
            self.started = []
            self.flushed = False

        @contextmanager
        def start_as_current_observation(self, **kwargs):
            span = FakeSpan()
            self.started.append(kwargs)
            yield span

        def flush(self):
            self.flushed = True

    fake_langfuse = FakeLangfuseClient()
    mock_client.return_value.messages.create.return_value = _make_claude_response("brief text")

    fake_settings = SimpleNamespace(
        anthropic_api_key="fake",
        llm_timeout_seconds=30.0,
        llm_trace_log_path="/tmp/llm-trace.jsonl",
        langfuse_public_key="pk-lf-test",
        langfuse_secret_key="sk-lf-test",
        langfuse_base_url="http://langfuse-web:3000",
        langfuse_tracing_environment="development",
    )

    @contextmanager
    def fake_propagate_attributes(**kwargs):
        fake_langfuse.propagated = kwargs
        yield

    with patch.object(llm_module, "settings", fake_settings), \
        patch.object(llm_module, "_get_langfuse_client", return_value=fake_langfuse), \
        patch.object(llm_module, "propagate_attributes", side_effect=fake_propagate_attributes), \
        patch.object(llm_module, "_schedule_langfuse_flush", return_value=None):
        result = llm_module.generate_brief("resume text", [])

    assert result == "brief text"
    assert fake_langfuse.started[0]["name"] == "generate_brief"
    assert fake_langfuse.started[0]["model"] == "claude-sonnet-4-6"
    assert fake_langfuse.propagated["trace_name"] == "generate_brief"
    assert fake_langfuse.propagated["version"] == "development"
    assert fake_langfuse.started[0]["input"]["metadata"]["trace_id"]
    assert fake_langfuse.started[0]["input"]["message_count"] == 1
    assert fake_langfuse.started[0]["input"]["system_preview"]
    assert fake_langfuse.started[0]["input"]["system_chars"] > 0
    assert fake_langfuse.started[0]["input"]["max_tokens"] == 2048
    assert fake_langfuse.started[0]["input"]["timeout_seconds"] is None
    assert fake_langfuse.started[0]["input"]["messages"][0]["role"] == "user"
    assert fake_langfuse.started[0]["input"]["messages"][0]["content_preview"]
    assert fake_langfuse.started[0]["input"]["messages"][0]["content_chars"] > 0
    assert fake_langfuse.started[0]["input"]["metadata"]["trace_id"] == fake_langfuse.propagated["metadata"]["trace_id"]
    assert fake_langfuse.flushed is False


@patch("services.llm.get_client")
def test_shutdown_langfuse_traces_shuts_down_client(mock_client):
    import services.llm as llm_module

    class FakeLangfuseClient:
        def __init__(self):
            self.flushed = False
            self.shut_down = False

        def flush(self):
            self.flushed = True

        def shutdown(self):
            self.shut_down = True

    fake_langfuse = FakeLangfuseClient()
    fake_settings = SimpleNamespace(
        anthropic_api_key="fake",
        llm_timeout_seconds=30.0,
        llm_trace_log_path="/tmp/llm-trace.jsonl",
        langfuse_public_key="pk-lf-test",
        langfuse_secret_key="sk-lf-test",
        langfuse_base_url="http://langfuse-web:3000",
        langfuse_tracing_environment="development",
    )

    with patch.object(llm_module, "settings", fake_settings), \
        patch.object(llm_module, "_get_langfuse_client", return_value=fake_langfuse), \
        patch.object(llm_module, "_schedule_langfuse_flush", return_value=None):
        llm_module.shutdown_langfuse_traces()

    assert fake_langfuse.flushed is False
    assert fake_langfuse.shut_down is True
