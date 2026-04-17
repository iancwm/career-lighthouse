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
import re
import uuid
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
_TRACE_PREVIEW_CHARS = 500

_llm = model_cfg["llm"]
# Merge model.yaml prompts (chat_system, disambiguation, brief_system)
# with prompts.yaml prompts (analyse_kb_input, track_draft, session_intents)
_prompts = {**model_cfg.get("prompts", {}), **prompts_cfg.get("prompts", {})}
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


def _append_llm_trace(entry: dict) -> None:
    path = Path(settings.llm_trace_log_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
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
            "error": str(exc.detail),
        })
        raise

    output_text = ""
    if getattr(response, "content", None):
        first = response.content[0]
        output_text = getattr(first, "text", "") or ""

    elapsed_ms = round((perf_counter() - start) * 1000, 1)
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
    return response


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
        system=_prompts["brief_system"],
        messages=[{"role": "user", "content":
            f"Resume:\n{resume_text}\n\nKnowledge base:\n{kb_text}"}],
    )
    return response.content[0].text


def _merge_intents(results: list[dict]) -> dict:
    """Merge and deduplicate intent extraction results from multiple chunks."""
    merged_cards = []
    merged_already_covered = []
    thoughts = []

    seen_card_keys = set()  # (domain, slug, summary_key)

    for i, res in enumerate(results):
        if res.get("thought"):
            thoughts.append(f"--- Chunk {i+1} ---\n{res['thought']}")
        
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
        "thought": "\n\n".join(thoughts)
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
    Requires the LLM to provide a <thought> block before the JSON for observability.
    """
    # 1. Check for multi-pass need
    # Large documents are split into chunks for extraction density/reliability.
    threshold = _effective_session_multi_pass_setting(
        "llm_session_multi_pass_threshold_chars",
        "multi_pass_threshold_chars",
    )
    if len(raw_input) > threshold:
        logger.info("generate_session_intents: Large document detected (%d chars). Using multi-pass.", len(raw_input))
        chunk_tokens = _effective_session_multi_pass_setting(
            "llm_session_multi_pass_chunk_tokens",
            "multi_pass_chunk_tokens",
        )
        overlap_tokens = _effective_session_multi_pass_setting(
            "llm_session_multi_pass_overlap_tokens",
            "multi_pass_overlap_tokens",
        )
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
        return _merge_intents(results)

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

    # Load system prompt from YAML
    system_prompt = _prompts["session_intents"]

    context = (
        f"Counsellor raw input:\n{raw_input}\n\n"
        f"Existing career tracks (for reference — create cards for NEW sectors too):\n{tracks_text or '(none)'}\n\n"
        f"Existing employers (for reference — create cards for NEW companies too):\n{employers_text or '(none)'}\n\n"
        "Extract intents as JSON. Remember: if the memo is about companies or sectors NOT listed above, create cards for them."
    )

    def parse_response(text: str) -> dict:
        thought = ""
        thought_match = re.search(r"<thought>(.*?)</thought>", text, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()
        
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
            parsed["thought"] = thought
            return parsed
        except json.JSONDecodeError:
            return {"cards": [], "already_covered": [], "thought": thought}

    try:
        model = _llm["model"]
        base_phase = (trace_metadata or {}).get("phase")
        phase = str(base_phase) if base_phase else "session_analysis"

        response = _call_with_trace(
            operation="generate_session_intents",
            model=model,
            max_tokens=_llm["max_tokens_session_extraction"],
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": context}],
            timeout_seconds=settings.llm_session_timeout_seconds,
            max_retries=0,
            trace_metadata={
                **(trace_metadata or {}),
                "session_id": session_id,
                "phase": phase,
                "multi_pass_threshold_chars": threshold,
                "multi_pass_chunk_tokens": _effective_session_multi_pass_setting(
                    "llm_session_multi_pass_chunk_tokens",
                    "multi_pass_chunk_tokens",
                ),
                "multi_pass_overlap_tokens": _effective_session_multi_pass_setting(
                    "llm_session_multi_pass_overlap_tokens",
                    "multi_pass_overlap_tokens",
                ),
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
                system=system_prompt + "\n\nIMPORTANT: Your previous response was missing JSON or malformed. Respond with <thought> and JSON.",
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

        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("generate_session_intents: LLM call failed: %s", exc)
        return {"cards": [], "already_covered": [], "thought": ""}
