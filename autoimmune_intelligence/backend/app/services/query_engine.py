"""Keyword-based retrieval engine for the autoimmune knowledge base.

Scores each KB entry against a user query using normalised token overlap
and returns the best-matching entries above a relevance threshold.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.data.knowledge_base import ENTRIES, KBEntry


@dataclass
class ScoredEntry:
    entry: KBEntry
    score: float


def _tokenize(text: str) -> set[str]:
    """Lowercase, strip punctuation, and split into unique tokens."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", " ", text)
    return {t for t in text.split() if len(t) > 1}


def search(query: str, top_k: int = 3, threshold: float = 0.05) -> list[ScoredEntry]:
    """Return the *top_k* KB entries most relevant to *query*.

    Scoring considers:
    1. Keyword overlap  — fraction of entry keywords matched by query tokens.
    2. Topic overlap     — bonus for query tokens found in the entry topic.
    3. Token recall      — fraction of query tokens found in any entry field.
    """
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    scored: list[ScoredEntry] = []

    for entry in ENTRIES:
        kw_tokens = {k.lower() for k in entry.keywords}
        topic_tokens = _tokenize(entry.topic)

        # keyword hit ratio
        kw_hits = query_tokens & kw_tokens
        kw_score = len(kw_hits) / len(kw_tokens) if kw_tokens else 0.0

        # topic hit ratio (bonus weight)
        topic_hits = query_tokens & topic_tokens
        topic_score = len(topic_hits) / len(topic_tokens) if topic_tokens else 0.0

        # combined score (keyword 60%, topic 40%)
        score = 0.6 * kw_score + 0.4 * topic_score

        if score >= threshold:
            scored.append(ScoredEntry(entry=entry, score=score))

    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:top_k]
