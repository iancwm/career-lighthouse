"""Tracing helpers for LLM calls and Langfuse integration."""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable


def truncate_preview(text: str | None, limit: int) -> str:
    if not text:
        return ""
    clean = text.strip()
    if len(clean) <= limit:
        return clean
    return clean[:limit] + "…"


def mask_langfuse_value(
    data: Any,
    *,
    email_re: re.Pattern[str],
    phone_re: re.Pattern[str],
    api_key_re: re.Pattern[str],
    bearer_re: re.Pattern[str],
) -> Any:
    """Best-effort SDK-side masking for trace inputs, outputs, and metadata."""
    if isinstance(data, str):
        masked = email_re.sub("[EMAIL_REDACTED]", data)
        masked = phone_re.sub("[PHONE_REDACTED]", masked)
        masked = api_key_re.sub("[API_KEY_REDACTED]", masked)
        masked = bearer_re.sub("Bearer [REDACTED]", masked)
        return masked
    if isinstance(data, dict):
        return {
            key: mask_langfuse_value(
                value,
                email_re=email_re,
                phone_re=phone_re,
                api_key_re=api_key_re,
                bearer_re=bearer_re,
            )
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [
            mask_langfuse_value(
                item,
                email_re=email_re,
                phone_re=phone_re,
                api_key_re=api_key_re,
                bearer_re=bearer_re,
            )
            for item in data
        ]
    if isinstance(data, tuple):
        return [
            mask_langfuse_value(
                item,
                email_re=email_re,
                phone_re=phone_re,
                api_key_re=api_key_re,
                bearer_re=bearer_re,
            )
            for item in data
        ]
    if data is None or isinstance(data, (int, float, bool)):
        return data
    return str(data)


def langfuse_metadata_key(key: str) -> str:
    parts = [part for part in re.split(r"[^0-9A-Za-z]+", key) if part]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][0].lower() + parts[0][1:] if parts[0] else ""
    first = parts[0][0].lower() + parts[0][1:] if parts[0] else ""
    rest = "".join(part[:1].upper() + part[1:] for part in parts[1:] if part)
    return first + rest


