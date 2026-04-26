"""LLM service — Claude API integration for career advisory tasks.

This module provides:
- chat_with_context(): multi-turn conversations with KB context injection
- analyse_kb_input(): structured analysis of counselor input for KB updates
- generate_track_draft(): create new career track profiles from research
- generate_session_intents(): extract structured update intents from notes
- generate_brief(): pre-meeting advisor brief from resume + KB

All prompts and model parameters are loaded from cfg/ YAML files.
"""
import json
import logging
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import anthropic
from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from constants.profile_fields import ALLOWED_ALUMNI_FIELDS, ALLOWED_ALUMNI_LINK_FIELDS
from config import settings
from models_employers import AlumniExtractionPreview
from services.ingestion import chunk_text
from models_facts import Fact
from models_kb import KBAnalysisResult
from models_tracks import DraftTrackDetail
from utils.sanitization import sanitize_for_prompt

logger = logging.getLogger(__name__)
from cfg import model_cfg, kb_cfg, prompts_cfg

_clients: dict[int, anthropic.Anthropic] = {}
_langfuse_client = None
_langfuse_client_config: tuple | None = None
_langfuse_class = None
propagate_attributes = None
_langfuse_flush_executor: ThreadPoolExecutor | None = None
_TRACE_PREVIEW_CHARS = 500
_LANGFUSE_METADATA_VALUE_LIMIT = 200
_LANGFUSE_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_LANGFUSE_PHONE_RE = re.compile(r"(?<!\w)\+?(?:\d[\d\s().-]*[\s().-][\d\s().-]*\d)(?!\w)")
_LANGFUSE_API_KEY_RE = re.compile(r"\b(?:sk|pk|key|secret)[_-][A-Za-z0-9_-]{8,}\b")
_LANGFUSE_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._-]+\b", re.IGNORECASE)

_llm = model_cfg["llm"]
_prompts = prompts_cfg.get("prompts", {})
SCHOOL_NAME = model_cfg["school"]["name"]


def _llm_setting(setting_name: str, model_key: str, default: Any = None) -> Any:
    value = getattr(settings, setting_name, None)
    if value is not None:
        return value
    return _llm.get(model_key, default)


def _llm_int(setting_name: str, model_key: str, default: int) -> int:
    value = _llm_setting(setting_name, model_key, default)
    if value is None:
        return int(default)
    return int(value)


def _llm_bool(setting_name: str, model_key: str, default: bool) -> bool:
    value = _llm_setting(setting_name, model_key, default)
    return bool(value)


def _model_validate(model_cls: type[BaseModel], data: Any) -> BaseModel:
    validator = getattr(model_cls, "model_validate", None)
    if callable(validator):
        return validator(data)
    return model_cls.parse_obj(data)


def _effective_session_multi_pass_setting(setting_name: str, model_key: str) -> int:
    value = getattr(settings, setting_name, None)
    if value is not None:
        return int(value)
    return int(_llm[model_key])


def get_model_name() -> str:
    return getattr(settings, "anthropic_model", "") or _llm["model"]


def _trace_metadata_int(metadata: dict[str, object], key: str, default: int | None = None) -> int | None:
    value = metadata.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_client(max_retries: int = 2):
    client = _clients.get(max_retries)
    if client is None:
        client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=max_retries,
        )
        _clients[max_retries] = client
    return client


def _safe_create(*, timeout_seconds: float | None = None, max_retries: int | None = None, **kwargs):
    """Call client.messages.create() with timeout/connection error handling.

    Raises HTTP 504 on timeout and HTTP 502 on connection failure so callers
    receive a structured error response instead of hanging workers.
    """
    if timeout_seconds is not None:
        kwargs["timeout"] = timeout_seconds
    try:
        client = get_client() if max_retries is None else get_client(max_retries=max_retries)
        return client.messages.create(**kwargs)
    except anthropic.APITimeoutError:
        raise HTTPException(status_code=504, detail="LLM service timeout")
    except anthropic.APIConnectionError:
        raise HTTPException(status_code=502, detail="LLM service unavailable")


def _truncate_preview(text: str | None, limit: int = _TRACE_PREVIEW_CHARS) -> str:
    if not text:
        return ""
    clean = text.strip()
    if len(clean) <= limit:
        return clean
    return clean[:limit] + "…"


def _mask_langfuse_value(data: Any) -> Any:
    """Best-effort SDK-side masking for trace inputs, outputs, and metadata."""
    if isinstance(data, str):
        masked = _LANGFUSE_EMAIL_RE.sub("[EMAIL_REDACTED]", data)
        masked = _LANGFUSE_PHONE_RE.sub("[PHONE_REDACTED]", masked)
        masked = _LANGFUSE_API_KEY_RE.sub("[API_KEY_REDACTED]", masked)
        masked = _LANGFUSE_BEARER_RE.sub("Bearer [REDACTED]", masked)
        return masked
    if isinstance(data, dict):
        return {key: _mask_langfuse_value(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_mask_langfuse_value(item) for item in data]
    if isinstance(data, tuple):
        return [_mask_langfuse_value(item) for item in data]
    if data is None or isinstance(data, (int, float, bool)):
        return data
    return str(data)


def _langfuse_metadata_key(key: str) -> str:
    """Convert a snake_case key into Langfuse-safe camelCase metadata."""
    parts = [part for part in re.split(r"[^0-9A-Za-z]+", key) if part]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][0].lower() + parts[0][1:] if parts[0] else ""
    first = parts[0][0].lower() + parts[0][1:] if parts[0] else ""
    rest = "".join(part[:1].upper() + part[1:] for part in parts[1:] if part)
    return first + rest


def _langfuse_metadata_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    if len(text) > _LANGFUSE_METADATA_VALUE_LIMIT:
        text = text[: _LANGFUSE_METADATA_VALUE_LIMIT - 1] + "…"
    return text


def _langfuse_is_enabled() -> bool:
    return bool(
        getattr(settings, "langfuse_public_key", "")
        and getattr(settings, "langfuse_secret_key", "")
        and (
            getattr(settings, "langfuse_base_url", "")
            or getattr(settings, "langfuse_host", "")
        )
    )


def _load_langfuse_symbols() -> None:
    global _langfuse_class, propagate_attributes
    if _langfuse_class is not None and propagate_attributes is not None:
        return
    try:
        from langfuse import Langfuse as _Langfuse, propagate_attributes as _propagate_attributes
    except ImportError:  # pragma: no cover - optional dependency for local dev/tests
        return
    _langfuse_class = _Langfuse
    propagate_attributes = _propagate_attributes


def _langfuse_endpoint() -> str | None:
    endpoint = getattr(settings, "langfuse_host", "") or getattr(settings, "langfuse_base_url", "")
    return endpoint or None


def _langfuse_client_config_key() -> tuple:
    return (
        getattr(settings, "langfuse_public_key", ""),
        getattr(settings, "langfuse_secret_key", ""),
        _langfuse_endpoint(),
        getattr(settings, "langfuse_timeout_seconds", None),
        getattr(settings, "langfuse_flush_at", None),
        getattr(settings, "langfuse_flush_interval", None),
        getattr(settings, "langfuse_tracing_environment", "development"),
    )


def _get_langfuse_client():
    global _langfuse_client, _langfuse_client_config
    if not _langfuse_is_enabled():
        return None
    _load_langfuse_symbols()
    if _langfuse_class is None:
        return None
    config_key = _langfuse_client_config_key()
    if _langfuse_client is None or _langfuse_client_config != config_key:
        try:
            _langfuse_client = _langfuse_class(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                base_url=_langfuse_endpoint(),
                timeout=getattr(settings, "langfuse_timeout_seconds", 20),
                tracing_enabled=True,
                flush_at=getattr(settings, "langfuse_flush_at", 1),
                flush_interval=getattr(settings, "langfuse_flush_interval", 1.0),
                environment=getattr(settings, "langfuse_tracing_environment", "development"),
                mask=_mask_langfuse_value,
            )
            _langfuse_client_config = config_key
        except Exception:
            logger.warning("Langfuse client initialization failed; continuing without tracing", exc_info=True)
            return None
    return _langfuse_client


