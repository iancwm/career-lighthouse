"""Structured JSON parsing and repair helpers for LLM responses."""

from __future__ import annotations

import difflib
import json
import logging
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

_logger = logging.getLogger(__name__)


def extract_json_block(text: str) -> str:
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

    obj_start = text.find("{")
    obj_end = text.rfind("}")
    arr_start = text.find("[")
    arr_end = text.rfind("]")

    has_obj = obj_start != -1 and obj_end != -1 and obj_end > obj_start
    has_arr = arr_start != -1 and arr_end != -1 and arr_end > arr_start

    if has_obj and has_arr:
        if arr_start < obj_start:
            return text[arr_start : arr_end + 1].strip()
        return text[obj_start : obj_end + 1].strip()
    if has_obj:
        return text[obj_start : obj_end + 1].strip()
    if has_arr:
        return text[arr_start : arr_end + 1].strip()
    return text


def parse_json_payload(text: str) -> Any:
    return json.loads(extract_json_block(text))


def json_dumps_safe(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    except Exception:
        return str(value)


def repair_json_output(
    *,
    raw_text: str,
    schema_name: str,
    schema_hint: str,
    operation: str,
    model: str,
    json_repair_enabled: Callable[[], bool],
    call_with_trace: Callable[..., object],
    response_text: Callable[[object], str],
    parse_json: Callable[[str], Any],
    safe_dumps: Callable[[Any], str],
    max_tokens: int = 512,
    timeout_seconds: float | None = None,
    trace_metadata: dict[str, object] | None = None,
    max_retries: int | None = 2,
) -> dict | list:
    if not json_repair_enabled():
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
            repair_system += (
                f"\nThe previous JSON parse attempt failed with: {parse_error_text}"
            )

        repair_user = f"Malformed JSON:\n{repair_source}"
        response = call_with_trace(
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
        repaired_text = response_text(response)
        try:
            repaired = parse_json(repaired_text)
        except Exception as exc:
            last_error = exc
            parse_error_text = str(exc)
            repair_source = repaired_text
            continue

        if isinstance(repaired, (dict, list)):
            diff = list(difflib.unified_diff(
                repair_source.splitlines(),
                repaired_text.splitlines(),
                fromfile="pre-repair",
                tofile="post-repair",
                lineterm="",
            ))
            if diff:
                _logger.warning(
                    "llm_json repair applied for %s (attempt %d):\n%s",
                    schema_name,
                    repair_attempt,
                    "\n".join(diff),
                )
            return repaired

        last_error = ValueError(
            f"{schema_name} repair did not return a JSON object or array"
        )
        parse_error_text = str(last_error)
        repair_source = safe_dumps(repaired)

    raise ValueError(
        f"{schema_name} repair did not return a valid JSON object"
    ) from last_error


def validate_or_repair(
    *,
    parsed: dict,
    raw_text: str,
    schema_name: str,
    schema_hint: str,
    operation: str,
    model: str,
    validator: type[BaseModel] | None,
    model_validate: Callable[[type[BaseModel], Any], BaseModel],
    repair_json_output_fn: Callable[..., dict | list],
    logger: logging.Logger,
    max_tokens: int = 512,
    timeout_seconds: float | None = None,
    trace_metadata: dict[str, object] | None = None,
    max_retries: int | None = 2,
) -> Any:
    if validator is None:
        return parsed

    try:
        return model_validate(validator, parsed)
    except (ValidationError, ValueError, TypeError) as exc:
        logger.debug("%s validation failed, attempting repair: %s", schema_name, exc)
        parsed_text = json_dumps_safe(parsed)
        repaired = repair_json_output_fn(
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
        return model_validate(validator, repaired)


def call_structured_json(
    *,
    operation: str,
    model: str,
    system: str,
    user: str,
    schema_name: str,
    schema_hint: str,
    max_tokens: int,
    call_with_trace: Callable[..., object],
    response_text: Callable[[object], str],
    parse_json: Callable[[str], Any],
    safe_dumps: Callable[[Any], str],
    repair_json_output_fn: Callable[..., dict | list],
    validate_or_repair_fn: Callable[..., Any],
    timeout_seconds: float | None = None,
    trace_metadata: dict[str, object] | None = None,
    validator: type[BaseModel] | None = None,
    max_repair_tokens: int = 8192,
    max_retries: int | None = 2,
) -> Any:
    response = call_with_trace(
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
    raw_text = response_text(response)
    try:
        parsed = parse_json(raw_text)
    except Exception:
        parsed = repair_json_output_fn(
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
        parsed = repair_json_output_fn(
            raw_text=safe_dumps(parsed),
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
    return validate_or_repair_fn(
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