def langfuse_metadata_value(value: object, *, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


def langfuse_is_enabled(settings: object) -> bool:
    return bool(
        getattr(settings, "langfuse_public_key", "")
        and getattr(settings, "langfuse_secret_key", "")
        and (
            getattr(settings, "langfuse_base_url", "")
            or getattr(settings, "langfuse_host", "")
        )
    )


def load_langfuse_symbols() -> tuple[object | None, object | None]:
    try:
        from langfuse import (
            Langfuse as langfuse_class,
            propagate_attributes as propagate_attrs,
        )
    except ImportError:  # pragma: no cover - optional dependency for local dev/tests
        return None, None
    return langfuse_class, propagate_attrs


def langfuse_endpoint(settings: object) -> str | None:
    endpoint = getattr(settings, "langfuse_host", "") or getattr(
        settings, "langfuse_base_url", ""
    )
    return endpoint or None


def langfuse_client_config_key(
    settings: object, *, endpoint: str | None
) -> tuple[Any, ...]:
    return (
        getattr(settings, "langfuse_public_key", ""),
        getattr(settings, "langfuse_secret_key", ""),
        endpoint,
        getattr(settings, "langfuse_timeout_seconds", None),
        getattr(settings, "langfuse_flush_at", None),
        getattr(settings, "langfuse_flush_interval", None),
        getattr(settings, "langfuse_tracing_environment", "development"),
    )


def start_langfuse_observation(client: object, logger: logging.Logger, **kwargs):
    try:
        return client.start_as_current_observation(**kwargs)
    except Exception:
        logger.warning(
            "Langfuse observation startup failed; continuing without tracing",
            exc_info=True,
        )
        return nullcontext()


def langfuse_input_payload(
    system: str,
    messages: list[dict],
    metadata: dict[str, object],
    max_tokens: int,
    timeout_seconds: float | None,
    *,
    truncate_preview_fn: Callable[[str | None], str],
    metadata_key_fn: Callable[[str], str],
) -> dict[str, Any]:
    message_summaries = []
    for message in messages:
        content = str(message.get("content", ""))
        message_summaries.append(
            {
                "role": message.get("role", "user"),
                "content_preview": truncate_preview_fn(content),
                "content_chars": len(content),
            }
        )

    normalized_metadata: dict[str, object] = dict(metadata)
    for key, value in metadata.items():
        normalized_key = metadata_key_fn(str(key))
        if normalized_key:
            normalized_metadata[normalized_key] = value

    return {
        "system_preview": truncate_preview_fn(system),
        "system_chars": len(system),
        "messages": message_summaries,
        "message_count": len(messages),
        "metadata": normalized_metadata,
        "max_tokens": max_tokens,
        "timeout_seconds": timeout_seconds,
    }


def langfuse_trace_metadata(
    settings: object,
    metadata: dict[str, object],
    trace_id: str,
    *,
    metadata_key_fn: Callable[[str], str],
    metadata_value_fn: Callable[[object], str | None],
) -> dict[str, str]:
    out: dict[str, str] = {
        "traceId": trace_id,
        "environment": str(
            getattr(settings, "langfuse_tracing_environment", "development")
        ),
    }
    for key, value in metadata.items():
        if value is None or key in {"trace_id", "traceId", "session_id", "sessionId"}:
            continue
        langfuse_key = metadata_key_fn(key)
        if not langfuse_key:
            continue
        masked_value = metadata_value_fn(value)
        if masked_value is None:
            continue
        out[langfuse_key] = masked_value
    return out


def langfuse_usage_details(response: object) -> dict[str, int] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    if input_tokens is None and output_tokens is None:
        return None
    details: dict[str, int] = {}
    if input_tokens is not None:
        details["input_tokens"] = int(input_tokens)
    if output_tokens is not None:
        details["output_tokens"] = int(output_tokens)
    return details or None


def append_llm_trace(path: Path, entry: dict[str, Any], logger: logging.Logger) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        logger.warning(
            "Failed to write LLM trace entry — request unaffected", exc_info=True
        )


@dataclass
class LLMTraceRecorder:
    operation: str
    model: str
    max_tokens: int
    system: str
    messages: list[dict]
    timeout_seconds: float | None
    trace_metadata: dict[str, object]
    get_langfuse_client: Callable[[], object | None]
    start_langfuse_observation_fn: Callable[..., Any]
    schedule_langfuse_flush: Callable[[], None]
    append_llm_trace_fn: Callable[[dict[str, Any]], None]
    langfuse_input_payload_fn: Callable[..., dict[str, Any]]
    langfuse_trace_metadata_fn: Callable[[dict[str, object], str], dict[str, str]]
    langfuse_usage_details_fn: Callable[[object], dict[str, int] | None]
    trace_metadata_int_fn: Callable[[dict[str, object], str, int | None], int | None]
    truncate_preview_fn: Callable[[str | None], str]
    propagate_attributes: Callable[..., Any] | None

    def run(self, call_api: Callable[[], object]) -> object:
        start = perf_counter()
        input_chars = len(self.system) + sum(
            len(str(message.get("content", ""))) for message in self.messages
        )
        trace_id = uuid.uuid4().hex
        input_preview = (
            self.truncate_preview_fn(self.messages[-1].get("content", ""))
            if self.messages
            else ""
        )
        metadata = self.trace_metadata or {}
        feature = str(metadata.get("feature") or self.operation)
        trace_entry_metadata: dict[str, object] = {
            **metadata,
            "feature": feature,
            "input_chars_pre_trim": self.trace_metadata_int_fn(
                metadata, "input_chars_pre_trim", input_chars
            ),
            "input_chars_sent": self.trace_metadata_int_fn(
                metadata, "input_chars_sent", input_chars
            ),
        }
        for field in (
            "workflow_id",
            "workflow_name",
            "kb_chunks_retrieved",
            "kb_chunks_sent",
            "parse_attempt",
            "repair_attempt",
            "partial_result",
            "prompt_name",
            "prompt_source",
            "prompt_label",
            "prompt_version",
            "schema_name",
            "domain_mix",
            "repair_applied",
            "card_count_raw",
            "card_count_repaired",
            "card_count_committed",
        ):
            if field in metadata and metadata[field] is not None:
                trace_entry_metadata[field] = metadata[field]

        langfuse_client = self.get_langfuse_client()
        observation_cm = nullcontext()
        if langfuse_client is not None:
            observation_cm = self.start_langfuse_observation_fn(
                langfuse_client,
                as_type="generation",
                name=self.operation,
                model=self.model,
                input=self.langfuse_input_payload_fn(
                    self.system,
                    self.messages,
                    {**trace_entry_metadata, "traceId": trace_id, "trace_id": trace_id},
                    self.max_tokens,
                    self.timeout_seconds,
                ),
            )

        self.append_llm_trace_fn(
            {
                "trace_id": trace_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "operation": self.operation,
                "status": "started",
                "model": self.model,
                **trace_entry_metadata,
                "timeout_seconds": self.timeout_seconds,
                "max_tokens": self.max_tokens,
                "latency_ms": 0.0,
                "input_chars": input_chars,
                "output_chars": 0,
                "input_preview": input_preview,
                "output_preview": "",
                "error": None,
            }
        )

        with observation_cm as lf_observation:
            if lf_observation is not None and self.propagate_attributes is not None:
                try:
                    propagate_kwargs: dict[str, object] = {
                        "trace_name": self.operation,
                    }
                    if metadata.get("session_id"):
                        propagate_kwargs["session_id"] = str(metadata["session_id"])
                    langfuse_metadata = self.langfuse_trace_metadata_fn(
                        metadata, trace_id
                    )
                    if langfuse_metadata:
                        propagate_kwargs["metadata"] = langfuse_metadata
                    attr_cm = self.propagate_attributes(**propagate_kwargs)
                except Exception:
                    attr_cm = nullcontext()
            else:
                attr_cm = nullcontext()

            with attr_cm:
                try:
                    response = call_api()
                except Exception as exc:
                    elapsed_ms = round((perf_counter() - start) * 1000, 1)
                    error_message = (
                        str(getattr(exc, "detail", None))
                        if getattr(exc, "detail", None) is not None
                        else str(exc) or exc.__class__.__name__
                    )
                    self.append_llm_trace_fn(
                        {
                            "trace_id": trace_id,
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "operation": self.operation,
                            "status": "error",
                            "model": self.model,
                            **trace_entry_metadata,
                            "timeout_seconds": self.timeout_seconds,
                            "max_tokens": self.max_tokens,
                            "latency_ms": elapsed_ms,
                            "input_chars": input_chars,
                            "output_chars": 0,
                            "input_preview": input_preview,
                            "output_preview": "",
                            "error_class": exc.__class__.__name__,
                            "error": error_message,
                        }
                    )
                    if lf_observation is not None:
                        lf_observation.update(
                            level="ERROR",
                            status_message=error_message,
                            metadata=self.langfuse_trace_metadata_fn(
                                {
                                    **trace_entry_metadata,
                                    "timeout_seconds": self.timeout_seconds,
                                    "max_tokens": self.max_tokens,
                                    "error": error_message,
                                },
                                trace_id,
                            ),
                        )
                    self.schedule_langfuse_flush()
                    raise

                output_text = ""
                if getattr(response, "content", None):
                    first = response.content[0]
                    output_text = getattr(first, "text", "") or ""

                elapsed_ms = round((perf_counter() - start) * 1000, 1)
                usage_details = self.langfuse_usage_details_fn(response)
                self.append_llm_trace_fn(
                    {
                        "trace_id": trace_id,
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "operation": self.operation,
                        "status": "ok",
                        "model": self.model,
                        **trace_entry_metadata,
                        "timeout_seconds": self.timeout_seconds,
                        "max_tokens": self.max_tokens,
                        "latency_ms": elapsed_ms,
                        "input_chars": input_chars,
                        "output_chars": len(output_text),
                        "input_preview": input_preview,
                        "output_preview": self.truncate_preview_fn(output_text),
                        "error": None,
                    }
                )
                if lf_observation is not None:
                    lf_observation.update(
                        output=self.truncate_preview_fn(output_text),
                        usage_details=usage_details,
                        metadata=self.langfuse_trace_metadata_fn(
                            {
                                **trace_entry_metadata,
                                "timeout_seconds": self.timeout_seconds,
                                "max_tokens": self.max_tokens,
                                "output_chars": len(output_text),
                            },
                            trace_id,
                        ),
                    )
                self.schedule_langfuse_flush()
                return response
