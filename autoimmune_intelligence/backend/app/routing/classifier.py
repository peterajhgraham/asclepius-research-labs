"""Query complexity classifier for LLM tier selection."""

from __future__ import annotations

import re

_COMPLEX_PATTERNS = [
    r"\bcompar\w+\b",       # compare, comparison
    r"\bmechanism\w*\b",    # mechanism, mechanisms
    r"\bpathogenesis\b",
    r"\bsynth\w+\b",        # synthesis, synthesize
    r"\bcausal\b",
    r"\binteraction\w*\b",
    r"\bcombination\b",
    r"\bepigeneti\w+\b",
    r"\bmultipl\w+\b",      # multiple
    r"\bcontrast\w*\b",
    r"\bdifferenti\w+\b",   # differentiate, differentiation
]

_MULTI_ENTITY_THRESHOLD = 3  # word count heuristic for named entities


def classify_complexity(query: str) -> str:
    """Classify query complexity as 'simple', 'medium', or 'complex'.

    Used to pre-select the starting LLM tier before routing.
    """
    lower = query.lower()

    complex_hits = sum(1 for p in _COMPLEX_PATTERNS if re.search(p, lower))
    word_count = len(query.split())

    if complex_hits >= 2 or word_count > 20:
        return "complex"
    if complex_hits == 1 or word_count > 10:
        return "medium"
    return "simple"


def starting_tier(complexity: str) -> int:
    """Return the tier index (0=Haiku, 1=Sonnet, 2=Opus) to start routing at."""
    return {"simple": 0, "medium": 0, "complex": 1}.get(complexity, 0)