def _start_langfuse_observation(client, **kwargs):
    try:
        return client.start_as_current_observation(**kwargs)
    except Exception:
        logger.warning("Langfuse observation startup failed; continuing without tracing", exc_info=True)
        return nullcontext()


def _schedule_langfuse_flush() -> None:
    if not _langfuse_is_enabled():
        return
    global _langfuse_flush_executor
    if _langfuse_flush_executor is None:
        _langfuse_flush_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="langfuse-flush")
    try:
        _langfuse_flush_executor.submit(flush_langfuse_traces)
    except Exception:
        logger.warning("Failed to schedule Langfuse flush", exc_info=True)


def _langfuse_input_payload(system: str, messages: list[dict], metadata: dict[str, object], max_tokens: int, timeout_seconds: float | None) -> dict:
    """Build the Langfuse input payload dict with content previews and char counts instead of full text."""
    message_summaries = []
    for message in messages:
        content = str(message.get("content", ""))
        message_summaries.append({
            "role": message.get("role", "user"),
            "content_preview": _truncate_preview(content),
            "content_chars": len(content),
        })
    normalized_metadata: dict[str, object] = dict(metadata)
    for key, value in metadata.items():
        normalized_key = _langfuse_metadata_key(str(key))
        if normalized_key:
            normalized_metadata[normalized_key] = value
    return {
        "system_preview": _truncate_preview(system),
        "system_chars": len(system),
        "messages": message_summaries,
        "message_count": len(messages),
        "metadata": normalized_metadata,
        "max_tokens": max_tokens,
        "timeout_seconds": timeout_seconds,
    }


def _langfuse_trace_metadata(metadata: dict[str, object], trace_id: str) -> dict[str, str]:
    """Convert internal trace metadata to the camelCase string dict expected by the Langfuse SDK, stripping None values and reserved keys."""
    out: dict[str, str] = {
        "traceId": trace_id,
        "environment": str(getattr(settings, "langfuse_tracing_environment", "development")),
    }
    for key, value in metadata.items():
        if value is None or key in {"trace_id", "traceId", "session_id", "sessionId"}:
            continue
        langfuse_key = _langfuse_metadata_key(key)
        if not langfuse_key:
            continue
        masked_value = _langfuse_metadata_value(value)
        if masked_value is None:
            continue
        out[langfuse_key] = masked_value
    return out


def _langfuse_usage_details(response: object) -> dict[str, int] | None:
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


