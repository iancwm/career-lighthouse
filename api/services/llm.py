# api/services/llm.py
import json
import logging

from config import settings

logger = logging.getLogger(__name__)
from cfg import model_cfg

_client = None

_llm = model_cfg["llm"]
_prompts = model_cfg["prompts"]
SCHOOL_NAME = model_cfg["school"]["name"]


def get_client():
    import anthropic

    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def chat_with_context(message: str, resume_text: str | None,
                      chunks: list[dict], history: list[dict],
                      career_context: str | None = None,
                      employer_context: str | None = None) -> str:
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
    employer_summary: str = "",
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
        '          "employer_updates": {\n'
        '            "<employer_slug>": {\n'
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
        "        - FIRST compare the input against the existing KB excerpts provided below.\n"
        "          Only propose changes for facts that are genuinely new, corrected, or\n"
        "          contradictory. Do not re-propose information already covered.\n"
        "        - Only propose profile_updates for fields that the input clearly changes or\n"
        "          corrects. Use the exact field names from CURRENT CAREER PROFILE FIELDS.\n"
        "          Do not guess field names not listed there.\n"
        "        - Only propose employer_updates for employer_slug/field_name pairs that appear\n"
        "          in CURRENT EMPLOYER FACTS. Allowed fields: ep_requirement, intake_seasons,\n"
        "          singapore_headcount_estimate, application_process, counsellor_contact, notes.\n"
        "          Do not guess employer slugs or field names not listed there.\n"
        "        - new_chunks: self-contained facts not present in existing excerpts.\n"
        '          Maximum 6 chunks. Prefer dense, self-contained chunks. Leave chunk_id as "".\n'
        '          If the input is a full counsellor memo covering multiple topics, note that\n'
        '          Session Editor is the better intake path for memo-level ingestion.\n'
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
        f"CURRENT CAREER PROFILE FIELDS (key fields only):\n{profile_summary}\n\n"
        f"CURRENT EMPLOYER FACTS (key fields only):\n{employer_summary or '(No employers configured)'}"
    )

    response = get_client().messages.create(
        model=_llm["model"],
        max_tokens=2048,
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
        f"{str(c['payload'].get('text', ''))[:400]}"
        for i, c in enumerate(retrieved_chunks)
    ) or "(No related knowledge retrieved)"
    existing_draft_text = json.dumps(existing_draft or {}, indent=2, ensure_ascii=False) or "{}"

    system = (
        f"You are a career knowledge curator for {SCHOOL_NAME}.\n"
        "You will be given counsellor research input for a new or underdeveloped career track.\n"
        "Sometimes you will also receive an existing draft. In that case, treat it as the current best draft and improve it cautiously.\n"
        "Return ONLY a JSON object matching the schema below. Do not wrap it in markdown.\n\n"
        "Output schema:\n"
        "{\n"
        '  "slug": "<slug>",\n'
        '  "track_name": "<display name>",\n'
        '  "status": "draft",\n'
        '  "match_description": "<1-2 sentence routing description>",\n'
        '  "match_keywords": ["<keyword>", "<keyword>"],\n'
        '  "ep_sponsorship": "<guidance>",\n'
        '  "compass_score_typical": "<guidance>",\n'
        '  "top_employers_smu": ["<employer>"],\n'
        '  "recruiting_timeline": "<guidance>",\n'
        '  "international_realistic": true,\n'
        '  "entry_paths": ["<path>"],\n'
        '  "salary_range_2024": "<guidance>",\n'
        '  "typical_background": "<guidance>",\n'
        '  "counselor_contact": "",\n'
        '  "notes": "<counsellor notes>",\n'
        '  "source_refs": [{"type": "<note|file>", "label": "<source label>"}],\n'
        '  "structured": {\n'
        '    "sponsorship_tier": "<High|Medium|Low|>",\n'
        '    "compass_points_typical": "<range or empty>",\n'
        '    "salary_min_sgd": 0,\n'
        '    "salary_max_sgd": 0,\n'
        '    "ep_realistic": true\n'
        "  },\n"
        '  "salary_levels": [\n'
        '    {"stage": "<career stage>", "range_sgd": "<SGD range>", "notes": "<bonus/equity context>"}\n'
        "  ],\n"
        '  "visa_pathway_notes": "<multi-step visa path if relevant, empty string otherwise>"\n'
        "}\n\n"
        "Rules:\n"
        "- Preserve the provided slug and track_name exactly.\n"
        "- Only include claims supported by the counsellor input or the retrieved excerpts.\n"
        "- If a fact is unclear, leave it cautious rather than inventing detail.\n"
        "- If an existing draft is provided, preserve its useful fields unless the new evidence clearly improves or corrects them.\n"
        "- match_keywords should be concrete phrases students might actually type.\n"
        "- top_employers_smu and entry_paths may be empty if the input is too weak, but prefer a useful first draft.\n"
        "- Use source_refs with the provided source_type and source_label.\n"
        "- structured fields should be conservative defaults; use 0 for unknown salary bounds and empty strings when unsure.\n"
        "- salary_levels: extract per-stage compensation if the input has level-by-level data. Leave as [] if not present.\n"
        "- visa_pathway_notes: include EP/Tech.Pass/PR timeline and any partnership eligibility conditions if the track has significant international complexity. Empty string if not relevant.\n"
    )

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

    response = get_client().messages.create(
        model=_llm["model"],
        max_tokens=2500,
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


def generate_session_intents(
    raw_input: str,
    existing_tracks: list[dict] | None = None,
    existing_employers: list[dict] | None = None,
) -> dict:
    """Extract distinct update intents from counsellor raw research notes.

    Returns a dict with keys 'cards' (list of IntentCard-shaped dicts) and
    'already_covered' (list of AlreadyCovered-shaped dicts).

    Calls Claude with a structured prompt and retries once on malformed JSON.
    On total failure, returns empty result without raising.
    """
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

    system_prompt = (
        "You are a knowledge extraction assistant for a career advisory platform.\n"
        "Given counsellor research notes (which may be structured memos, tables,\n"
        "or free-form notes), extract distinct update intents for employers and tracks.\n"
        "\n"
        "The input may contain:\n"
        "- Compensation tables (title, base, bonus by career stage)\n"
        "- Career progression timelines\n"
        "- Hiring trends and market analysis\n"
        "- Strategic initiatives and project details\n"
        "- Certifications, competencies, and recommendations\n"
        "- Follow-up actions for the career services team\n"
        "\n"
        "For EACH distinct piece of new information about an employer or track,\n"
        "create a card. A single memo may produce 5-15 cards.\n"
        "\n"
        "IMPORTANT:\n"
        "- Compensation data in tables → create a card with salary_range_2024 (track)\n"
        "  or notes (employer) containing the comp details.\n"
        "- Career progression timelines → create a card with notes or entry_paths.\n"
        "- Hiring trends → create a card with notes (employer) or notes (track).\n"
        "- Follow-up actions → create cards for each action targeting the relevant entity.\n"
        "- Certifications and skills → create a card with match_keywords or notes.\n"
        "\n"
        "Each intent targets EXACTLY ONE domain: 'employer' or 'track'.\n"
        "Prefer concrete field-level changes (e.g. 'update EP requirement to EP4')\n"
        "over vague summaries (e.g. 'improve employer profile'). Be specific.\n"
        "Return ONLY valid JSON with this structure:\n"
        '{\n'
        '  "cards": [\n'
        '    {\n'
        '      "card_id": "card-<short-uuid>",\n'
        '      "domain": "employer" | "track",\n'
        '      "summary": "One-line summary of the change",\n'
        '      "diff": {"slug": "entity-slug", "field_name": "proposed_new_value", ...},\n'
        '      "raw_input_ref": "The original text excerpt that triggered this intent"\n'
        '    }\n'
        '  ],\n'
        '  "already_covered": [\n'
        '    {"content": "...", "reason": "..."}\n'
        '  ]\n'
        '}\n'
        "Rules:\n"
        "- If the note confirms something already in the knowledge base, put it in already_covered (no card).\n"
        "- If the note proposes a change to any entity, create a card. The entity may be NEW — that's fine, it will be auto-created.\n"
        "- A structured memo with compensation tables, career progression, and hiring trends ALWAYS contains new data. Create cards for each distinct piece of information.\n"
        "- If the input contains salary/compensation data for a specific employer, create an employer card with 'notes' containing the comp breakdown.\n"
        "- If the input contains sector-wide hiring trends or market analysis, create a track card with 'notes' containing the market details.\n"
        "- If the input contains follow-up actions, create a card for each action targeting the relevant employer or track.\n"
        "- diff MUST include 'slug' — a lowercase_with_underscores slug derived from the entity name (e.g. 'accenture', 'consulting', 'gs', 'mckinsey').\n"
        "- For 'employer' domain, diff fields must be from:\n"
        "  * employer_name (str), tracks (list of str), ep_requirement (str), intake_seasons (list of str, e.g. ['Apr', 'Oct']), application_process (str), headcount_estimate (str), counselor_contact (str), notes (str).\n"
        "  * CRITICAL: 'tracks' and 'intake_seasons' MUST be lists, not strings.\n"
        "  * Use 'employer_name' NOT 'display_name'.\n"
        "- For 'track' domain, diff fields must be from:\n"
        "  * track_name (str), match_description (str), match_keywords (list of str), ep_sponsorship (str), compass_score_typical (str), top_employers_smu (list of str), recruiting_timeline (str), international_realistic (bool), entry_paths (list of str), salary_range_2024 (str), typical_background (str), counselor_contact (str), notes (str).\n"
        "  * CRITICAL: 'match_keywords', 'top_employers_smu', and 'entry_paths' MUST be lists, not strings.\n"
        "- diff should contain only the fields that need updating — not the entire entity.\n"
        "- raw_input_ref should be a short excerpt (1-2 sentences) from the original note.\n"
        "- Generate unique card_ids using 'card-<short-uuid>' format.\n"
        "- If no changes are needed, return empty cards and populated already_covered.\n"
    )

    context = (
        f"Counsellor raw input:\n{raw_input}\n\n"
        f"Existing career tracks:\n{tracks_text or '(none)'}\n\n"
        f"Existing employers:\n{employers_text or '(none)'}\n\n"
        "Extract intents as JSON:"
    )

    try:
        client = get_client()
        model = _llm["model"]

        response = client.messages.create(
            model=model,
            max_tokens=4096,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": context}],
        )

        text = response.content[0].text.strip()

        # Strip markdown code fences if Claude wraps the JSON
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if "```" in text:
                text = text.rsplit("```", 1)[0]
        text = text.strip()

        try:
            parsed = json.loads(text)
            if "cards" not in parsed:
                parsed = {"cards": [], "already_covered": []}
            return parsed
        except json.JSONDecodeError:
            # Retry with error feedback
            retry_response = client.messages.create(
                model=model,
                max_tokens=4096,
                temperature=0,
                system=system_prompt + "\n\nIMPORTANT: Your previous response was not valid JSON. Respond ONLY with valid JSON.",
                messages=[{"role": "user", "content": context}],
            )
            retry_text = retry_response.content[0].text.strip()
            # Strip markdown code fences on retry too
            if retry_text.startswith("```"):
                retry_text = retry_text.split("\n", 1)[1]
                if "```" in retry_text:
                    retry_text = retry_text.rsplit("```", 1)[0]
            retry_text = retry_text.strip()
            try:
                parsed = json.loads(retry_text)
                if "cards" not in parsed:
                    parsed = {"cards": [], "already_covered": []}
                return parsed
            except json.JSONDecodeError:
                return {"cards": [], "already_covered": []}
    except Exception as exc:
        logger.warning("generate_session_intents: LLM call failed: %s", exc)
        return {"cards": [], "already_covered": []}
