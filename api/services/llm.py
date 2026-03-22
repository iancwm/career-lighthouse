# api/services/llm.py
import anthropic
from config import settings

_client = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


SCHOOL_NAME = "SMU (Singapore Management University)"


def chat_with_context(message: str, resume_text: str | None,
                      chunks: list[dict], history: list[dict]) -> str:
    kb_text = "\n\n---\n\n".join(
        f"[{c['payload']['source_filename']}]\n{c['payload']['text']}"
        for c in chunks
    )
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in history[-10:]
    ) if history else "None"

    user_content = (
        f"Student resume:\n{resume_text or 'Not provided'}\n\n"
        f"School knowledge base:\n{kb_text or 'No documents uploaded yet.'}\n\n"
        f"Conversation so far:\n{history_text}\n\n"
        f"Student question: {message}"
    )

    response = get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=(
            f"You are a knowledgeable career advisor at {SCHOOL_NAME}. "
            "Answer questions using the provided school knowledge base. "
            "Always cite which document your advice comes from by name. "
            "Be specific to this school's career paths and recruiting relationships. "
            "If the knowledge base has no relevant information, say so honestly."
        ),
        messages=[{"role": "user", "content": user_content}],
    )
    return response.content[0].text


def generate_brief(resume_text: str, chunks: list[dict]) -> str:
    kb_text = "\n\n---\n\n".join(
        f"[{c['payload']['source_filename']}]\n{c['payload']['text']}"
        for c in chunks
    )

    response = get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=(
            "You are a career counselor assistant. Given a student's resume and "
            "school-specific career knowledge, produce a pre-meeting brief with: "
            "(1) Student's apparent career goals, "
            "(2) Resume gaps vs. target paths, "
            "(3) 3-5 recommended talking points grounded in the knowledge base. "
            "Be concise and actionable."
        ),
        messages=[{"role": "user", "content":
            f"Resume:\n{resume_text}\n\nKnowledge base:\n{kb_text}"}],
    )
    return response.content[0].text
