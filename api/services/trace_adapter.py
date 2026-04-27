"""Adapters for presenting LLM trace data to the admin API."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta

from config import settings
from models_kb import LLMTraceEntry
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
    }

    started = LLMTraceEntry(
        trace_id=trace_id,
        ts=start_ts,
        operation=operation,
        status="started",
        model=model,
        feature=trace_meta["feature"],
        session_id=str(session_id) if session_id is not None else None,
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


_observation_to_trace_entries = observation_to_trace_entries
_read_langfuse_trace_log = read_langfuse_trace_log
_read_llm_trace_log = read_llm_trace_log
