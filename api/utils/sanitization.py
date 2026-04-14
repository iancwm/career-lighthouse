"""Sanitization utilities for prompt-injection defence.

Applied to document chunks during RAG ingestion so that adversarial
instructions embedded in uploaded PDFs/DOCX files cannot hijack LLM behaviour
when the chunk text is later interpolated into system prompts.

This is a defence-in-depth layer — keep upload size limits and content-type
validation in place alongside this module.
"""

import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compiled patterns (built once at import time for performance)
# ---------------------------------------------------------------------------

# Angle-bracket directives: <|...|>, <...>, including multi-line payloads
_ANGLE_DIRECTIVE_RE = re.compile(r"<\|?.*?\|?>", re.DOTALL)

# Common jailbreak / override phrases (case-insensitive)
_JAILBREAK_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"system\s+prompt\s+override", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?safety\s+guidelines?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:in\s+)?(?:DAN|jailbreak|developer)\s+mode", re.IGNORECASE),
    re.compile(r"forget\s+(?:all\s+)?(?:your\s+)?(?:previous\s+)?(?:instructions?|training)", re.IGNORECASE),
]

# Collapse runs of 3+ newlines down to two (normalise excessive whitespace)
_EXCESSIVE_NEWLINES_RE = re.compile(r"\n{3,}")


def sanitize_for_prompt(text: str) -> str:
    """Remove prompt-injection artefacts from *text* before it enters an LLM prompt.

    Operations (applied in order):
    1. Strip angle-bracket directives (``<|...|>``, ``<...>``).
    2. Replace known jailbreak phrases with ``[REDACTED]``.
    3. Collapse runs of 3+ newlines to two.
    4. Strip leading/trailing whitespace.

    The function is idempotent: ``sanitize_for_prompt(sanitize_for_prompt(t)) == sanitize_for_prompt(t)``.
    """
    if not text:
        return text

    original = text

    # 1. Remove angle-bracket directives
    text = _ANGLE_DIRECTIVE_RE.sub("", text)

    # 2. Replace jailbreak phrases
    for pattern in _JAILBREAK_PATTERNS:
        text = pattern.sub("[REDACTED]", text)

    # 3. Normalise excessive whitespace
    text = _EXCESSIVE_NEWLINES_RE.sub("\n\n", text)

    # 4. Strip
    text = text.strip()

    if text != original.strip():
        logger.debug("sanitize_for_prompt: content modified (len %d → %d)", len(original), len(text))

    return text
