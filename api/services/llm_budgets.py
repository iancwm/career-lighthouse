"""Budgeting and config helpers for LLM prompt assembly."""

from __future__ import annotations

from typing import Any


def llm_setting(
    settings: object,
    llm_cfg: dict[str, Any],
    setting_name: str,
    model_key: str,
    default: Any = None,
) -> Any:
    value = getattr(settings, setting_name, None)
    if value is not None:
        return value
    return llm_cfg.get(model_key, default)


def llm_int(
    settings: object,
    llm_cfg: dict[str, Any],
    setting_name: str,
    model_key: str,
    default: int,
) -> int:
    value = llm_setting(settings, llm_cfg, setting_name, model_key, default)
    if value is None:
        return int(default)
    return int(value)


def llm_bool(
    settings: object,
    llm_cfg: dict[str, Any],
    setting_name: str,
    model_key: str,
    default: bool,
) -> bool:
    value = llm_setting(settings, llm_cfg, setting_name, model_key, default)
    return bool(value)


def effective_session_multi_pass_setting(
    settings: object,
    llm_cfg: dict[str, Any],
    setting_name: str,
    model_key: str,
) -> int:
    value = getattr(settings, setting_name, None)
    if value is not None:
        return int(value)
    return int(llm_cfg[model_key])


def trim_to_budget(text: str, budget: int | None) -> str:
    text = text.strip()
    if budget is None or budget <= 0:
        return text
    if len(text) <= budget:
        return text
    return text[:budget].rstrip()


def budget_chunks(
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
        char_budget = (
            min(char_budget, max_chunk_chars)
            if char_budget is not None
            else max_chunk_chars
        )
    for chunk in limited:
        payload = chunk.get("payload", {}) if isinstance(chunk, dict) else {}
        budgeted.append(
            {
                "score": chunk.get("score") if isinstance(chunk, dict) else None,
                "payload": {
                    "source_filename": payload.get("source_filename", "unknown"),
                    "text": trim_to_budget(str(payload.get("text", "")), char_budget),
                },
            }
        )
    return budgeted


def join_budgeted_sections(
    sections: list[str], *, max_context_chars: int | None
) -> str:
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


def budget_history(
    history: list[dict], *, max_turns: int, max_chars: int | None
) -> str:
    lines = []
    for message in history[-max_turns:]:
        role = str(message.get("role", "user")).upper()
        content = trim_to_budget(str(message.get("content", "")), max_chars)
        lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "None"
