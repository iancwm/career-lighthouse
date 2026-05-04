"""Tests for structured LLM observability logging."""
from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

def _make_claude_response(text: str):
    mock_resp = MagicMock()
    mock_content = MagicMock()
    mock_content.text = text
    mock_resp.content = [mock_content]
    return mock_resp


def test_anthropic_model_env_override_wins():
    import services.llm as llm_module

    fake_settings = SimpleNamespace(anthropic_model="claude-opus-4-1")
    with patch.object(llm_module, "settings", fake_settings):
        assert llm_module.get_model_name() == "claude-opus-4-1"


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
    assert entries[1]["feature"] == "generate_brief"
    assert entries[0]["trace_id"] == entries[1]["trace_id"]
    assert entries[1]["model"] == "claude-sonnet-4-6"
    assert entries[1]["output_preview"] == "brief text"
    assert entries[1]["input_chars"] > 0
    assert entries[1]["input_chars_pre_trim"] > 0
    assert entries[1]["input_chars_sent"] >= entries[1]["input_chars_pre_trim"]
    assert entries[1]["kb_chunks_retrieved"] == 0
    assert entries[1]["kb_chunks_sent"] == 0


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
            "feature": "chat_with_context",
            "timeout_seconds": 30.0,
            "max_tokens": 2048,
            "latency_ms": 1234.5,
            "input_chars": 512,
            "input_chars_pre_trim": 640,
            "input_chars_sent": 512,
            "kb_chunks_retrieved": 4,
            "kb_chunks_sent": 2,
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
            "feature": "generate_brief",
            "timeout_seconds": 30.0,
            "max_tokens": 2048,
            "latency_ms": 3210.0,
            "input_chars": 256,
            "input_chars_pre_trim": 256,
            "input_chars_sent": 256,
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
    assert data[0].feature == "generate_brief"
    assert data[0].input_chars_pre_trim == 256
    assert data[0].input_chars_sent == 256


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
def test_generate_alumni_extraction_writes_structured_trace(mock_client, tmp_path):
    import services.llm as llm_module

    trace_path = tmp_path / "logs" / "llm_trace_log.jsonl"
    mock_client.return_value.messages.create.return_value = _make_claude_response(
        json.dumps(
            {
                "summary_bullets": ["Maya mentors product students from Grab."],
                "profile_proposals": {
                    "current_title": {
                        "value": "Senior Product Lead",
                        "confidence": 91,
                        "evidence": ["Senior Product Lead at Grab"],
                        "rationale": "Explicitly stated in the note.",
                    }
                },
                "company_link_proposals": [
                    {
                        "company_slug": "grab",
                        "company_name": "Grab",
                        "role_title": "Senior Product Lead",
                        "link_type": "current",
                        "confidence": 91,
                        "evidence": ["Senior Product Lead at Grab"],
                        "rationale": "Current employer relationship.",
                    }
                ],
                "fit_triad": {},
                "source_label": "counsellor_note",
                "source_type": "note",
                "is_update": True,
                "matched_slug": "maya_lim",
                "source_excerpt": "Maya is a Senior Product Lead at Grab and can mentor product students.",
                "alumni": [
                    {
                        "summary_bullets": ["Maya mentors product students from Grab."],
                        "profile_proposals": {
                            "current_title": {
                                "value": "Senior Product Lead",
                                "confidence": 91,
                                "evidence": ["Senior Product Lead at Grab"],
                                "rationale": "Explicitly stated in the note.",
                            }
                        },
                        "company_link_proposals": [
                            {
                                "company_slug": "grab",
                                "company_name": "Grab",
                                "role_title": "Senior Product Lead",
                                "link_type": "current",
                                "confidence": 91,
                                "evidence": ["Senior Product Lead at Grab"],
                                "rationale": "Current employer relationship.",
                            }
                        ],
                        "fit_triad": {},
                        "source_label": "counsellor_note",
                        "source_type": "note",
                        "is_update": True,
                        "matched_slug": "maya_lim",
                        "source_excerpt": "Maya is a Senior Product Lead at Grab and can mentor product students.",
                    }
                ],
            }
        )
    )

    fake_settings = SimpleNamespace(
        anthropic_api_key="fake",
        llm_timeout_seconds=30.0,
        llm_trace_log_path=str(trace_path),
    )

    with patch.object(llm_module, "settings", fake_settings):
        result = llm_module.generate_alumni_extraction(
            "Maya is a Senior Product Lead at Grab and can mentor product students.",
            [{"slug": "maya_lim", "full_name": "Maya Lim", "current_company": "Grab"}],
            "session-123",
        )

    assert result["matched_slug"] == "maya_lim"
    assert result["alumni"][0]["source_excerpt"].startswith("Maya is a Senior Product Lead")
    with open(trace_path, encoding="utf-8") as handle:
        entries = [json.loads(line) for line in handle if line.strip()]

    assert len(entries) == 2
    assert entries[0]["operation"] == "generate_alumni_extraction"
    assert entries[1]["operation"] == "generate_alumni_extraction"
    assert entries[1]["feature"] == "generate_alumni_extraction"
    assert entries[1]["session_id"] == "session-123"
    assert entries[1]["existing_alumni_count"] == 1


