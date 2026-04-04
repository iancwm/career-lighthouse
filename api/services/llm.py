# api/services/llm.py
import anthropic
from config import settings
from cfg import model_cfg

_client = None

_llm = model_cfg["llm"]
_prompts = model_cfg["prompts"]
SCHOOL_NAME = model_cfg["school"]["name"]


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def chat_with_context(message: str, resume_text: str | None,
                      chunks: list[dict], history: list[dict],
                      career_context: str | None = None) -> str:
    kb_text = "\n\n---\n\n".join(
        f"[{c['payload']['source_filename']}]\n{c['payload']['text']}"
        for c in chunks
    )
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in history[-_llm["history_window"]:]
    ) if history else "None"

    # Career context block (from YAML profile) is prepended ahead of KB chunks
    # so the LLM treats structured institutional facts as primary context.
    context_sections = []
    if career_context:
        context_sections.append(career_context)
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

    response = get_client().messages.create(
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
) -> dict:
    """Call Claude to produce a structured KB diff from counsellor input.

    Returns the raw parsed JSON dict (caller validates with Pydantic).
    Raises ValueError if Claude returns malformed JSON.
    """
    import json

    system = (
        f"You are a knowledge base curator for {SCHOOL_NAME}'s career advisory AI.\n"
        "        You will be given new input text and excerpts from the existing knowledge base.\n"
        "        Your task: identify what the input adds, changes, or contradicts relative to\n"
        "        the existing KB. Return ONLY a JSON object matching the schema below.\n"
        "        Do not add explanatory text outside the JSON.\n\n"
        "        Output schema:\n"
        "        {\n"
        '          "interpretation_bullets": ["<2-5 short bullets — plain English>"],\n'
        '          "profile_updates": {\n'
        '            "<career_type_slug>": {\n'
        '              "<field_name>": { "old": "<current value or null>", "new": "<proposed>" }\n'
        "            }\n"
        "          },\n"
        '          "new_chunks": [\n'
        '            { "text": "<chunk>", "source_type": "note", "source_label": "counsellor_note",\n'
        '              "career_type": "<slug or null>", "chunk_id": "" }\n'
        "          ],\n"
        '          "already_covered": [\n'
        '            { "excerpt": "<excerpt>", "source_doc": "<filename>" }\n'
        "          ]\n"
        "        }\n\n"
        "        Rules:\n"
        "        - Only propose profile_updates for fields that the input clearly changes or\n"
        "          corrects. Use the exact field names from CURRENT CAREER PROFILE FIELDS.\n"
        "          Do not guess field names not listed there.\n"
        "        - new_chunks: self-contained facts not present in existing excerpts.\n"
        '          Maximum 3 chunks. Prefer fewer, denser chunks. Leave chunk_id as "".\n'
        "        - already_covered: existing KB excerpts substantially overlapping with the\n"
        "          input. Include up to 5.\n"
        "        - career_type: use the slug from CURRENT CAREER PROFILE FIELDS, or null."
    )

    formatted_chunks = "\n\n".join(
        f"[{i+1}] (score={c['score']:.3f}) source={c['payload']['source_filename']}\n"
        f"{c['payload']['text'][:400]}"
        for i, c in enumerate(retrieved_chunks)
    ) or "(No existing KB content retrieved)"

    user = (
        f"INPUT TEXT:\n{counsellor_input}\n\n"
        f"EXISTING KB EXCERPTS (top 10 by semantic similarity):\n{formatted_chunks}\n\n"
        f"CURRENT CAREER PROFILE FIELDS (key fields only):\n{profile_summary}"
    )

    response = get_client().messages.create(
        model=_llm["model"],
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
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


def generate_brief(resume_text: str, chunks: list[dict]) -> str:
    kb_text = "\n\n---\n\n".join(
        f"[{c['payload']['source_filename']}]\n{c['payload']['text']}"
        for c in chunks
    )

    response = get_client().messages.create(
        model=_llm["model"],
        max_tokens=_llm["max_tokens"],
        system=_prompts["brief_system"],
        messages=[{"role": "user", "content":
            f"Resume:\n{resume_text}\n\nKnowledge base:\n{kb_text}"}],
    )
    return response.content[0].text
