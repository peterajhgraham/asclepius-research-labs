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

def classify_complexity(query: str) -> str:
    """Classify query complexity as 'simple' or 'complex'.

    Used to pre-select the starting LLM tier before routing.
    """
    lower = query.lower()

    complex_hits = sum(1 for p in _COMPLEX_PATTERNS if re.search(p, lower))
    word_count = len(query.split())

    if complex_hits >= 1 or word_count > 10:
        return "complex"
    return "simple"


def starting_tier(complexity: str) -> int:
    """Return the tier index (0=Haiku, 1=Sonnet, 2=Opus) to start routing at."""
    return {"simple": 0, "complex": 1}.get(complexity, 0)