def test_call_with_trace_writes_error_row_for_unexpected_exception(tmp_path):
    import services.llm as llm_module

    trace_path = tmp_path / "logs" / "llm_trace_log.jsonl"
    fake_settings = SimpleNamespace(
        anthropic_api_key="fake",
        llm_timeout_seconds=30.0,
        llm_trace_log_path=str(trace_path),
        langfuse_public_key="",
        langfuse_secret_key="",
        langfuse_base_url="",
        langfuse_host="",
    )

    with patch.object(llm_module, "settings", fake_settings), patch.object(
        llm_module,
        "_safe_create",
        side_effect=RuntimeError("client blew up"),
    ):
        try:
            llm_module._call_with_trace(
                operation="generate_alumni_extraction",
                model="claude-sonnet-4-6",
                max_tokens=512,
                system="Return JSON",
                messages=[{"role": "user", "content": "hello"}],
                trace_metadata={"session_id": "session-123", "feature": "generate_alumni_extraction"},
            )
        except RuntimeError:
            pass
        else:
            assert False, "Expected RuntimeError to be re-raised"

    with open(trace_path, encoding="utf-8") as handle:
        entries = [json.loads(line) for line in handle if line.strip()]

    assert len(entries) == 2
    assert entries[0]["status"] == "started"
    assert entries[1]["status"] == "error"
    assert entries[1]["error"] == "client blew up"
    assert entries[1]["session_id"] == "session-123"


def test_llm_traces_endpoint_reads_langfuse_sessions():
    from routers.kb_router import _read_llm_trace_log
    import routers.kb_router as kb_router

    started_at = datetime(2026, 4, 20, 3, 34, 26, tzinfo=timezone.utc)
    finished_at = datetime(2026, 4, 20, 3, 35, 52, tzinfo=timezone.utc)

    observation = SimpleNamespace(
        id="langfuse-observation-1",
        name="generate_session_intents_json_repair",
        input={
            "raw_input_chars": 7111,
            "input_chars_pre_trim": 7111,
            "session_id": "session-123",
            "multi_pass": False,
            "threshold_chars": 12000,
            "chunk_tokens": 15000,
            "overlap_tokens": 2000,
        },
        output={
            "cards": 0,
            "already_covered": 0,
            "multi_pass": False,
            "error": "SessionAnalysisResult repair did not return a valid JSON object",
        },
        session_id="session-123",
        metadata={
            "traceId": "trace-123",
            "feature": "generate_session_intents",
            "phase": "json_repair",
            "parseAttempt": 2,
            "repairAttempt": 2,
            "inputCharsPreTrim": 7111,
            "inputCharsSent": 2505,
            "maxTokens": 512,
            "timeoutSeconds": 180,
        },
        start_time=started_at,
        end_time=finished_at,
        model="claude-sonnet-4-6",
        level="DEFAULT",
    )

    fake_trace = SimpleNamespace(
        id="trace-123",
        observations=[observation],
    )

    fake_session = SimpleNamespace(
        id="session-123",
        traces=[fake_trace],
    )

    class FakeSessionsApi:
        def list(self, limit=None):
            return SimpleNamespace(data=[SimpleNamespace(id="session-123")])

        def get(self, session_id):
            assert session_id == "session-123"
            return fake_session

    class FakeLangfuseClient:
        def __init__(self):
            self.api = SimpleNamespace(sessions=FakeSessionsApi())

    fake_langfuse = FakeLangfuseClient()

    with patch.object(kb_router.llm_service, "_get_langfuse_client", return_value=fake_langfuse):
        data = _read_llm_trace_log(limit=10)

    assert len(data) == 2
    assert data[0].status == "started"
    assert data[1].status == "error"
    assert data[1].trace_id == "trace-123"
    assert data[1].session_id == "session-123"
    assert data[1].operation == "generate_session_intents_json_repair"
    assert data[1].error == "SessionAnalysisResult repair did not return a valid JSON object"


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
    assert fake_langfuse.propagated["metadata"]["environment"] == "development"
    assert fake_langfuse.propagated["metadata"]["feature"] == "generate_brief"
    assert fake_langfuse.started[0]["input"]["metadata"]["traceId"]
    assert fake_langfuse.started[0]["input"]["metadata"]["traceId"] == fake_langfuse.propagated["metadata"]["traceId"]
    assert fake_langfuse.started[0]["input"]["message_count"] == 1
    assert fake_langfuse.started[0]["input"]["system_preview"]
    assert fake_langfuse.started[0]["input"]["system_chars"] > 0
    assert fake_langfuse.started[0]["input"]["max_tokens"] == 2048
    assert fake_langfuse.started[0]["input"]["timeout_seconds"] is None
    assert fake_langfuse.started[0]["input"]["messages"][0]["role"] == "user"
    assert fake_langfuse.started[0]["input"]["messages"][0]["content_preview"]
    assert fake_langfuse.started[0]["input"]["messages"][0]["content_chars"] > 0
    assert fake_langfuse.started[0]["input"]["metadata"]["inputCharsPreTrim"] > 0
    assert fake_langfuse.started[0]["input"]["metadata"]["kbChunksRetrieved"] == 0
    assert fake_langfuse.flushed is False


