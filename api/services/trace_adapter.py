"""Adapters for presenting LLM trace data to the admin API."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from config import settings
from models_kb import (
    LLMTraceEntry,
    LLMPromptProvenance,
    LLMWorkflowCardCounts,
    LLMWorkflowDetail,
    LLMWorkflowScore,
    LLMWorkflowStep,
    LLMWorkflowSummary,
)
from services.session_store import SessionStore
from services import llm as llm_service
from services.shared_yaml import safe_float, safe_int
from utils.sdk_shapes import (
    coerce_mapping,
    coerce_sequence,
    estimate_input_chars,
    estimate_output_chars,
    format_timestamp,
    get_value,
    preview_input,
    preview_output,
)

logger = logging.getLogger(__name__)


def observation_to_trace_entries(observation: object) -> list[LLMTraceEntry]:
    """Convert a Langfuse observation into started and terminal admin rows."""
    metadata = coerce_mapping(get_value(observation, "metadata", default={})) or {}
    input_payload = get_value(observation, "input", default={})
    output_payload = get_value(observation, "output", default=None)
    nested_observations = coerce_sequence(get_value(observation, "observations", default=[]))

    operation = str(
        get_value(
            observation,
            "name",
            "operation",
            default=metadata.get("feature") or metadata.get("operation") or "llm_call",
        )
    )
    if operation == "llm_call" and nested_observations:
        for nested in nested_observations:
            nested_metadata = coerce_mapping(get_value(nested, "metadata", default={})) or {}
            nested_operation = get_value(
                nested,
                "name",
                "operation",
                default=nested_metadata.get("feature") or nested_metadata.get("operation") or "",
            )
            if nested_operation and str(nested_operation) != "llm_call":
                operation = str(nested_operation)
                break
    trace_id = str(
        metadata.get("traceId")
        or metadata.get("trace_id")
        or get_value(
            observation,
            "id",
            "trace_id",
            "traceId",
            default="",
        )
    )
    session_id = get_value(
        observation,
        "session_id",
        "sessionId",
        default=metadata.get("session_id") or metadata.get("sessionId"),
    )
    if session_id is None and nested_observations:
        for nested in nested_observations:
            nested_metadata = coerce_mapping(get_value(nested, "metadata", default={})) or {}
            session_id = get_value(
                nested,
                "session_id",
                "sessionId",
                default=nested_metadata.get("session_id") or nested_metadata.get("sessionId"),
            )
            if session_id is not None:
                break
    model = str(
        get_value(
            observation,
            "model",
            "provided_model_name",
            default=metadata.get("model") or metadata.get("providedModelName") or "",
        )
    )
    if not model:
        for nested in nested_observations:
            hinted_model = get_value(nested, "model", "provided_model_name", default=None)
            if hinted_model:
                model = str(hinted_model)
                break
    phase = str(metadata.get("phase") or metadata.get("phaseName") or "")
    status_message = get_value(observation, "status_message", "statusMessage", default=metadata.get("error"))
    level = str(get_value(observation, "level", default="")).upper()
    output_error = None
    output_mapping = coerce_mapping(output_payload)
    if output_mapping:
        raw_output_error = output_mapping.get("error")
        if raw_output_error:
            output_error = str(raw_output_error)

    if not output_error and nested_observations:
        for nested in nested_observations:
            nested_metadata = coerce_mapping(get_value(nested, "metadata", default={})) or {}
            nested_output = coerce_mapping(get_value(nested, "output", default=None))
            nested_error = get_value(nested, "status_message", "statusMessage", default=nested_metadata.get("error"))
            if not nested_error and nested_output:
                raw_nested_output_error = nested_output.get("error")
                if raw_nested_output_error:
                    nested_error = str(raw_nested_output_error)
            if nested_error:
                output_error = str(nested_error)
                break
            nested_level = str(get_value(nested, "level", default="")).upper()
            if nested_level == "ERROR":
                output_error = nested_level
                break
    error_text = str(status_message) if status_message else output_error

    start_value = get_value(observation, "start_time", "startTime", "created_at", "createdAt", "timestamp", "ts", default=None)
    end_value = get_value(observation, "end_time", "endTime", "updated_at", "updatedAt", default=None)
    latency_seconds = safe_float(get_value(observation, "latency", default=None), default=0.0)
    start_ts = format_timestamp(start_value)
    if isinstance(start_value, datetime) and end_value is None and latency_seconds:
        end_ts = format_timestamp(start_value + timedelta(seconds=latency_seconds))
    else:
        end_ts = format_timestamp(end_value)

    latency_ms = safe_float(
        get_value(
            observation,
            "latency_ms",
            "latencyMs",
            default=None,
        ),
        default=0.0,
    )
    if not latency_ms:
        start_dt = get_value(observation, "start_time", "startTime", "created_at", "createdAt", "timestamp", default=None)
        end_dt = get_value(observation, "end_time", "endTime", "updated_at", "updatedAt", default=None)
        if isinstance(start_dt, datetime) and isinstance(end_dt, datetime):
            latency_ms = round((end_dt - start_dt).total_seconds() * 1000, 1)
        elif isinstance(start_dt, datetime) and latency_seconds:
            latency_ms = round(latency_seconds * 1000, 1)

    input_chars = safe_int(metadata.get("input_chars"), None)
    if input_chars is None:
        input_chars = estimate_input_chars(input_payload)

    output_chars = safe_int(metadata.get("output_chars"), None)
    if output_chars is None:
        output_chars = estimate_output_chars(output_payload)

    trace_meta = {
        "feature": metadata.get("feature") or operation,
        "session_id": session_id,
        "workflow_id": get_value(metadata, "workflowId", "workflow_id", default=None),
        "workflow_name": get_value(metadata, "workflowName", "workflow_name", default=None),
        "phase": phase or None,
        "chunk_index": safe_int(get_value(metadata, "chunkIndex", "chunk_index")),
        "chunk_count": safe_int(get_value(metadata, "chunkCount", "chunk_count")),
        "multi_pass_threshold_chars": safe_int(get_value(metadata, "multiPassThresholdChars", "multi_pass_threshold_chars")),
        "multi_pass_chunk_tokens": safe_int(get_value(metadata, "multiPassChunkTokens", "multi_pass_chunk_tokens")),
        "multi_pass_overlap_tokens": safe_int(get_value(metadata, "multiPassOverlapTokens", "multi_pass_overlap_tokens")),
        "input_chars_pre_trim": safe_int(get_value(metadata, "inputCharsPreTrim", "input_chars_pre_trim")),
        "input_chars_sent": safe_int(get_value(metadata, "inputCharsSent", "input_chars_sent")),
        "kb_chunks_retrieved": safe_int(get_value(metadata, "kbChunksRetrieved", "kb_chunks_retrieved")),
        "kb_chunks_sent": safe_int(get_value(metadata, "kbChunksSent", "kb_chunks_sent")),
        "parse_attempt": safe_int(get_value(metadata, "parseAttempt", "parse_attempt")),
        "repair_attempt": safe_int(get_value(metadata, "repairAttempt", "repair_attempt")),
        "partial_result": get_value(metadata, "partialResult", "partial_result", default=None),
        "prompt_name": get_value(metadata, "promptName", "prompt_name", default=None),
        "prompt_source": get_value(metadata, "promptSource", "prompt_source", default=None),
        "prompt_label": get_value(metadata, "promptLabel", "prompt_label", default=None),
        "prompt_version": safe_int(get_value(metadata, "promptVersion", "prompt_version"), None),
        "schema_name": get_value(metadata, "schemaName", "schema_name", default=None),
        "error_class": get_value(metadata, "errorClass", "error_class", default=None),
        "domain_mix": get_value(metadata, "domainMix", "domain_mix", default=None),
        "repair_applied": get_value(metadata, "repairApplied", "repair_applied", default=None),
        "card_count_raw": safe_int(get_value(metadata, "cardCountRaw", "card_count_raw"), None),
        "card_count_repaired": safe_int(get_value(metadata, "cardCountRepaired", "card_count_repaired"), None),
        "card_count_committed": safe_int(get_value(metadata, "cardCountCommitted", "card_count_committed"), None),
    }

    started = LLMTraceEntry(
        trace_id=trace_id,
        ts=start_ts,
        operation=operation,
        status="started",
        model=model,
        feature=trace_meta["feature"],
        session_id=str(session_id) if session_id is not None else None,
        workflow_id=str(trace_meta["workflow_id"]) if trace_meta["workflow_id"] is not None else None,
        workflow_name=str(trace_meta["workflow_name"]) if trace_meta["workflow_name"] is not None else None,
        phase=trace_meta["phase"],
        chunk_index=trace_meta["chunk_index"],
        chunk_count=trace_meta["chunk_count"],
        multi_pass_threshold_chars=trace_meta["multi_pass_threshold_chars"],
        multi_pass_chunk_tokens=trace_meta["multi_pass_chunk_tokens"],
        multi_pass_overlap_tokens=trace_meta["multi_pass_overlap_tokens"],
        input_chars_pre_trim=trace_meta["input_chars_pre_trim"],
        input_chars_sent=trace_meta["input_chars_sent"],
        kb_chunks_retrieved=trace_meta["kb_chunks_retrieved"],
        kb_chunks_sent=trace_meta["kb_chunks_sent"],
        parse_attempt=trace_meta["parse_attempt"],
        repair_attempt=trace_meta["repair_attempt"],
        partial_result=trace_meta["partial_result"],
        prompt_name=str(trace_meta["prompt_name"]) if trace_meta["prompt_name"] is not None else None,
        prompt_source=str(trace_meta["prompt_source"]) if trace_meta["prompt_source"] is not None else None,
        prompt_label=str(trace_meta["prompt_label"]) if trace_meta["prompt_label"] is not None else None,
        prompt_version=trace_meta["prompt_version"],
        schema_name=str(trace_meta["schema_name"]) if trace_meta["schema_name"] is not None else None,
        error_class=str(trace_meta["error_class"]) if trace_meta["error_class"] is not None else None,
        domain_mix=str(trace_meta["domain_mix"]) if trace_meta["domain_mix"] is not None else None,
        repair_applied=trace_meta["repair_applied"],
        card_count_raw=trace_meta["card_count_raw"],
        card_count_repaired=trace_meta["card_count_repaired"],
        card_count_committed=trace_meta["card_count_committed"],
        timeout_seconds=safe_float(get_value(metadata, "timeoutSeconds", "timeout_seconds"), None),
        max_tokens=safe_int(get_value(metadata, "maxTokens", "max_tokens"), 0) or 0,
        latency_ms=0.0,
        input_chars=input_chars,
        output_chars=0,
        input_preview=preview_input(input_payload),
        output_preview="",
        error=None,
    )

    terminal_status = "error" if (level == "ERROR" or error_text) else "ok"
    terminal = LLMTraceEntry(
        trace_id=trace_id,
        ts=end_ts,
        operation=operation,
        status=terminal_status,
        model=model,
        feature=trace_meta["feature"],
        session_id=str(session_id) if session_id is not None else None,
        workflow_id=str(trace_meta["workflow_id"]) if trace_meta["workflow_id"] is not None else None,
        workflow_name=str(trace_meta["workflow_name"]) if trace_meta["workflow_name"] is not None else None,
        phase=trace_meta["phase"],
        chunk_index=trace_meta["chunk_index"],
        chunk_count=trace_meta["chunk_count"],
        multi_pass_threshold_chars=trace_meta["multi_pass_threshold_chars"],
        multi_pass_chunk_tokens=trace_meta["multi_pass_chunk_tokens"],
        multi_pass_overlap_tokens=trace_meta["multi_pass_overlap_tokens"],
        input_chars_pre_trim=trace_meta["input_chars_pre_trim"],
        input_chars_sent=trace_meta["input_chars_sent"],
        kb_chunks_retrieved=trace_meta["kb_chunks_retrieved"],
        kb_chunks_sent=trace_meta["kb_chunks_sent"],
        parse_attempt=trace_meta["parse_attempt"],
        repair_attempt=trace_meta["repair_attempt"],
        partial_result=trace_meta["partial_result"],
        prompt_name=str(trace_meta["prompt_name"]) if trace_meta["prompt_name"] is not None else None,
        prompt_source=str(trace_meta["prompt_source"]) if trace_meta["prompt_source"] is not None else None,
        prompt_label=str(trace_meta["prompt_label"]) if trace_meta["prompt_label"] is not None else None,
        prompt_version=trace_meta["prompt_version"],
        schema_name=str(trace_meta["schema_name"]) if trace_meta["schema_name"] is not None else None,
        error_class=str(trace_meta["error_class"]) if trace_meta["error_class"] is not None else None,
        domain_mix=str(trace_meta["domain_mix"]) if trace_meta["domain_mix"] is not None else None,
        repair_applied=trace_meta["repair_applied"],
        card_count_raw=trace_meta["card_count_raw"],
        card_count_repaired=trace_meta["card_count_repaired"],
        card_count_committed=trace_meta["card_count_committed"],
        timeout_seconds=safe_float(get_value(metadata, "timeoutSeconds", "timeout_seconds"), None),
        max_tokens=safe_int(get_value(metadata, "maxTokens", "max_tokens"), 0) or 0,
        latency_ms=latency_ms,
        input_chars=input_chars,
        output_chars=output_chars,
        input_preview=preview_input(input_payload),
        output_preview=preview_output(output_payload),
        error=error_text if terminal_status == "error" else None,
    )

    return [started, terminal]


def read_langfuse_trace_log(
    limit: int = 50,
    session_id: str | None = None,
    operation: str | None = None,
    status: str | None = None,
) -> list[LLMTraceEntry]:
    """Read recent LLM trace entries from Langfuse sessions if configured."""
    langfuse_client = llm_service._get_langfuse_client()
    if langfuse_client is None:
        return []

    sessions_api = getattr(getattr(langfuse_client, "api", None), "sessions", None)
    if sessions_api is None:
        return []

    session_objects: list[object] = []
    try:
        if session_id:
            session_objects = [get_value(sessions_api.get(session_id), "traces", default=[])]
        else:
            sessions_response = sessions_api.list(limit=max(1, min(limit, 50)))
            session_items = coerce_sequence(get_value(sessions_response, "data", "items", default=[]))
            for item in session_items:
                item_id = get_value(item, "id", default=None)
                if not item_id:
                    continue
                try:
                    session_objects.append(get_value(sessions_api.get(str(item_id)), "traces", default=[]))
                except Exception:
                    logger.warning("Skipping unreadable Langfuse session %r", item_id, exc_info=True)
    except Exception as exc:
        logger.warning("Failed to read Langfuse sessions; falling back to JSONL log", exc_info=exc)
        return []

    entries: list[LLMTraceEntry] = []
    for trace_group in session_objects:
        traces = coerce_sequence(trace_group)
        for trace in traces:
            try:
                for entry in observation_to_trace_entries(trace):
                    if session_id and entry.session_id != session_id:
                        continue
                    if operation and entry.operation != operation and entry.feature != operation:
                        continue
                    if status and entry.status != status:
                        continue
                    entries.append(entry)
            except Exception:
                logger.warning("Skipping malformed Langfuse trace", exc_info=True)

    entries.sort(key=lambda entry: entry.ts)
    return entries[-limit:]


def read_llm_trace_log(
    limit: int = 50,
    session_id: str | None = None,
    operation: str | None = None,
    status: str | None = None,
    trace_path: str | None = None,
) -> list[LLMTraceEntry]:
    """Read recent LLM trace entries from Langfuse, falling back to JSONL."""
    langfuse_entries = read_langfuse_trace_log(
        limit=limit,
        session_id=session_id,
        operation=operation,
        status=status,
    )
    if langfuse_entries:
        return langfuse_entries

    entries: list[LLMTraceEntry] = []
    try:
        resolved_trace_path = trace_path if trace_path is not None else getattr(settings, "llm_trace_log_path", "")
        if not resolved_trace_path or not os.path.exists(resolved_trace_path):
            return []
        with open(resolved_trace_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                entries.append(LLMTraceEntry(**raw))
            except Exception:
                logger.warning("Skipping malformed LLM trace line: %r", line[:120])
    except Exception:
        logger.warning("Failed to read LLM trace log", exc_info=True)
        return []

    if session_id:
        entries = [entry for entry in entries if entry.session_id == session_id]
    if operation:
        entries = [entry for entry in entries if entry.operation == operation]
    if status:
        entries = [entry for entry in entries if entry.status == status]
    return entries[-limit:]


def list_recent(
    limit: int = 50,
    session_id: str | None = None,
    operation: str | None = None,
    status: str | None = None,
    trace_path: str | None = None,
) -> list[LLMTraceEntry]:
    """Return recent LLM trace entries for admin display."""
    return read_llm_trace_log(
        limit=limit,
        session_id=session_id,
        operation=operation,
        status=status,
        trace_path=trace_path,
    )


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _is_session_workflow_entry(entry: LLMTraceEntry) -> bool:
    if entry.workflow_name == "session_card_analysis":
        return True
    return entry.operation in {
        "generate_session_intents",
        "generate_session_intents_json_repair",
        "generate_alumni_extraction",
        "generate_alumni_extraction_json_repair",
    }


def _workflow_group_key(entry: LLMTraceEntry) -> str:
    return entry.workflow_id or entry.session_id or entry.trace_id


def _load_session_workflows(session_id: str | None = None) -> dict[str, object]:
    store = SessionStore()
    sessions = []
    if session_id:
        session = store.get_session(session_id)
        if session:
            sessions = [session]
    else:
        sessions = store.list_sessions()

    indexed: dict[str, object] = {}
    for session in sessions:
        workflow = getattr(session, "analysis_workflow", None) or {}
        if not workflow:
            continue
        workflow_id = str(workflow.get("workflow_id") or session.id)
        indexed[workflow_id] = session
    return indexed


def _prompt_from_entries(entries: list[LLMTraceEntry]) -> LLMPromptProvenance:
    for entry in entries:
        if entry.prompt_name or entry.prompt_source or entry.prompt_label or entry.prompt_version is not None:
            return LLMPromptProvenance(
                prompt_name=entry.prompt_name,
                prompt_source=entry.prompt_source,
                prompt_label=entry.prompt_label,
                prompt_version=entry.prompt_version,
            )
    return LLMPromptProvenance()


def _workflow_card_counts(entries: list[LLMTraceEntry], workflow_debug: dict[str, object]) -> LLMWorkflowCardCounts:
    card_counts = workflow_debug.get("card_counts") if isinstance(workflow_debug.get("card_counts"), dict) else {}
    raw = safe_int(card_counts.get("raw"), None)
    repaired = safe_int(card_counts.get("repaired"), None)
    committed = safe_int(card_counts.get("committed"), None)
    already_covered = safe_int(card_counts.get("already_covered"), None)
    alumni_built = safe_int(card_counts.get("alumni_built"), None)

    if raw is None:
        raw = max((entry.card_count_raw or 0 for entry in entries), default=0) or None
    if repaired is None:
        repaired = max((entry.card_count_repaired or 0 for entry in entries), default=0) or None
    if committed is None:
        committed = max((entry.card_count_committed or 0 for entry in entries), default=0) or None

    return LLMWorkflowCardCounts(
        raw=raw,
        repaired=repaired,
        committed=committed,
        already_covered=already_covered,
        alumni_built=alumni_built,
    )


def _workflow_status(entries: list[LLMTraceEntry], workflow_debug: dict[str, object]) -> str:
    status = str(workflow_debug.get("status") or "").strip()
    if status:
        return status
    if any(entry.status == "error" for entry in entries):
        return "error"
    if any(entry.status == "started" for entry in entries) and not any(entry.status == "ok" for entry in entries):
        return "started"
    return "ok"


def _workflow_times(entries: list[LLMTraceEntry], workflow_debug: dict[str, object]) -> tuple[str | None, str | None, float | None]:
    started_at = str(workflow_debug.get("started_at") or "").strip() or None
    ended_at = str(workflow_debug.get("ended_at") or "").strip() or None

    if not started_at and entries:
        started_at = min((entry.ts for entry in entries if entry.ts), default=None)
    if not ended_at:
        finished = [entry.ts for entry in entries if entry.status != "started" and entry.ts]
        ended_at = max(finished, default=None)

    start_dt = _parse_ts(started_at)
    end_dt = _parse_ts(ended_at)
    duration_ms = round((end_dt - start_dt).total_seconds() * 1000, 1) if start_dt and end_dt else None
    return started_at, ended_at, duration_ms


def _workflow_failure_summary(entries: list[LLMTraceEntry], workflow_debug: dict[str, object]) -> str | None:
    failure = str(workflow_debug.get("failure_summary") or workflow_debug.get("analysis_error") or "").strip()
    if failure:
        return failure
    for entry in reversed(entries):
        if entry.error:
            return entry.error
    return None


def _workflow_steps(entries: list[LLMTraceEntry], workflow_debug: dict[str, object]) -> list[LLMWorkflowStep]:
    label_map = {
        "generate_session_intents": "Intent extraction",
        "generate_session_intents_json_repair": "JSON repair",
        "generate_alumni_extraction": "Alumni extraction",
        "generate_alumni_extraction_json_repair": "Alumni JSON repair",
    }
    by_trace: dict[str, list[LLMTraceEntry]] = {}
    for entry in entries:
        by_trace.setdefault(entry.trace_id, []).append(entry)

    steps: list[LLMWorkflowStep] = []
    for trace_id, trace_entries in by_trace.items():
        trace_entries.sort(key=lambda item: item.ts)
        first = trace_entries[0]
        last = trace_entries[-1]
        started_at, ended_at, duration_ms = _workflow_times(trace_entries, {})
        steps.append(
            LLMWorkflowStep(
                step_id=trace_id,
                label=label_map.get(first.operation, first.operation.replace("_", " ")),
                status=last.status,
                started_at=started_at,
                ended_at=ended_at,
                duration_ms=duration_ms or last.latency_ms or None,
                detail=last.error or last.output_preview or first.input_preview,
                metadata={
                    "operation": first.operation,
                    "phase": first.phase,
                    "prompt_name": first.prompt_name,
                    "prompt_version": first.prompt_version,
                    "repair_attempt": last.repair_attempt,
                },
            )
        )

    router_steps = workflow_debug.get("steps") if isinstance(workflow_debug.get("steps"), list) else []
    for index, raw_step in enumerate(router_steps):
        if not isinstance(raw_step, dict):
            continue
        steps.append(
            LLMWorkflowStep(
                step_id=str(raw_step.get("step_id") or f"router-step-{index + 1}"),
                label=str(raw_step.get("label") or raw_step.get("step") or f"Router step {index + 1}"),
                status=str(raw_step.get("status") or "ok"),
                started_at=raw_step.get("started_at"),
                ended_at=raw_step.get("ended_at"),
                duration_ms=safe_float(raw_step.get("duration_ms"), None),
                detail=raw_step.get("detail"),
                metadata=raw_step.get("metadata") if isinstance(raw_step.get("metadata"), dict) else {},
            )
        )

    steps.sort(key=lambda step: step.started_at or "")
    return steps


def _workflow_scores(
    *,
    status: str,
    repair_applied: bool,
    card_counts: LLMWorkflowCardCounts,
    workflow_debug: dict[str, object],
) -> list[LLMWorkflowScore]:
    drop_point = str(workflow_debug.get("drop_point") or "").strip() or None
    alumni = workflow_debug.get("alumni") if isinstance(workflow_debug.get("alumni"), dict) else {}
    alumni_invoked = bool(alumni.get("invoked"))
    alumni_built = safe_int(alumni.get("cards_built"), 0) or 0

    scores = [
        LLMWorkflowScore(
            key="json_validity",
            value=1 if status != "error" else 0,
            label="JSON validity",
            rationale="Structured output survived parsing and validation." if status != "error" else "A parsing or validation error interrupted the workflow.",
        ),
        LLMWorkflowScore(
            key="repair_invoked",
            value=repair_applied,
            label="Repair invoked",
            rationale="A JSON repair subflow ran for this workflow." if repair_applied else "No repair subflow was needed.",
        ),
        LLMWorkflowScore(
            key="card_presence",
            value=(card_counts.repaired or card_counts.raw or 0) > 0,
            label="Card presence",
            rationale="At least one card survived the extraction path." if (card_counts.repaired or card_counts.raw or 0) > 0 else "No cards were produced for this run.",
        ),
        LLMWorkflowScore(
            key="alumni_card_presence",
            value=alumni_built > 0,
            label="Alumni card presence",
            rationale="The alumni path produced at least one alumni card." if alumni_built > 0 else "The alumni path did not yield a surviving alumni card.",
        ),
        LLMWorkflowScore(
            key="schema_rejection",
            value=drop_point == "card_validation",
            label="Schema rejection",
            rationale="A card failed schema validation before append." if drop_point == "card_validation" else "No schema rejection was recorded.",
        ),
        LLMWorkflowScore(
            key="expected_domain_recall",
            value=1 if (card_counts.repaired or card_counts.raw or 0) > 0 or status == "ok" else 0,
            label="Expected domain recall",
            rationale="The run preserved at least one domain card or ended cleanly." if (card_counts.repaired or card_counts.raw or 0) > 0 or status == "ok" else "The workflow ended before any domain cards survived.",
        ),
    ]

    if alumni_invoked or alumni_built > 0:
        scores.append(
            LLMWorkflowScore(
                key="manual_debug_severity",
                value="warning" if alumni_invoked and alumni_built == 0 else "normal",
                label="Manual debug severity",
                rationale="Alumni extraction ran but no alumni card survived." if alumni_invoked and alumni_built == 0 else "No elevated manual debug signal was detected.",
            )
        )

    return scores


def list_workflow_summaries(
    limit: int = 25,
    session_id: str | None = None,
    status: str | None = None,
) -> list[LLMWorkflowSummary]:
    trace_limit = max(limit * 20, 200)
    entries = [entry for entry in read_llm_trace_log(limit=trace_limit, session_id=session_id) if _is_session_workflow_entry(entry)]
    grouped: dict[str, list[LLMTraceEntry]] = {}
    for entry in entries:
        grouped.setdefault(_workflow_group_key(entry), []).append(entry)

    sessions = _load_session_workflows(session_id=session_id)
    summaries: list[LLMWorkflowSummary] = []
    workflow_ids = set(grouped.keys()) | set(sessions.keys())
    for workflow_id in workflow_ids:
        session = sessions.get(workflow_id)
        workflow_debug = getattr(session, "analysis_workflow", None) or {}
        workflow_entries = grouped.get(workflow_id, [])
        status_value = _workflow_status(workflow_entries, workflow_debug)
        if status and status_value != status:
            continue
        started_at, ended_at, duration_ms = _workflow_times(workflow_entries, workflow_debug)
        prompt = _prompt_from_entries(workflow_entries)
        card_counts = _workflow_card_counts(workflow_entries, workflow_debug)
        alumni = workflow_debug.get("alumni") if isinstance(workflow_debug.get("alumni"), dict) else {}
        summaries.append(
            LLMWorkflowSummary(
                workflow_id=str(workflow_debug.get("workflow_id") or workflow_id),
                workflow_name=str(workflow_debug.get("workflow_name") or "session_card_analysis"),
                status=status_value,
                started_at=started_at,
                ended_at=ended_at,
                duration_ms=duration_ms,
                session_id=str(getattr(session, "id", None) or (workflow_entries[0].session_id if workflow_entries else "")) or None,
                model=next((entry.model for entry in workflow_entries if entry.model), None),
                prompt=prompt,
                drop_point=str(workflow_debug.get("drop_point") or "").strip() or None,
                failure_summary=_workflow_failure_summary(workflow_entries, workflow_debug),
                repair_applied=bool(workflow_debug.get("repair_applied")) or any(
                    bool(entry.repair_applied) or (entry.repair_attempt or 0) > 0
                    for entry in workflow_entries
                ),
                card_counts=card_counts,
                alumni_path=str(alumni.get("result") or alumni.get("status") or "").strip() or None,
                is_partial=bool(workflow_debug.get("partial_result")) or any(bool(entry.partial_result) for entry in workflow_entries),
            )
        )

    summaries.sort(key=lambda item: item.started_at or "", reverse=True)
    return summaries[:limit]


def get_workflow_detail(*, workflow_id: str | None = None, session_id: str | None = None) -> LLMWorkflowDetail | None:
    sessions = _load_session_workflows(session_id=session_id)
    session = None
    if workflow_id and workflow_id in sessions:
        session = sessions[workflow_id]
    elif session_id:
        for candidate in sessions.values():
            if getattr(candidate, "id", None) == session_id:
                session = candidate
                break

    workflow_debug = getattr(session, "analysis_workflow", None) or {}
    resolved_workflow_id = str(workflow_id or workflow_debug.get("workflow_id") or getattr(session, "id", "")).strip()
    resolved_session_id = str(session_id or getattr(session, "id", "") or workflow_debug.get("session_id") or "").strip() or None
    trace_limit = 400 if resolved_session_id else 200
    entries = [entry for entry in read_llm_trace_log(limit=trace_limit, session_id=resolved_session_id) if _is_session_workflow_entry(entry)]
    if resolved_workflow_id:
        entries = [entry for entry in entries if _workflow_group_key(entry) == resolved_workflow_id]

    if not entries and session is None:
        return None

    status = _workflow_status(entries, workflow_debug)
    started_at, ended_at, duration_ms = _workflow_times(entries, workflow_debug)
    prompt = _prompt_from_entries(entries)
    prompt_unavailable = not any([prompt.prompt_name, prompt.prompt_source, prompt.prompt_label, prompt.prompt_version])
    card_counts = _workflow_card_counts(entries, workflow_debug)
    repair_applied = bool(workflow_debug.get("repair_applied")) or any((entry.repair_attempt or 0) > 0 for entry in entries)
    drop_point = str(workflow_debug.get("drop_point") or "").strip() or None
    alumni = workflow_debug.get("alumni") if isinstance(workflow_debug.get("alumni"), dict) else {}
    failure_summary = _workflow_failure_summary(entries, workflow_debug)

    if status == "ok" and (card_counts.committed or 0) > 0:
        summary_text = f"{card_counts.committed} cards are ready to review."
        likely_cause = "The extraction, validation, and append path completed successfully."
        recommended_action = "Review the pending cards in the staging area."
    elif status == "started":
        summary_text = "This workflow is still analyzing the session."
        likely_cause = "The extraction path has started but has not written a terminal result yet."
        recommended_action = "Keep the summary view open; detail can refresh while the workflow is active."
    else:
        summary_text = "This workflow did not produce a clean review-ready result."
        likely_cause = failure_summary or "A downstream validation or append step dropped the cards."
        recommended_action = "Inspect the repair, validation, and append evidence below before retrying."

    limitations: list[str] = []
    if not entries:
        limitations.append("Trace detail is unavailable; showing router-side session evidence only.")
    if prompt_unavailable:
        limitations.append("Prompt version unavailable for this run.")
    if not workflow_debug.get("append"):
        limitations.append("Router append result was not recorded for this session.")
    if repair_applied and not any("repair" in step.label.lower() for step in _workflow_steps(entries, workflow_debug)):
        limitations.append("Repair output not available from fallback trace data.")

    return LLMWorkflowDetail(
        workflow_id=resolved_workflow_id or (entries[0].workflow_id if entries else str(getattr(session, "id", ""))),
        workflow_name=str(workflow_debug.get("workflow_name") or "session_card_analysis"),
        status=status,
        session_id=resolved_session_id,
        trace_ids=sorted({entry.trace_id for entry in entries}),
        started_at=started_at,
        ended_at=ended_at,
        duration_ms=duration_ms,
        prompt=prompt,
        model=next((entry.model for entry in entries if entry.model), None),
        summary=summary_text,
        likely_cause=likely_cause,
        recommended_action=recommended_action,
        drop_point=drop_point,
        alumni_path=str(alumni.get("result") or alumni.get("status") or "").strip() or None,
        prompt_provenance_unavailable=prompt_unavailable,
        context_pack_summary=workflow_debug.get("context_pack") if isinstance(workflow_debug.get("context_pack"), dict) else {},
        raw_output_summary=workflow_debug.get("raw_output") if isinstance(workflow_debug.get("raw_output"), dict) else {
            "latest_preview": next((entry.output_preview for entry in reversed(entries) if entry.output_preview), ""),
            "errors": [entry.error for entry in entries if entry.error],
        },
        repair_summary=workflow_debug.get("repair") if isinstance(workflow_debug.get("repair"), dict) else {
            "applied": repair_applied,
            "attempts": max((entry.repair_attempt or 0 for entry in entries), default=0),
        },
        parsed_payload_summary=workflow_debug.get("parsed_payload") if isinstance(workflow_debug.get("parsed_payload"), dict) else {
            "already_covered": card_counts.already_covered,
            "cards_raw": card_counts.raw,
            "cards_repaired": card_counts.repaired,
        },
        validation_summary=workflow_debug.get("validation") if isinstance(workflow_debug.get("validation"), dict) else {},
        append_summary=workflow_debug.get("append") if isinstance(workflow_debug.get("append"), dict) else {},
        card_counts=card_counts,
        scores=_workflow_scores(
            status=status,
            repair_applied=repair_applied,
            card_counts=card_counts,
            workflow_debug=workflow_debug,
        ),
        steps=_workflow_steps(entries, workflow_debug),
        limitations=limitations,
    )


_observation_to_trace_entries = observation_to_trace_entries
_read_langfuse_trace_log = read_langfuse_trace_log
_read_llm_trace_log = read_llm_trace_log
