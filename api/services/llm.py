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
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import anthropic
from fastapi import HTTPException

from config import settings
from services.ingestion import chunk_text

logger = logging.getLogger(__name__)
from cfg import model_cfg, kb_cfg, prompts_cfg

_clients: dict[int, anthropic.Anthropic] = {}
_langfuse_client = None
_langfuse_client_config: tuple | None = None
_langfuse_class = None
propagate_attributes = None
_langfuse_flush_executor: ThreadPoolExecutor | None = None
_TRACE_PREVIEW_CHARS = 500

_llm = model_cfg["llm"]
_prompts = prompts_cfg.get("prompts", {})
SCHOOL_NAME = model_cfg["school"]["name"]


def _effective_session_multi_pass_setting(setting_name: str, model_key: str) -> int:
    value = getattr(settings, setting_name, None)
    if value is not None:
        return int(value)
    return int(_llm[model_key])


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
    message_summaries = []
    for message in messages:
        content = str(message.get("content", ""))
        message_summaries.append({
            "role": message.get("role", "user"),
            "content_preview": _truncate_preview(content),
            "content_chars": len(content),
        })
    return {
        "system_preview": _truncate_preview(system),
        "system_chars": len(system),
        "messages": message_summaries,
        "message_count": len(messages),
        "metadata": metadata,
        "max_tokens": max_tokens,
        "timeout_seconds": timeout_seconds,
    }