def test_langfuse_mask_redacts_common_secrets():
    import services.llm as llm_module

    masked = llm_module._mask_langfuse_value(
        {
            "email": "alice@example.com",
            "phone": "+1 (555) 123-4567",
            "api_key": "sk-test-1234567890",
            "nested": ["Bearer abc.def.ghi", "plain text"],
        }
    )

    assert masked["email"] == "[EMAIL_REDACTED]"
    assert masked["phone"] == "[PHONE_REDACTED]"
    assert masked["api_key"] == "[API_KEY_REDACTED]"
    assert masked["nested"][0] == "Bearer [REDACTED]"
    assert masked["nested"][1] == "plain text"


@patch("services.llm.get_client")
def test_extract_facts_from_prose_writes_langfuse_observation(mock_client):
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
    mock_client.return_value.messages.create.return_value = _make_claude_response(
        json.dumps([
            {
                "slug": "google-internship",
                "type": "timeline_phase",
                "phase_name": "Summer internship",
                "value": "June to August",
                "source": "inferred",
                "confidence": 90,
                "timestamp": "2026-04-20T00:00:00Z",
            }
        ])
    )

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
        facts = asyncio.run(llm_module.extract_facts_from_prose("Alice discussed Google hiring timelines.", "Google"))

    assert len(facts) == 1
    assert facts[0]["slug"] == "google-internship"
    assert fake_langfuse.started[0]["name"] == "extract_facts_from_prose"
    assert fake_langfuse.started[0]["input"]["metadata"]["feature"] == "extract_facts_from_prose"
    assert fake_langfuse.started[0]["input"]["metadata"]["trace_id"]
    assert fake_langfuse.propagated["metadata"]["environment"] == "development"
    assert fake_langfuse.flushed is False


@patch("services.llm.get_client")
def test_extract_facts_from_prose_accepts_fenced_json_without_repair(mock_client):
    import services.llm as llm_module

    class FakeLangfuseClient:
        def __init__(self):
            self.started = []
            self.flushed = False

        @contextmanager
        def start_as_current_observation(self, **kwargs):
            self.started.append(kwargs)
            yield SimpleNamespace(update=lambda **kwargs: None)

        def flush(self):
            self.flushed = True

    fake_langfuse = FakeLangfuseClient()
    mock_client.return_value.messages.create.return_value = _make_claude_response(
        "```json\n"
        + json.dumps([
            {
                "slug": "google-internship",
                "type": "timeline_phase",
                "phase_name": "Summer internship",
                "value": "June to August",
                "source": "inferred",
                "confidence": 90,
                "timestamp": "2026-04-20T00:00:00Z",
            }
        ])
        + "\n```"
    )

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
        patch.object(llm_module, "_schedule_langfuse_flush", return_value=None), \
        patch.object(llm_module, "_repair_json_output", side_effect=AssertionError("repair should not be needed")):
        facts = asyncio.run(llm_module.extract_facts_from_prose("Alice discussed Google hiring timelines.", "Google"))

    assert len(facts) == 1
    assert facts[0]["slug"] == "google-internship"
    assert fake_langfuse.started[0]["name"] == "extract_facts_from_prose"
    assert fake_langfuse.started[0]["input"]["metadata"]["feature"] == "extract_facts_from_prose"
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


