"""Proposition extractor using Claude Haiku for atomic claim decomposition.

Falls back to sliding-window chunks when Anthropic is unavailable.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.chunking.sliding_window import chunk_text

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a biomedical proposition extractor. Given a passage of immunology "
    "or disease biology text, extract all atomic, self-contained factual propositions "
    "as a JSON array of strings. Each proposition must be a single declarative sentence "
    "that makes sense without surrounding context. Focus on mechanistic claims, "
    "clinical facts, and gene/pathway/cytokine relationships. "
    "Return ONLY the JSON array with no other text."
)

_HAIKU_MODEL = "claude-haiku-4-5-20251001"
_MAX_CHUNKS = 5  # per document, to keep extraction costs bounded


def extract_propositions(
    text: str,
    source_metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Extract propositions from text, with Haiku as primary and sliding-window as fallback.

    Returns a list of dicts with 'text' and 'metadata' keys.
    """
    meta = source_metadata or {}
    try:
        return _extract_with_haiku(text, meta)
    except Exception:
        logger.debug("Haiku proposition extraction failed — using sliding window", exc_info=True)
        return _fallback_chunks(text, meta)


def _extract_with_haiku(text: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    import anthropic

    from app.core.config import settings

    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    chunks = chunk_text(text, chunk_size=400, overlap=50)
    all_props: list[dict[str, Any]] = []

    for chunk in chunks[:_MAX_CHUNKS]:
        response = client.messages.create(
            model=_HAIKU_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": f"{_SYSTEM}\n\nText:\n{chunk}"}],
        )
        content = response.content[0].text.strip()
        if content.startswith("["):
            try:
                propositions = json.loads(content)
                for prop in propositions:
                    if isinstance(prop, str) and len(prop) > 20:
                        all_props.append({
                            "text": prop,
                            "metadata": {**metadata, "extraction": "haiku"},
                        })
            except json.JSONDecodeError:
                logger.debug("JSON parse failed for Haiku proposition response")

    return all_props


def _fallback_chunks(text: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"text": chunk, "metadata": {**metadata, "extraction": "sliding_window"}}
        for chunk in chunk_text(text, chunk_size=100, overlap=20)
    ]