def _append_llm_trace(entry: dict) -> None:
    path = Path(settings.llm_trace_log_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        logger.warning("Failed to write LLM trace entry — request unaffected", exc_info=True)


def _response_text(response: object) -> str:
    if not getattr(response, "content", None):
        raise ValueError("Claude returned an empty or non-text response")
    first = response.content[0]
    text = getattr(first, "text", "") or ""
    text = text.strip()
    if not text:
        raise ValueError("Claude returned an empty or non-text response")
    return text


def _extract_json_block(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        if "\n" in text:
            text = text.split("\n", 1)[1]
        else:
            text = ""
        if "```" in text:
            text = text.rsplit("```", 1)[0]
    text = text.strip()
    if not text:
        return text

    # Prefer the outermost object/array if the model wrapped the JSON in prose.
    obj_start = text.find("{")
    obj_end = text.rfind("}")
    arr_start = text.find("[")
    arr_end = text.rfind("]")

    has_obj = obj_start != -1 and obj_end != -1 and obj_end > obj_start
    has_arr = arr_start != -1 and arr_end != -1 and arr_end > arr_start

    if has_obj and has_arr:
        # Return whichever bracket opens first (outermost structure)
        if arr_start < obj_start:
            return text[arr_start:arr_end + 1].strip()
        return text[obj_start:obj_end + 1].strip()
    if has_obj:
        return text[obj_start:obj_end + 1].strip()
    if has_arr:
        return text[arr_start:arr_end + 1].strip()
    return text


def _parse_json_payload(text: str) -> Any:
    return json.loads(_extract_json_block(text))


def _json_dumps_safe(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    except Exception:
        return str(value)


def _json_repair_enabled() -> bool:
    return _llm_bool("llm_json_repair_enabled", "json_repair_enabled", True)


def _staged_extraction_enabled() -> bool:
    return _llm_bool("llm_staged_extraction_enabled", "staged_extraction_enabled", True)


def _repair_json_output(
    *,
    raw_text: str,
    schema_name: str,
    schema_hint: str,
    operation: str,
    model: str,
    max_tokens: int = 512,
    timeout_seconds: float | None = None,
    trace_metadata: dict[str, object] | None = None,
    max_retries: int | None = 2,
) -> dict | list:
    if not _json_repair_enabled():
        raise ValueError(f"{schema_name} JSON repair is disabled")

    repair_source = raw_text
    parse_error_text: str | None = None
    last_error: Exception | None = None

    for repair_attempt in (1, 2):
        repair_system = (
            f"You repair malformed JSON for {schema_name}.\n"
            "Return ONLY valid JSON. Do not add markdown or explanation.\n"
            f"Schema hint: {schema_hint}\n"
            "Fix the JSON below and preserve the original meaning as closely as possible."
        )
        if parse_error_text:
            repair_system += f"\nThe previous JSON parse attempt failed with: {parse_error_text}"

        repair_user = f"Malformed JSON:\n{repair_source}"
        response = _call_with_trace(
            operation=f"{operation}_json_repair",
            model=model,
            max_tokens=max_tokens,
            system=repair_system,
            messages=[{"role": "user", "content": repair_user}],
            timeout_seconds=timeout_seconds,
            trace_metadata={
                **(trace_metadata or {}),
                "phase": "json_repair",
                "schema_name": schema_name,
                "parse_attempt": 2,
                "repair_attempt": repair_attempt,
                "input_chars_pre_trim": len(repair_source),
            },
            max_retries=max_retries,
        )
        repaired_text = _response_text(response)
        try:
            repaired = _parse_json_payload(repaired_text)
        except Exception as exc:
            last_error = exc
            parse_error_text = str(exc)
            repair_source = repaired_text
            continue

        if isinstance(repaired, (dict, list)):
            return repaired

        last_error = ValueError(f"{schema_name} repair did not return a JSON object or array")
        parse_error_text = str(last_error)
        repair_source = _json_dumps_safe(repaired)

    raise ValueError(f"{schema_name} repair did not return a valid JSON object") from last_error


def _validate_or_repair(
    *,
    parsed: dict,
    raw_text: str,
    schema_name: str,
    schema_hint: str,
    operation: str,
    model: str,
    validator: type[BaseModel] | None,
    max_tokens: int = 512,
    timeout_seconds: float | None = None,
    trace_metadata: dict[str, object] | None = None,
    max_retries: int | None = 2,
) -> Any:
    if validator is None:
        return parsed

    try:
        return _model_validate(validator, parsed)
    except (ValidationError, ValueError, TypeError) as exc:
        logger.debug("%s validation failed, attempting repair: %s", schema_name, exc)
        parsed_text = _json_dumps_safe(parsed)
        repaired = _repair_json_output(
            raw_text=parsed_text if parsed_text.strip() else raw_text,
            schema_name=schema_name,
            schema_hint=schema_hint,
            operation=operation,
            model=model,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            trace_metadata=trace_metadata,
            max_retries=max_retries,
        )
        return _model_validate(validator, repaired)


def call_structured_json(
    *,
    operation: str,
    model: str,
    system: str,
    user: str,
    schema_name: str,
    schema_hint: str,
    max_tokens: int,
    timeout_seconds: float | None = None,
    trace_metadata: dict[str, object] | None = None,
    validator: type[BaseModel] | None = None,
    max_repair_tokens: int = 8192,
    max_retries: int | None = 2,
) -> Any:
    response = _call_with_trace(
        operation=operation,
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        timeout_seconds=timeout_seconds,
        trace_metadata={
            **(trace_metadata or {}),
            "parse_attempt": 1,
            "repair_attempt": 0,
            "input_chars_pre_trim": len(user),
        },
        temperature=0,
        max_retries=max_retries,
    )
    raw_text = _response_text(response)
    try:
        parsed = _parse_json_payload(raw_text)
    except Exception:
        parsed = _repair_json_output(
            raw_text=raw_text,
            schema_name=schema_name,
            schema_hint=schema_hint,
            operation=operation,
            model=model,
            max_tokens=max_repair_tokens,
            timeout_seconds=timeout_seconds,
            trace_metadata=trace_metadata,
        )
    if not isinstance(parsed, dict):
        parsed = _repair_json_output(
            raw_text=_json_dumps_safe(parsed),
            schema_name=schema_name,
            schema_hint=schema_hint,
            operation=operation,
            model=model,
            max_tokens=max_repair_tokens,
            timeout_seconds=timeout_seconds,
            trace_metadata=trace_metadata,
        )
    if not isinstance(parsed, dict):
        raise ValueError(f"{schema_name} must be a JSON object")
    return _validate_or_repair(
        parsed=parsed,
        raw_text=raw_text,
        schema_name=schema_name,
        schema_hint=schema_hint,
        operation=operation,
        model=model,
        validator=validator,
        max_tokens=max_repair_tokens,
        timeout_seconds=timeout_seconds,
        trace_metadata=trace_metadata,
        max_retries=max_retries,
    )


def _trim_to_budget(text: str, budget: int | None) -> str:
    text = text.strip()
    if budget is None or budget <= 0:
        return text
    if len(text) <= budget:
        return text
    return text[:budget].rstrip()


def _budget_chunks(
    chunks: list[dict],
    *,
    max_chunks: int | None,
    excerpt_chars: int | None,
    max_chunk_chars: int | None = None,
) -> list[dict]:
    limited = chunks[:max_chunks] if max_chunks is not None else list(chunks)
    budgeted: list[dict] = []
    char_budget = excerpt_chars
    if max_chunk_chars is not None and max_chunk_chars > 0:
        char_budget = min(char_budget, max_chunk_chars) if char_budget is not None else max_chunk_chars
    for chunk in limited:
        payload = chunk.get("payload", {}) if isinstance(chunk, dict) else {}
        budgeted.append({
            "score": chunk.get("score") if isinstance(chunk, dict) else None,
            "payload": {
                "source_filename": payload.get("source_filename", "unknown"),
                "text": _trim_to_budget(str(payload.get("text", "")), char_budget),
            },
        })
    return budgeted


def _join_budgeted_sections(sections: list[str], *, max_context_chars: int | None) -> str:
    cleaned = [section.strip() for section in sections if section and section.strip()]
    if not cleaned:
        return ""
    if max_context_chars is None or max_context_chars <= 0:
        return "\n\n".join(cleaned)

    out: list[str] = []
    remaining = max_context_chars
    for section in cleaned:
        if remaining <= 0:
            break
        if len(section) <= remaining:
            out.append(section)
            remaining -= len(section)
            continue
        out.append(section[:remaining].rstrip())
        break
    return "\n\n".join(out)


def _normalize_existing_alumni_candidates(existing_alumni: list[dict[str, Any]] | None) -> list[dict[str, str | None]]:
    candidates: list[dict[str, str | None]] = []
    for raw in existing_alumni or []:
        if not isinstance(raw, dict):
            continue
        slug = str(raw.get("slug") or "").strip() or None
        full_name = str(raw.get("full_name") or raw.get("name") or "").strip() or None
        current_company = str(raw.get("current_company") or "").strip() or None
        current_title = str(raw.get("current_title") or "").strip() or None
        if not slug and not full_name:
            continue
        candidates.append({
            "slug": slug,
            "full_name": full_name,
            "current_company": current_company,
            "current_title": current_title,
        })
    return candidates


def _validated_alumni_preview_payload(
    payload: dict[str, Any],
    *,
    source_label: str,
    source_type: str,
) -> dict[str, Any]:
    preview = _model_validate(
        AlumniExtractionPreview,
        {
            "summary_bullets": payload.get("summary_bullets") or [],
            "profile_proposals": payload.get("profile_proposals") or {},
            "company_link_proposals": payload.get("company_link_proposals") or [],
            "fit_triad": payload.get("fit_triad") or {},
            "source_label": payload.get("source_label") or source_label,
            "source_type": payload.get("source_type") or source_type,
        },
    )
    return preview.model_dump()


def _budget_history(history: list[dict], *, max_turns: int, max_chars: int | None) -> str:
    lines = []
    for message in history[-max_turns:]:
        role = str(message.get("role", "user")).upper()
        content = _trim_to_budget(str(message.get("content", "")), max_chars)
        lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "None"


def _call_with_trace(
    *,
    operation: str,
    model: str,
    max_tokens: int,
    system: str,
    messages: list[dict],
    timeout_seconds: float | None = None,
    trace_metadata: dict[str, object] | None = None,
    **kwargs,
) -> object:
    """Call the Anthropic API with full observability: emits started/ok/error JSONL trace entries and a Langfuse generation span."""
    start = perf_counter()
    input_chars = len(system) + sum(len(str(message.get("content", ""))) for message in messages)
    trace_id = uuid.uuid4().hex
    input_preview = _truncate_preview(messages[-1].get("content", "")) if messages else ""
    metadata = trace_metadata or {}
    feature = str(metadata.get("feature") or operation)
    trace_entry_metadata: dict[str, object] = {
        **metadata,
        "feature": feature,
        "input_chars_pre_trim": _trace_metadata_int(metadata, "input_chars_pre_trim", input_chars),
        "input_chars_sent": _trace_metadata_int(metadata, "input_chars_sent", input_chars),
    }
    for field in (
        "kb_chunks_retrieved",
        "kb_chunks_sent",
        "parse_attempt",
        "repair_attempt",
        "partial_result",
    ):
        if field in metadata and metadata[field] is not None:
            trace_entry_metadata[field] = metadata[field]
    langfuse_client = _get_langfuse_client()
    observation_cm = nullcontext()
    if langfuse_client is not None:
        observation_cm = _start_langfuse_observation(
            langfuse_client,
            as_type="generation",
            name=operation,
            model=model,
            input=_langfuse_input_payload(system, messages, {**trace_entry_metadata, "traceId": trace_id, "trace_id": trace_id}, max_tokens, timeout_seconds),
        )
    _append_llm_trace({
        "trace_id": trace_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "operation": operation,
        "status": "started",
        "model": model,
        **trace_entry_metadata,
        "timeout_seconds": timeout_seconds,
        "max_tokens": max_tokens,
        "latency_ms": 0.0,
        "input_chars": input_chars,
        "output_chars": 0,
        "input_preview": input_preview,
        "output_preview": "",
        "error": None,
    })
    with observation_cm as lf_observation:
        if lf_observation is not None and propagate_attributes is not None:
            try:
                propagate_kwargs: dict[str, object] = {
                    "trace_name": operation,
                }
                if metadata.get("session_id"):
                    propagate_kwargs["session_id"] = str(metadata["session_id"])
                langfuse_metadata = _langfuse_trace_metadata(metadata, trace_id)
                if langfuse_metadata:
                    propagate_kwargs["metadata"] = langfuse_metadata
                attr_cm = propagate_attributes(**propagate_kwargs)
            except Exception:
                logger.warning("Langfuse propagation failed; continuing without tracing", exc_info=True)
                attr_cm = nullcontext()
        else:
            attr_cm = nullcontext()
        with attr_cm:
            try:
                response = _safe_create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=messages,
                    timeout_seconds=timeout_seconds,
                    **kwargs,
                )
            except HTTPException as exc:
                elapsed_ms = round((perf_counter() - start) * 1000, 1)
                error_message = str(exc.detail)
                _append_llm_trace({
                    "trace_id": trace_id,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "operation": operation,
                    "status": "error",
                    "model": model,
                    **trace_entry_metadata,
                    "timeout_seconds": timeout_seconds,
                    "max_tokens": max_tokens,
                    "latency_ms": elapsed_ms,
                    "input_chars": input_chars,
                    "output_chars": 0,
                    "input_preview": input_preview,
                    "output_preview": "",
                    "error": error_message,
                })
                if lf_observation is not None:
                    lf_observation.update(
                        level="ERROR",
                        status_message=error_message,
                        metadata=_langfuse_trace_metadata(
                            {
                                **trace_entry_metadata,
                                "timeout_seconds": timeout_seconds,
                                "max_tokens": max_tokens,
                                "error": error_message,
                            },
                            trace_id,
                        ),
                )
                _schedule_langfuse_flush()
                raise
            except Exception as exc:
                elapsed_ms = round((perf_counter() - start) * 1000, 1)
                error_message = str(exc) or exc.__class__.__name__
                _append_llm_trace({
                    "trace_id": trace_id,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "operation": operation,
                    "status": "error",
                    "model": model,
                    **trace_entry_metadata,
                    "timeout_seconds": timeout_seconds,
                    "max_tokens": max_tokens,
                    "latency_ms": elapsed_ms,
                    "input_chars": input_chars,
                    "output_chars": 0,
                    "input_preview": input_preview,
                    "output_preview": "",
                    "error": error_message,
                })
                if lf_observation is not None:
                    lf_observation.update(
                        level="ERROR",
                        status_message=error_message,
                        metadata=_langfuse_trace_metadata(
                            {
                                **trace_entry_metadata,
                                "timeout_seconds": timeout_seconds,
                                "max_tokens": max_tokens,
                                "error": error_message,
                            },
                            trace_id,
                        ),
                    )
                _schedule_langfuse_flush()
                raise

            output_text = ""
            if getattr(response, "content", None):
                first = response.content[0]
                output_text = getattr(first, "text", "") or ""

            elapsed_ms = round((perf_counter() - start) * 1000, 1)
            usage_details = _langfuse_usage_details(response)
            _append_llm_trace({
                "trace_id": trace_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "operation": operation,
                "status": "ok",
                "model": model,
                **trace_entry_metadata,
                "timeout_seconds": timeout_seconds,
                "max_tokens": max_tokens,
                "latency_ms": elapsed_ms,
                "input_chars": input_chars,
                "output_chars": len(output_text),
                "input_preview": input_preview,
                "output_preview": _truncate_preview(output_text),
                "error": None,
            })
            if lf_observation is not None:
                lf_observation.update(
                    output=_truncate_preview(output_text),
                    usage_details=usage_details,
                    metadata=_langfuse_trace_metadata(
                        {
                            **trace_entry_metadata,
                            "timeout_seconds": timeout_seconds,
                            "max_tokens": max_tokens,
                            "output_chars": len(output_text),
                        },
                        trace_id,
                    ),
                )
            _schedule_langfuse_flush()
            return response


def flush_langfuse_traces() -> None:
    client = _get_langfuse_client()
    if client is None:
        return
    try:
        client.flush()
    except Exception:
        logger.warning("Failed to flush Langfuse traces", exc_info=True)


def shutdown_langfuse_traces() -> None:
    global _langfuse_flush_executor
    if _langfuse_flush_executor is not None:
        try:
            _langfuse_flush_executor.shutdown(wait=True, cancel_futures=False)
        except Exception:
            logger.warning("Failed to stop Langfuse flush executor", exc_info=True)
        finally:
            _langfuse_flush_executor = None
    client = _get_langfuse_client()
    if client is None:
        return
    try:
        client.shutdown()
    except Exception:
        logger.warning("Failed to shutdown Langfuse traces", exc_info=True)


def chat_with_context(message: str, resume_text: str | None,
                      chunks: list[dict], history: list[dict],
                      career_context: str | None = None,
                      employer_context: str | None = None) -> str:
    """Chat with context injection for multi-turn career advising conversations.

    Injects structured context blocks in a specific order:
    1. Career profile context (if matched)
    2. Employer facts (if applicable to the career type)
    3. KB chunks (retrieved by semantic search)
    4. Conversation history (most recent N turns)

    Automatically adds a disambiguation prompt if no career type is active,
    guiding students to clarify their focus area.

    Args:
        message: student question
        resume_text: student resume (optional)
        chunks: KB chunks retrieved by semantic search
        history: prior conversation turns
        career_context: formatted career profile block (from profile_to_context_block)
        employer_context: formatted employer facts

    Returns:
        LLM response text.
    """
    generic_max_chunks = _llm_int("llm_max_chunks_per_prompt", "max_chunks_per_prompt", 8)
    max_chunks = min(_llm_int("llm_chat_max_chunks", "chat_max_chunks", 5), generic_max_chunks)
    excerpt_chars = _llm_int("llm_chat_excerpt_preview_chars", "chat_excerpt_preview_chars", int(_llm["excerpt_preview_chars"]))
    max_chunk_chars = _llm_int("llm_max_chunk_chars_for_prompt", "max_chunk_chars_for_prompt", 4000)
    max_context_chars = _llm_int("llm_chat_max_context_chars", "chat_max_context_chars", 12000)
    max_resume_chars = _llm_int("llm_chat_max_resume_chars", "chat_max_resume_chars", 5000)
    history_window = int(_llm["history_window"])

    kb_chunks_retrieved = len(chunks)
    budgeted_chunks = _budget_chunks(chunks, max_chunks=max_chunks, excerpt_chars=excerpt_chars, max_chunk_chars=max_chunk_chars)
    kb_text = "\n\n---\n\n".join(
        f"[{c['payload']['source_filename']}]\n{c['payload']['text']}"
        for c in budgeted_chunks
    )
    raw_history_text = _budget_history(history, max_turns=history_window, max_chars=None) if history else "None"
    history_text = _budget_history(history, max_turns=history_window, max_chars=max_context_chars // 2 if max_context_chars else None) if history else "None"

    safe_career_context = sanitize_for_prompt(career_context) if career_context else None
    safe_employer_context = sanitize_for_prompt(employer_context) if employer_context else None

    # Injection order: career profile → employer facts → KB chunks
    # Employer facts always appear before KB chunks so authoritative YAML data
    # supersedes any stale chunk content about the same employers.
    raw_context_sections = []
    if safe_career_context:
        raw_context_sections.append(safe_career_context)
    if safe_employer_context:
        if safe_career_context:
            raw_context_sections.insert(1, safe_employer_context)
        else:
            raw_context_sections.insert(0, safe_employer_context)
    raw_context_sections.append(f"School knowledge base:\n{kb_text or 'No documents uploaded yet.'}")
    raw_combined_context = "\n\n".join(raw_context_sections)

    context_sections = []
    if safe_career_context:
        context_sections.append(_trim_to_budget(safe_career_context, max_context_chars))
    if safe_employer_context:
        if safe_career_context:
            context_sections.insert(1, _trim_to_budget(safe_employer_context, max_context_chars))
        else:
            context_sections.insert(0, _trim_to_budget(safe_employer_context, max_context_chars))
    context_sections.append(f"School knowledge base:\n{kb_text or 'No documents uploaded yet.'}")
    combined_context = "\n\n".join(context_sections)

    # Disambiguation instruction: injected when no career type is active, so the
    # LLM naturally asks the student to clarify their track rather than giving a
    # generic answer.
    disambiguation_note = (
        ""
        if career_context
        else "\n\n" + _prompts["disambiguation"]
    )

    resume_section = f"Student resume:\n{_trim_to_budget(resume_text or 'Not provided', max_resume_chars)}"
    context_section = combined_context
    history_section = f"Conversation so far:\n{history_text}"
    question_section = f"Student question: {message}"
    raw_resume_section = f"Student resume:\n{resume_text or 'Not provided'}"
    raw_history_section = f"Conversation so far:\n{raw_history_text}"
    input_chars_pre_trim = sum(
        len(section)
        for section in (
            raw_resume_section,
            raw_combined_context,
            raw_history_section,
            question_section,
        )
        if section
    )
    core_budget = max(0, max_context_chars - len(question_section) - 32)
    core_section = _join_budgeted_sections(
        [resume_section, context_section, history_section],
        max_context_chars=core_budget,
    )
    user_content = f"{core_section}\n\n{question_section}" if core_section else question_section

    response = _call_with_trace(
        operation="chat_with_context",
        model=get_model_name(),
        max_tokens=_llm["max_tokens"],
        system=_prompts["chat_system"].format(school_name=SCHOOL_NAME) + disambiguation_note,
        messages=[{"role": "user", "content": user_content}],
        trace_metadata={
            "feature": "chat_with_context",
            "input_chars_pre_trim": input_chars_pre_trim,
            "kb_chunks_retrieved": kb_chunks_retrieved,
            "kb_chunks_sent": len(budgeted_chunks),
        },
    )
    return response.content[0].text


def analyse_kb_input(
    counsellor_input: str,
    retrieved_chunks: list[dict],
    profile_summary: str,
    employer_summary: str = "",
) -> dict:
    """Call Claude to produce a structured KB diff from counsellor input.

    Analyzes new input against existing KB and returns proposed updates to profiles
    and employers, new chunks, and already-covered information.

    Returns the raw parsed JSON dict (caller validates with Pydantic).
    Raises ValueError if Claude returns malformed JSON.
    """
    allowed_fields = ", ".join(kb_cfg["employers"]["allowed_update_fields"])
    system = _prompts["analyse_kb_input"].format(
        school_name=SCHOOL_NAME,
        allowed_employer_fields=allowed_fields
    )
    excerpt_chars = _llm_int("llm_analysis_excerpt_preview_chars", "analysis_excerpt_preview_chars", int(_llm["excerpt_preview_chars"]))
    generic_max_chunks = _llm_int("llm_max_chunks_per_prompt", "max_chunks_per_prompt", 8)
    max_chunks = min(_llm_int("llm_analysis_max_chunks", "analysis_max_chunks", 6), generic_max_chunks)
    threshold = _llm_int("llm_analysis_max_input_chars", "analysis_max_input_chars", 12000)
    chunk_tokens = _effective_session_multi_pass_setting("llm_session_multi_pass_chunk_tokens", "multi_pass_chunk_tokens")
    overlap_tokens = _effective_session_multi_pass_setting("llm_session_multi_pass_overlap_tokens", "multi_pass_overlap_tokens")
    max_chunk_chars = _llm_int("llm_max_chunk_chars_for_prompt", "max_chunk_chars_for_prompt", 4000)
    budgeted_chunks = _budget_chunks(retrieved_chunks, max_chunks=max_chunks, excerpt_chars=excerpt_chars, max_chunk_chars=max_chunk_chars)
    formatted_chunks = "\n\n".join(
        f"[{i+1}] (score={c['score']:.3f}) source={c['payload']['source_filename']}\n"
        f"{str(c['payload']['text'])[:excerpt_chars]}"
        for i, c in enumerate(budgeted_chunks)
    ) or "(No existing KB content retrieved)"

    schema_hint = (
        "JSON object with interpretation_bullets, profile_updates, employer_updates, "
        "new_chunks, and already_covered. already_covered items may use content/reason "
        "or excerpt/source_doc."
    )

    def build_user(input_text: str) -> str:
        return (
            f"INPUT TEXT:\n{input_text}\n\n"
            f"EXISTING KB EXCERPTS (top {max_chunks} by semantic similarity):\n{formatted_chunks}\n\n"
            f"CURRENT CAREER PROFILE FIELDS (key fields only):\n{profile_summary}\n\n"
            f"CURRENT EMPLOYER FACTS (key fields only):\n{employer_summary or '(No employers configured)'}"
        )

    results, failures = _collect_chunked_results(
        operation="analyse_kb_input",
        raw_input=counsellor_input,
        threshold_chars=threshold,
        chunk_tokens=chunk_tokens,
        overlap_tokens=overlap_tokens,
        system=system,
        schema_name="KBAnalysisResult",
        schema_hint=schema_hint,
        build_user=build_user,
        max_tokens=_llm["max_tokens_kb_analysis"],
        trace_metadata={
            "feature": "analyse_kb_input",
            "retrieved_chunks": len(retrieved_chunks),
            "kb_chunks_retrieved": len(retrieved_chunks),
            "kb_chunks_sent": len(budgeted_chunks),
            "input_chars_pre_trim": len(counsellor_input),
        },
        validator=KBAnalysisResult,
    )
    if not results:
        raise ValueError(f"Claude returned no valid KB analysis results: {failures[0] if failures else 'unknown error'}")

    merged = results[0] if len(results) == 1 else _merge_analysis_results(results)
    try:
        validated = _model_validate(KBAnalysisResult, merged)
    except Exception as exc:
        raise ValueError(f"Claude returned malformed JSON: {exc}") from exc
    if failures:
        logger.warning("analyse_kb_input: partial extraction due to %d failing chunk(s)", len(failures))
    return validated.model_dump()


def generate_track_draft(
    counsellor_input: str,
    track_name: str,
    slug: str,
    existing_tracks: list[dict],
    retrieved_chunks: list[dict],
    source_label: str,
    source_type: str,
    existing_draft: dict | None = None,
) -> dict:
    """Generate a structured draft career track from counsellor research input.

    Returns a raw JSON dict shaped for DraftTrackDetail (caller validates).
    Raises ValueError if Claude returns malformed JSON.
    """
    tracks_text = "\n".join(
        f"- {item.get('slug')}: {item.get('career_type') or item.get('label') or item.get('slug')}"
        for item in existing_tracks
    ) or "(No existing tracks configured)"
    excerpt_chars = _llm_int("llm_track_draft_excerpt_preview_chars", "track_draft_excerpt_preview_chars", int(_llm["excerpt_preview_chars"]))
    generic_max_chunks = _llm_int("llm_max_chunks_per_prompt", "max_chunks_per_prompt", 8)
    max_chunks = min(_llm_int("llm_track_draft_max_chunks", "track_draft_max_chunks", 6), generic_max_chunks)
    threshold = _llm_int("llm_track_draft_max_input_chars", "track_draft_max_input_chars", 12000)
    chunk_tokens = _effective_session_multi_pass_setting("llm_session_multi_pass_chunk_tokens", "multi_pass_chunk_tokens")
    overlap_tokens = _effective_session_multi_pass_setting("llm_session_multi_pass_overlap_tokens", "multi_pass_overlap_tokens")
    max_chunk_chars = _llm_int("llm_max_chunk_chars_for_prompt", "max_chunk_chars_for_prompt", 4000)
    budgeted_chunks = _budget_chunks(retrieved_chunks, max_chunks=max_chunks, excerpt_chars=excerpt_chars, max_chunk_chars=max_chunk_chars)
    excerpts_text = "\n\n".join(
        f"[{i+1}] score={c['score']:.3f} source={c['payload'].get('source_filename', 'unknown')}\n"
        f"{str(c['payload'].get('text', ''))[:excerpt_chars]}"
        for i, c in enumerate(budgeted_chunks)
    ) or "(No related knowledge retrieved)"
    existing_draft_text = json.dumps(existing_draft or {}, indent=2, ensure_ascii=False) or "{}"
    system = _prompts["track_draft"].format(school_name=SCHOOL_NAME)
    schema_hint = (
        "JSON object matching DraftTrackDetail with slug, track_name, status, match_description, "
        "match_keywords, ep_sponsorship, compass_score_typical, top_employers_smu, recruiting_timeline, "
        "international_realistic, entry_paths, salary_range_2024, typical_background, counselor_contact, notes, "
        "source_refs, structured, salary_levels, and visa_pathway_notes."
    )

    def build_user(input_text: str) -> str:
        return (
            f"TARGET TRACK NAME: {track_name}\n"
            f"TARGET SLUG: {slug}\n\n"
            f"EXISTING TRACKS:\n{tracks_text}\n\n"
            f"CURRENT DRAFT (if any):\n{existing_draft_text}\n\n"
            f"COUNSELLOR INPUT:\n{input_text}\n\n"
            f"RELATED KNOWLEDGE EXCERPTS:\n{excerpts_text}\n\n"
            f"SOURCE LABEL: {source_label}\n"
            f"SOURCE TYPE: {source_type}\n"
        )

    results, failures = _collect_chunked_results(
        operation="generate_track_draft",
        raw_input=counsellor_input,
        threshold_chars=threshold,
        chunk_tokens=chunk_tokens,
        overlap_tokens=overlap_tokens,
        system=system,
        schema_name="DraftTrackDetail",
        schema_hint=schema_hint,
        build_user=build_user,
        max_tokens=_llm["max_tokens_track_draft"],
        trace_metadata={
            "feature": "generate_track_draft",
            "retrieved_chunks": len(retrieved_chunks),
            "kb_chunks_retrieved": len(retrieved_chunks),
            "kb_chunks_sent": len(budgeted_chunks),
            "source_type": source_type,
            "input_chars_pre_trim": len(counsellor_input),
        },
        validator=DraftTrackDetail,
    )
    if not results:
        raise ValueError(f"Claude returned no valid draft output: {failures[0] if failures else 'unknown error'}")

    merged = results[0] if len(results) == 1 else _merge_track_drafts(results)
    merged["slug"] = slug
    merged["track_name"] = track_name
    if existing_draft:
        merged.setdefault("source_refs", existing_draft.get("source_refs", []))
        merged.setdefault("structured", existing_draft.get("structured", {}))
    try:
        validated = _model_validate(DraftTrackDetail, merged)
    except Exception as exc:
        raise ValueError(f"Claude returned malformed JSON: {exc}") from exc
    if failures:
        logger.warning("generate_track_draft: partial extraction due to %d failing chunk(s)", len(failures))
    return validated.model_dump()


def generate_brief(resume_text: str, chunks: list[dict]) -> str:
    """Generate a pre-meeting brief for a counselor based on resume + KB.

    Produces a structured brief with student's apparent goals, resume gaps,
    and 3-5 recommended talking points grounded in the knowledge base.

    Args:
        resume_text: student resume
        chunks: KB chunks retrieved by semantic search

    Returns:
        Brief text with actionable talking points.
    """
    generic_max_chunks = _llm_int("llm_max_chunks_per_prompt", "max_chunks_per_prompt", 8)
    max_chunks = min(_llm_int("llm_brief_max_chunks", "brief_max_chunks", 6), generic_max_chunks)
    excerpt_chars = _llm_int("llm_brief_excerpt_preview_chars", "brief_excerpt_preview_chars", int(_llm["excerpt_preview_chars"]))
    max_chunk_chars = _llm_int("llm_max_chunk_chars_for_prompt", "max_chunk_chars_for_prompt", 4000)
    max_context_chars = _llm_int("llm_brief_max_context_chars", "brief_max_context_chars", 10000)
    max_resume_chars = _llm_int("llm_brief_max_resume_chars", "brief_max_resume_chars", 4500)

    kb_chunks_retrieved = len(chunks)
    budgeted_chunks = _budget_chunks(chunks, max_chunks=max_chunks, excerpt_chars=excerpt_chars, max_chunk_chars=max_chunk_chars)
    kb_text = "\n\n---\n\n".join(
        f"[{c['payload']['source_filename']}]\n{c['payload']['text']}"
        for c in budgeted_chunks
    )
    resume_section = f"Resume:\n{_trim_to_budget(resume_text, max_resume_chars)}"
    kb_section = f"Knowledge base:\n{kb_text or 'No documents uploaded yet.'}"
    input_chars_pre_trim = len(f"Resume:\n{resume_text}") + len(f"Knowledge base:\n{kb_text or 'No documents uploaded yet.'}")
    user_content = _join_budgeted_sections([resume_section, kb_section], max_context_chars=max_context_chars)

    response = _call_with_trace(
        operation="generate_brief",
        model=get_model_name(),
        max_tokens=_llm["max_tokens"],
        system=_prompts["brief_system"].format(school_name=SCHOOL_NAME),
        messages=[{"role": "user", "content": user_content}],
        trace_metadata={
            "feature": "generate_brief",
            "input_chars_pre_trim": input_chars_pre_trim,
            "kb_chunks_retrieved": kb_chunks_retrieved,
            "kb_chunks_sent": len(budgeted_chunks),
        },
    )
    return response.content[0].text


def generate_alumni_extraction(
    text: str,
    existing_alumni: list[dict[str, Any]] | None,
    session_id: str | None = None,
    *,
    source_label: str = "counsellor_note",
    source_type: str = "note",
    alumni_slug: str | None = None,
    current_profile: dict[str, Any] | None = None,
    current_links: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Extract alumni proposals for preview flows now and card-native flows next.

    Returns the legacy preview fields at top level for `/extract-preview`, plus
    an `alumni` list whose items also include `is_update`, `matched_slug`, and
    `source_excerpt` for the upcoming session-card pipeline.
    """
    notes = str(text or "").strip()
    if not notes:
        raise ValueError("notes are required")

    normalized_candidates = _normalize_existing_alumni_candidates(existing_alumni)
    current_profile_payload = current_profile if isinstance(current_profile, dict) else {}
    current_link_payload = current_links if isinstance(current_links, list) else []

    system = _prompts["alumni_extraction"].format(
        school_name=SCHOOL_NAME,
        allowed_alumni_fields=", ".join(sorted(ALLOWED_ALUMNI_FIELDS)),
        allowed_alumni_link_fields=", ".join(sorted(ALLOWED_ALUMNI_LINK_FIELDS)),
    )
    user = (
        f"MEETING NOTES:\n{sanitize_for_prompt(notes)}\n\n"
        f"CURRENT ALUMNI PROFILE (if editing existing alumni):\n"
        f"{json.dumps(current_profile_payload, ensure_ascii=False, indent=2)}\n\n"
        f"CURRENT COMPANY LINKS:\n{json.dumps(current_link_payload, ensure_ascii=False, indent=2)}\n\n"
        f"EXISTING ALUMNI CANDIDATES FOR MATCHING:\n"
        f"{json.dumps(normalized_candidates, ensure_ascii=False, indent=2)}\n\n"
        f"SOURCE LABEL: {source_label}\n"
        f"SOURCE TYPE: {source_type}\n"
        f"ALUMNI SLUG (when editing a known alumnus): {alumni_slug or ''}\n"
    )
    schema_hint = (
        "JSON object with top-level summary_bullets, profile_proposals, "
        "company_link_proposals, fit_triad, source_label, source_type, and an "
        "alumni array. Each alumni item repeats the preview fields and includes "
        "is_update, matched_slug, and source_excerpt."
    )

    result = call_structured_json(
        operation="generate_alumni_extraction",
        model=get_model_name(),
        system=system,
        user=user,
        schema_name="AlumniExtractionPreview",
        schema_hint=schema_hint,
        max_tokens=3000,
        timeout_seconds=settings.llm_timeout_seconds,
        trace_metadata={
            "feature": "generate_alumni_extraction",
            "session_id": session_id,
            "source_type": source_type,
            "source_label": source_label,
            "alumni_slug": alumni_slug,
            "existing_alumni_count": len(normalized_candidates),
            "input_chars_pre_trim": len(text or ""),
        },
        validator=None,
    )

    payload = dict(result) if isinstance(result, dict) else {}
    preview_payload = _validated_alumni_preview_payload(
        payload,
        source_label=source_label,
        source_type=source_type,
    )

    alumni_items_raw = payload.get("alumni")
    alumni_items: list[dict[str, Any]] = []
    if isinstance(alumni_items_raw, list):
        for item in alumni_items_raw:
            if not isinstance(item, dict):
                continue
            item_preview = _validated_alumni_preview_payload(
                item,
                source_label=source_label,
                source_type=source_type,
            )
            alumni_items.append(
                {
                    **item_preview,
                    "is_update": bool(item.get("is_update")),
                    "matched_slug": str(item.get("matched_slug") or "").strip() or None,
                    "source_excerpt": str(item.get("source_excerpt") or "").strip(),
                }
            )

    if not alumni_items:
        alumni_items.append(
            {
                **preview_payload,
                "is_update": bool(payload.get("is_update")),
                "matched_slug": str(payload.get("matched_slug") or "").strip() or None,
                "source_excerpt": str(payload.get("source_excerpt") or "").strip(),
            }
        )

    if not preview_payload.get("summary_bullets") and alumni_items:
        primary = alumni_items[0]
        preview_payload = _validated_alumni_preview_payload(
            primary,
            source_label=source_label,
            source_type=source_type,
        )

    primary_item = alumni_items[0]
    return {
        **preview_payload,
        "source_label": preview_payload.get("source_label") or source_label,
        "source_type": preview_payload.get("source_type") or source_type,
        "is_update": bool(payload.get("is_update", primary_item.get("is_update"))),
        "matched_slug": str(payload.get("matched_slug") or primary_item.get("matched_slug") or "").strip() or None,
        "source_excerpt": str(payload.get("source_excerpt") or primary_item.get("source_excerpt") or "").strip(),
        "alumni": alumni_items,
    }


def _merge_intents(results: list[dict]) -> dict:
    """Merge and deduplicate intent extraction results from multiple chunks."""
    merged_cards = []
    merged_already_covered = []

    seen_card_keys = set()  # (domain, slug, summary_key)

    for i, res in enumerate(results):
        for card in res.get("cards", []):
            # Create a semi-stable key for deduplication
            domain = card.get("domain", "unknown")
            slug = card.get("diff", {}).get("slug", "unknown")
            # use normalized summary prefix for deduplication (from config)
            summary_limit = _llm["intent_dedup_summary_chars"]
            summary = (card.get("summary") or "")[:summary_limit].lower().strip()
            key = (domain, slug, summary)

            if key not in seen_card_keys:
                seen_card_keys.add(key)
                # Ensure card_id is unique across chunks
                if i > 0:
                    card["card_id"] = f"card-{uuid.uuid4().hex[:8]}"
                merged_cards.append(card)
        
        for ac in res.get("already_covered", []):
            merged_already_covered.append(ac)

    return {
        "cards": merged_cards,
        "already_covered": merged_already_covered,
    }


def _merge_analysis_results(results: list[dict]) -> dict:
    """Merge KB analysis results from multiple chunks, deduplicating bullets, chunks, and already-covered items."""
    merged = {
        "interpretation_bullets": [],
        "profile_updates": {},
        "employer_updates": {},
        "new_chunks": [],
        "already_covered": [],
    }
    seen_bullets: set[str] = set()
    seen_chunks: set[tuple[str, str, str, str]] = set()
    seen_covered: set[tuple[str, str]] = set()

    for res in results:
        for bullet in res.get("interpretation_bullets", []) or []:
            bullet_text = str(bullet).strip()
            key = bullet_text.lower()
            if bullet_text and key not in seen_bullets:
                seen_bullets.add(key)
                merged["interpretation_bullets"].append(bullet_text)

        for slug, fields in (res.get("profile_updates", {}) or {}).items():
            merged["profile_updates"].setdefault(slug, {})
            merged["profile_updates"][slug].update(fields or {})

        for slug, fields in (res.get("employer_updates", {}) or {}).items():
            merged["employer_updates"].setdefault(slug, {})
            merged["employer_updates"][slug].update(fields or {})

        for chunk in res.get("new_chunks", []) or []:
            text = str(chunk.get("text", "")).strip()
            source_type = str(chunk.get("source_type", "")).strip()
            source_label = str(chunk.get("source_label", "")).strip()
            career_type = str(chunk.get("career_type", "") or "").strip()
            key = (text.lower(), source_type.lower(), source_label.lower(), career_type.lower())
            if text and key not in seen_chunks:
                seen_chunks.add(key)
                merged["new_chunks"].append(chunk)

        for ac in res.get("already_covered", []) or []:
            content = str(ac.get("content") or ac.get("excerpt") or "").strip()
            reason = str(ac.get("reason") or ac.get("source_doc") or "").strip()
            key = (content.lower(), reason.lower())
            if content and key not in seen_covered:
                seen_covered.add(key)
                merged["already_covered"].append(ac)

    return merged


def _merge_track_drafts(results: list[dict]) -> dict:
    """Merge track draft dicts from multiple extraction passes, combining list fields and updating scalar fields from later chunks."""
    merged: dict[str, Any] = {}
    list_fields = {
        "match_keywords",
        "top_employers_smu",
        "entry_paths",
        "source_refs",
        "salary_levels",
    }
    for res in results:
        for key, value in res.items():
            if value in (None, "", [], {}):
                continue
            if key in list_fields:
                current = merged.get(key) or []
                if not isinstance(current, list):
                    current = [current]
                incoming = value if isinstance(value, list) else [value]
                merged[key] = current + [item for item in incoming if item not in current]
            elif key == "structured" and isinstance(value, dict):
                current = merged.get(key) or {}
                if not isinstance(current, dict):
                    current = {}
                current.update(value)
                merged[key] = current
            else:
                merged[key] = value
    return merged


def _collect_chunked_results(
    *,
    operation: str,
    raw_input: str,
    threshold_chars: int,
    chunk_tokens: int,
    overlap_tokens: int,
    system: str,
    schema_name: str,
    schema_hint: str,
    build_user: Callable[[str], str],
    max_tokens: int,
    timeout_seconds: float | None = None,
    trace_metadata: dict[str, object] | None = None,
    validator: type[BaseModel] | None = None,
    max_retries: int | None = 2,
) -> tuple[list[dict], list[str]]:
    """Run a structured-JSON extraction over raw_input, splitting into overlapping chunks when the input exceeds threshold_chars."""
    if not _staged_extraction_enabled() or len(raw_input) <= threshold_chars:
        result = call_structured_json(
            operation=operation,
            model=get_model_name(),
            system=system,
            user=build_user(raw_input),
            schema_name=schema_name,
            schema_hint=schema_hint,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            trace_metadata={
                **(trace_metadata or {}),
                "input_chars_pre_trim": len(raw_input),
            },
            validator=validator,
            max_retries=max_retries,
        )
        if isinstance(result, BaseModel):
            result = result.model_dump()
        return [result], []

    chunks = chunk_text(raw_input, max_tokens=chunk_tokens, overlap=overlap_tokens)

    results: list[dict] = []
    failures: list[str] = []
    total_chunks = len(chunks)
    for index, chunk in enumerate(chunks, start=1):
        try:
            result = call_structured_json(
                operation=operation,
                model=get_model_name(),
                system=system,
                user=build_user(chunk),
                schema_name=schema_name,
                schema_hint=schema_hint,
                max_tokens=max_tokens,
                timeout_seconds=timeout_seconds,
                trace_metadata={
                    **(trace_metadata or {}),
                    "phase": "multi_pass_chunk",
                    "chunk_index": index,
                    "chunk_count": total_chunks,
                    "multi_pass_threshold_chars": threshold_chars,
                    "multi_pass_chunk_tokens": chunk_tokens,
                    "multi_pass_overlap_tokens": overlap_tokens,
                    "input_chars_pre_trim": len(raw_input),
                },
                validator=validator,
                max_retries=max_retries,
            )
            if isinstance(result, BaseModel):
                result = result.model_dump()
            results.append(result)
        except Exception as exc:
            failures.append(f"chunk {index}/{total_chunks}: {exc}")
    return results, failures


def generate_session_intents(
    raw_input: str,
    existing_tracks: list[dict] | None = None,
    existing_employers: list[dict] | None = None,
    session_id: str | None = None,
    trace_metadata: dict[str, object] | None = None,
) -> dict:
    """Extract distinct update intents from counsellor raw research notes.

    Supports multi-pass extraction for long documents (threshold from config).
    Chunks are extracted independently and merged, deduplicating on (domain, slug, summary).
    """
    threshold = _effective_session_multi_pass_setting(
        "llm_session_multi_pass_threshold_chars",
        "multi_pass_threshold_chars",
    )
    chunk_tokens = _effective_session_multi_pass_setting(
        "llm_session_multi_pass_chunk_tokens",
        "multi_pass_chunk_tokens",
    )
    overlap_tokens = _effective_session_multi_pass_setting(
        "llm_session_multi_pass_overlap_tokens",
        "multi_pass_overlap_tokens",
    )
    is_chunk_call = (trace_metadata or {}).get("phase") == "multi_pass_chunk"
    langfuse_client = _get_langfuse_client()
    root_span_cm = nullcontext()
    if langfuse_client is not None and not is_chunk_call:
        root_span_cm = _start_langfuse_observation(
            langfuse_client,
            as_type="span",
            name="generate_session_intents",
            input={
                "raw_input_chars": len(raw_input),
                "input_chars_pre_trim": len(raw_input),
                "session_id": session_id,
                "multi_pass": len(raw_input) > threshold,
                "threshold_chars": threshold,
                "chunk_tokens": chunk_tokens,
                "overlap_tokens": overlap_tokens,
            },
        )
    propagate_cm = nullcontext()
    if session_id and langfuse_client is not None and propagate_attributes is not None:
        try:
            propagate_cm = propagate_attributes(
                session_id=session_id,
                metadata={
                    "environment": str(getattr(settings, "langfuse_tracing_environment", "development")),
                    "feature": "generate_session_intents",
                },
            )
        except Exception:
            logger.warning("Langfuse propagation failed; continuing without tracing", exc_info=True)
            propagate_cm = nullcontext()

    with root_span_cm as root_span, propagate_cm:
        tracks_text = ""
        if existing_tracks:
            tracks_text = "\n".join(
                f"- {t.get('career_type', t.get('slug', 'unknown'))}: {t.get('match_description', '')}"
                for t in existing_tracks
            )

        employers_text = ""
        if existing_employers:
            employers_text = "\n".join(
                f"- {e.get('slug', 'unknown')}: tracks={e.get('tracks', [])}, "
                f"ep={e.get('ep_requirement', 'N/A')}"
                for e in existing_employers
            )

        schema_hint = (
            "JSON object with cards array and already_covered array. "
            "cards entries must include card_id, domain, summary, diff, and raw_input_ref. "
            "already_covered entries use content/reason."
        )

        def build_user(input_text: str) -> str:
            return (
                f"Counsellor raw input:\n{input_text}\n\n"
                f"Existing career tracks (for reference — create cards for NEW sectors too):\n{tracks_text or '(none)'}\n\n"
                f"Existing employers (for reference — create cards for NEW companies too):\n{employers_text or '(none)'}\n\n"
                "Extract intents as JSON. Remember: if the memo is about companies or sectors NOT listed above, create cards for them."
            )

        try:
            results, failures = _collect_chunked_results(
                operation="generate_session_intents",
                raw_input=raw_input,
                threshold_chars=threshold,
                chunk_tokens=chunk_tokens,
                overlap_tokens=overlap_tokens,
                system=_prompts["session_intents"],
                schema_name="SessionAnalysisResult",
                schema_hint=schema_hint,
                build_user=build_user,
                max_tokens=_llm["max_tokens_session_extraction"],
                timeout_seconds=settings.llm_session_timeout_seconds,
                max_retries=0,
                trace_metadata={
                    "feature": "generate_session_intents",
                    **(trace_metadata or {}),
                    "session_id": session_id,
                    "phase": str((trace_metadata or {}).get("phase") or "session_analysis"),
                    "multi_pass_threshold_chars": threshold,
                    "multi_pass_chunk_tokens": chunk_tokens,
                    "multi_pass_overlap_tokens": overlap_tokens,
                    "input_chars_pre_trim": len(raw_input),
                },
            )

            if not results:
                if root_span is not None:
                    root_span.update(
                        output={
                            "cards": 0,
                            "already_covered": 0,
                            "multi_pass": len(raw_input) > threshold,
                            "partial_result": False,
                            "error": failures[0] if failures else "no valid output",
                        }
                    )
                return {"cards": [], "already_covered": []}

            result = results[0] if len(results) == 1 else _merge_intents(results)
            result.setdefault("cards", [])
            result.setdefault("already_covered", [])
            if root_span is not None:
                root_span.update(
                    output={
                        "cards": len(result.get("cards", [])),
                        "already_covered": len(result.get("already_covered", [])),
                        "multi_pass": len(raw_input) > threshold,
                        "partial_result": bool(failures),
                    }
                )

            if failures:
                logger.warning("generate_session_intents: partial extraction due to %d failing chunk(s)", len(failures))
            return result
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("generate_session_intents: LLM call failed: %s", exc)
            if root_span is not None:
                root_span.update(
                    output={
                        "cards": 0,
                        "already_covered": 0,
                        "multi_pass": len(raw_input) > threshold,
                        "error": str(exc),
                    }
                )
            return {"cards": [], "already_covered": []}


async def extract_facts_from_prose(notes: str, employer_name: str = "employer") -> list[dict]:
    """Extract structured facts (timeline, alumni, interview, etc.) from prose notes.

    Uses Claude to parse employer notes and extract timeline_phase, alumni,
    interview_stage, compensation, and skill_requirement facts.

    Args:
        notes: Raw counselor notes about an employer
        employer_name: Employer name for context

    Returns:
        List of Fact dicts with slug, type, data, confidence, source, timestamp
    """
    if not notes or not notes.strip():
        return []

    prompt = f"""You are extracting structured facts from employer notes.

Return a raw JSON array only.
Do not use markdown fences, prose, bullets, comments, or code blocks.
If there are no facts, return [] exactly.

Notes:
{notes}

Employer: {employer_name}

Extract only facts that are explicitly stated or clearly supported by the notes.
Prefer fewer, higher-confidence facts over speculation.

Allowed fact types:
1. timeline_phase - application windows, deadlines, event timing, recruiting phases
2. alumni - student or alumni names, schools, years, roles, company transitions
3. interview_stage - process steps, format, timing, duration
4. compensation - base pay, bonus, equity, benefits, total compensation
5. skill_requirement - background, skills, tools, domain knowledge, prerequisites

For every fact object:
- Use exactly these top-level keys: slug, type, timestamp, source, confidence, data
- Put all descriptive fields inside data
- Use a lowercase slug like "stripe-aditya-mehta"
- Set source to "inferred"
- Set confidence to an integer from 50 to 100
- Set timestamp to an ISO-8601 UTC string ending in Z

Example:
[
  {{
    "slug": "stripe-internship-summer",
    "type": "timeline_phase",
    "timestamp": "2026-04-20T00:00:00Z",
    "source": "inferred",
    "confidence": 85,
    "data": {{
      "phase_name": "Summer internship application",
      "value": "June 1 - August 31",
      "role_type": "summer_internship",
      "duration_days": 92
    }}
  }}
]"""

    try:
        msg = _call_with_trace(
            operation="extract_facts_from_prose",
            model=get_model_name(),
            max_tokens=2000,
            system="You are a fact extraction service for employer intelligence. Return only a raw JSON array. Do not use markdown fences or any text outside the JSON.",
            messages=[{"role": "user", "content": prompt}],
            timeout_seconds=settings.llm_timeout_seconds,
            trace_metadata={
                "feature": "extract_facts_from_prose",
                "employer_name": employer_name,
                "input_chars_pre_trim": len(notes),
            },
        )

        response_text = _response_text(msg)

        # Try to parse as JSON, repair if needed.
        try:
            facts_raw = _parse_json_payload(response_text)
        except json.JSONDecodeError:
            # Attempt repair
            facts_raw = _repair_json_output(
                raw_text=response_text,
                schema_name="Fact",
                schema_hint="JSON array of fact objects with slug, type, timestamp, source, confidence, data fields",
                operation="extract_facts_from_prose",
                model=get_model_name(),
                max_tokens=2000,
            )
            if not isinstance(facts_raw, list):
                facts_raw = []

        # Validate each fact against Fact model
        validated_facts = []
        for f in facts_raw:
            try:
                fact_obj = Fact(
                    slug=f.get("slug", ""),
                    type=f.get("type", ""),
                    timestamp=f.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    source="inferred",
                    confidence=f.get("confidence", 75),
                    data=f,
                    deleted=False,
                )
                validated_facts.append(fact_obj.model_dump())
            except ValidationError as e:
                logger.warning("extract_facts_from_prose: invalid fact, skipping: %s", e)
                continue

        logger.info("extract_facts_from_prose: extracted %d facts from %s", len(validated_facts), employer_name)
        return validated_facts

    except Exception as exc:
        logger.error("extract_facts_from_prose: failed for %s: %s", employer_name, exc)
        raise HTTPException(status_code=500, detail=f"Fact extraction failed: {str(exc)}")