def test_workflow_detail_combines_trace_and_session_evidence(tmp_path, monkeypatch):
    import services.trace_adapter as trace_adapter
    from services.session_store import SessionStore

    sessions_dir = tmp_path / "sessions"
    trace_path = tmp_path / "logs" / "llm_trace_log.jsonl"
    monkeypatch.setenv("SESSIONS_DIR", str(sessions_dir))
    SessionStore._instance = None

    store = SessionStore()
    session = store.create_session("Met with Goldman and Maya Lim.", created_by="counsellor")
    session.status = "analyzed"
    session.intent_cards = [
        {
            "card_id": "card-1",
            "domain": "employer",
            "summary": "Update Goldman Sachs",
            "diff": {"slug": "goldman_sachs", "notes": "Raised EP requirement"},
            "raw_input_ref": "Goldman raised their EP requirement.",
            "status": "pending",
        }
    ]
    session.already_covered = [{"content": "Maya mentors students", "reason": "Already recorded"}]
    session.analysis_workflow = {
        "workflow_id": "workflow-123",
        "workflow_name": "session_card_analysis",
        "status": "ok",
        "started_at": "2026-05-03T12:00:00+00:00",
        "ended_at": "2026-05-03T12:00:03+00:00",
        "drop_point": "session.intent_cards",
        "append": {"target": "session.intent_cards", "result": "written", "card_count": 1},
        "validation": {"result": "accepted", "validated_cards": 1},
        "card_counts": {"raw": 1, "repaired": 1, "committed": 1, "already_covered": 1, "alumni_built": 0},
        "alumni": {"heavy": True, "invoked": True, "result": "invoked", "cards_built": 0},
        "steps": [{"step_id": "router-1", "label": "Append cards", "status": "ok", "detail": "Cards written"}],
    }
    store.save_session(session)

    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "trace_id": "trace-1",
                        "ts": "2026-05-03T12:00:00+00:00",
                        "operation": "generate_session_intents",
                        "status": "started",
                        "model": "claude-sonnet-4-6",
                        "session_id": session.id,
                        "workflow_id": "workflow-123",
                        "workflow_name": "session_card_analysis",
                        "prompt_name": "generate_session_intents",
                        "prompt_source": "repo",
                        "prompt_label": "repo",
                        "prompt_version": 3,
                        "schema_name": "SessionAnalysisResult",
                        "domain_mix": "track,employer",
                        "timeout_seconds": 180.0,
                        "max_tokens": 4096,
                        "latency_ms": 0.0,
                        "input_chars": 200,
                        "output_chars": 0,
                        "input_preview": "Met with Goldman",
                        "output_preview": "",
                        "error": None,
                    }
                ),
                json.dumps(
                    {
                        "trace_id": "trace-1",
                        "ts": "2026-05-03T12:00:02+00:00",
                        "operation": "generate_session_intents",
                        "status": "ok",
                        "model": "claude-sonnet-4-6",
                        "session_id": session.id,
                        "workflow_id": "workflow-123",
                        "workflow_name": "session_card_analysis",
                        "prompt_name": "generate_session_intents",
                        "prompt_source": "repo",
                        "prompt_label": "repo",
                        "prompt_version": 3,
                        "schema_name": "SessionAnalysisResult",
                        "domain_mix": "track,employer",
                        "repair_applied": True,
                        "card_count_raw": 1,
                        "card_count_repaired": 1,
                        "timeout_seconds": 180.0,
                        "max_tokens": 4096,
                        "latency_ms": 1532.0,
                        "input_chars": 200,
                        "output_chars": 420,
                        "input_preview": "Met with Goldman",
                        "output_preview": "{\"cards\": 1}",
                        "error": None,
                    }
                )
            ]
        ),
        encoding="utf-8",
    )

    fake_settings = SimpleNamespace(llm_trace_log_path=str(trace_path))
    with patch.object(trace_adapter, "settings", fake_settings), patch.object(trace_adapter.llm_service, "_get_langfuse_client", return_value=None):
        detail = trace_adapter.get_workflow_detail(session_id=session.id)
        summaries = trace_adapter.list_workflow_summaries(session_id=session.id)

    assert detail is not None
    assert detail.workflow_id == "workflow-123"
    assert detail.prompt.prompt_name == "generate_session_intents"
    assert detail.prompt.prompt_version == 3
    assert detail.card_counts.committed == 1
    assert detail.append_summary["result"] == "written"
    assert detail.alumni_path == "invoked"
    assert any(step.label == "Append cards" for step in detail.steps)

    assert len(summaries) == 1
    assert summaries[0].workflow_id == "workflow-123"
    assert summaries[0].repair_applied is True
    assert summaries[0].card_counts.committed == 1