def _langfuse_trace_metadata(metadata: dict[str, object], trace_id: str) -> dict[str, str]:
    out: dict[str, str] = {"trace_id": trace_id}
    for key, value in metadata.items():
        if value is None:
            continue
        out[key] = str(value)
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
    start = perf_counter()
    input_chars = len(system) + sum(len(str(message.get("content", ""))) for message in messages)
    trace_id = uuid.uuid4().hex
    input_preview = _truncate_preview(messages[-1].get("content", "")) if messages else ""
    metadata = trace_metadata or {}
    langfuse_client = _get_langfuse_client()
    observation_cm = nullcontext()
    if langfuse_client is not None:
        observation_cm = _start_langfuse_observation(
            langfuse_client,
            as_type="generation",
            name=operation,
            model=model,
            input=_langfuse_input_payload(system, messages, {**metadata, "trace_id": trace_id}, max_tokens, timeout_seconds),
        )
    _append_llm_trace({
        "trace_id": trace_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "operation": operation,
        "status": "started",
        "model": model,
        **metadata,
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
                    "version": getattr(settings, "langfuse_tracing_environment", "development"),
                }
                if metadata.get("session_id"):
                    propagate_kwargs["session_id"] = str(metadata["session_id"])
                trace_metadata = _langfuse_trace_metadata(metadata, trace_id)
                if trace_metadata:
                    propagate_kwargs["metadata"] = trace_metadata
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
                    **metadata,
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
                                **metadata,
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
                **metadata,
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
                            **metadata,
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
    kb_text = "\n\n---\n\n".join(
        f"[{c['payload']['source_filename']}]\n{c['payload']['text']}"
        for c in chunks
    )
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in history[-_llm["history_window"]:]
    ) if history else "None"

    # Injection order: career profile → employer facts → KB chunks
    # Employer facts always appear before KB chunks so authoritative YAML data
    # supersedes any stale chunk content about the same employers.
    context_sections = []
    if career_context:
        context_sections.append(career_context)
    if employer_context:
        if career_context:
            context_sections.insert(1, employer_context)
        else:
            context_sections.insert(0, employer_context)
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

    user_content = (
        f"Student resume:\n{resume_text or 'Not provided'}\n\n"
        f"{combined_context}\n\n"
        f"Conversation so far:\n{history_text}\n\n"
        f"Student question: {message}"
    )

    response = _call_with_trace(
        operation="chat_with_context",
        model=_llm["model"],
        max_tokens=_llm["max_tokens"],
        system=_prompts["chat_system"].format(school_name=SCHOOL_NAME) + disambiguation_note,
        messages=[{"role": "user", "content": user_content}],
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
    import json

    # Build allowed fields list from config
    allowed_fields = ", ".join(kb_cfg["employers"]["allowed_update_fields"])

    # Load system prompt from YAML and format with dynamic values
    system = _prompts["analyse_kb_input"].format(
        school_name=SCHOOL_NAME,
        allowed_employer_fields=allowed_fields
    )

    formatted_chunks = "\n\n".join(
        f"[{i+1}] (score={c['score']:.3f}) source={c['payload']['source_filename']}\n"
        f"{c['payload']['text'][:_llm['excerpt_preview_chars']]}"
        for i, c in enumerate(retrieved_chunks)
    ) or "(No existing KB content retrieved)"

    user = (
        f"INPUT TEXT:\n{counsellor_input}\n\n"
        f"EXISTING KB EXCERPTS (top 10 by semantic similarity):\n{formatted_chunks}\n\n"
        f"CURRENT CAREER PROFILE FIELDS (key fields only):\n{profile_summary}\n\n"
        f"CURRENT EMPLOYER FACTS (key fields only):\n{employer_summary or '(No employers configured)'}"
    )

    response = _call_with_trace(
        operation="analyse_kb_input",
        model=_llm["model"],
        max_tokens=_llm["max_tokens_kb_analysis"],
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    if not response.content or response.content[0].type != "text":
        raise ValueError("Claude returned an empty or non-text response")
    raw = response.content[0].text.strip()

    # Strip markdown code fences if Claude wraps the JSON
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if "```" in raw:
            raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except Exception as exc:
        raise ValueError(f"Claude returned malformed JSON: {exc}") from exc


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
    import json

    tracks_text = "\n".join(
        f"- {item.get('slug')}: {item.get('career_type') or item.get('label') or item.get('slug')}"
        for item in existing_tracks
    ) or "(No existing tracks configured)"

    excerpts_text = "\n\n".join(
        f"[{i+1}] score={c['score']:.3f} source={c['payload'].get('source_filename', 'unknown')}\n"
        f"{str(c['payload'].get('text', ''))[:_llm['excerpt_preview_chars']]}"
        for i, c in enumerate(retrieved_chunks)
    ) or "(No related knowledge retrieved)"
    existing_draft_text = json.dumps(existing_draft or {}, indent=2, ensure_ascii=False) or "{}"

    # Load system prompt from YAML and format with school name
    system = _prompts["track_draft"].format(school_name=SCHOOL_NAME)

    user = (
        f"TARGET TRACK NAME: {track_name}\n"
        f"TARGET SLUG: {slug}\n\n"
        f"EXISTING TRACKS:\n{tracks_text}\n\n"
        f"CURRENT DRAFT (if any):\n{existing_draft_text}\n\n"
        f"COUNSELLOR INPUT:\n{counsellor_input}\n\n"
        f"RELATED KNOWLEDGE EXCERPTS:\n{excerpts_text}\n\n"
        f"SOURCE LABEL: {source_label}\n"
        f"SOURCE TYPE: {source_type}\n"
    )

    response = _call_with_trace(
        operation="generate_track_draft",
        model=_llm["model"],
        max_tokens=_llm["max_tokens_track_draft"],
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    if not response.content or response.content[0].type != "text":
        raise ValueError("Claude returned an empty or non-text response")
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if "```" in raw:
            raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception as exc:
        raise ValueError(f"Claude returned malformed JSON: {exc}") from exc


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
    kb_text = "\n\n---\n\n".join(
        f"[{c['payload']['source_filename']}]\n{c['payload']['text']}"
        for c in chunks
    )

    response = _call_with_trace(
        operation="generate_brief",
        model=_llm["model"],
        max_tokens=_llm["max_tokens"],
        system=_prompts["brief_system"].format(school_name=SCHOOL_NAME),
        messages=[{"role": "user", "content":
            f"Resume:\n{resume_text}\n\nKnowledge base:\n{kb_text}"}],
    )
    return response.content[0].text


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
    # 1. Check for multi-pass need
    # Large documents are split into chunks for extraction density/reliability.
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
                version=getattr(settings, "langfuse_tracing_environment", "development"),
            )
        except Exception:
            logger.warning("Langfuse propagation failed; continuing without tracing", exc_info=True)
            propagate_cm = nullcontext()

    with root_span_cm as root_span, propagate_cm:
        if len(raw_input) > threshold:
            logger.info("generate_session_intents: Large document detected (%d chars). Using multi-pass.", len(raw_input))
            chunks = chunk_text(
                raw_input,
                max_tokens=chunk_tokens,
                overlap=overlap_tokens
            )
            results = []
            total_chunks = len(chunks)
            for index, chunk in enumerate(chunks, start=1):
                res = generate_session_intents(
                    chunk,
                    existing_tracks,
                    existing_employers,
                    session_id=session_id,
                    trace_metadata={
                        **(trace_metadata or {}),
                        "phase": "multi_pass_chunk",
                        "chunk_index": index,
                        "chunk_count": total_chunks,
                        "multi_pass_threshold_chars": threshold,
                        "multi_pass_chunk_tokens": chunk_tokens,
                        "multi_pass_overlap_tokens": overlap_tokens,
                    },
                )
                results.append(res)
            merged = _merge_intents(results)
            if root_span is not None:
                root_span.update(
                    output={
                        "cards": len(merged.get("cards", [])),
                        "already_covered": len(merged.get("already_covered", [])),
                        "multi_pass": True,
                        "chunk_count": total_chunks,
                    }
                )
            return merged

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

        context = (
            f"Counsellor raw input:\n{raw_input}\n\n"
            f"Existing career tracks (for reference — create cards for NEW sectors too):\n{tracks_text or '(none)'}\n\n"
            f"Existing employers (for reference — create cards for NEW companies too):\n{employers_text or '(none)'}\n\n"
            "Extract intents as JSON. Remember: if the memo is about companies or sectors NOT listed above, create cards for them."
        )

        def parse_response(text: str) -> dict:
            json_text = text
            if "```json" in text:
                json_text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                # Fallback for generic code blocks
                parts = text.split("```")
                if len(parts) >= 3:
                    json_text = parts[1].strip()
                    if json_text.startswith("json"):
                        json_text = json_text[4:].strip()
            else:
                # Try to find the first { and last }
                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end != -1:
                    json_text = text[start:end+1]

            try:
                parsed = json.loads(json_text)
                if "cards" not in parsed:
                    parsed["cards"] = []
                if "already_covered" not in parsed:
                    parsed["already_covered"] = []
                return parsed
            except json.JSONDecodeError:
                return {"cards": [], "already_covered": []}

        try:
            model = _llm["model"]
            base_phase = (trace_metadata or {}).get("phase")
            phase = str(base_phase) if base_phase else "session_analysis"

            response = _call_with_trace(
                operation="generate_session_intents",
                model=model,
                max_tokens=_llm["max_tokens_session_extraction"],
                temperature=0,
                system=_prompts["session_intents"],
                messages=[{"role": "user", "content": context}],
                timeout_seconds=settings.llm_session_timeout_seconds,
                max_retries=0,
                trace_metadata={
                    **(trace_metadata or {}),
                    "session_id": session_id,
                    "phase": phase,
                    "multi_pass_threshold_chars": threshold,
                    "multi_pass_chunk_tokens": chunk_tokens,
                    "multi_pass_overlap_tokens": overlap_tokens,
                },
            )

            text = response.content[0].text.strip()
            result = parse_response(text)

            if not result["cards"] and not result["already_covered"]:
                # Retry once on total failure
                retry_response = _call_with_trace(
                    operation="generate_session_intents_retry",
                    model=model,
                    max_tokens=_llm["max_tokens_session_extraction"],
                    temperature=0,
                    system=_prompts["session_intents"],
                    messages=[{"role": "user", "content": context}],
                    timeout_seconds=settings.llm_session_timeout_seconds,
                    max_retries=0,
                    trace_metadata={
                        **(trace_metadata or {}),
                        "session_id": session_id,
                        "phase": f"{phase}_retry",
                    },
                )
                result = parse_response(retry_response.content[0].text.strip())

            if root_span is not None:
                root_span.update(
                    output={
                        "cards": len(result.get("cards", [])),
                        "already_covered": len(result.get("already_covered", [])),
                        "multi_pass": False,
                    }
                )

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
