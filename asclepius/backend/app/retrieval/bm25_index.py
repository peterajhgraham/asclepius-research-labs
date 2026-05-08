"""BM25 lexical index using rank-bm25."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


def tokenize(text: str) -> list[str]:
    """Canonical tokenizer — lowercase, strip punctuation, split on whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", " ", text)
    return [t for t in text.split() if len(t) > 1]


@dataclass
class BM25Index:
    _docs: list[dict[str, Any]] = field(default_factory=list)
    _bm25: Any = field(default=None, init=False)

    def add(self, text: str, metadata: dict[str, Any]) -> None:
        self._docs.append({"text": text, "metadata": metadata})
        self._bm25 = None  # invalidate cached index

    def build(self) -> None:
        """Build BM25 index from all added documents."""
        if not self._docs:
            return
        try:
            from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]
            corpus = [tokenize(d["text"]) for d in self._docs]
            self._bm25 = BM25Okapi(corpus)
        except ImportError:
            pass  # falls back to empty results at query time

    def query(self, q: str, top_k: int = 20) -> list[tuple[int, float]]:
        """Return (doc_index, score) pairs sorted by descending BM25 score."""
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(tokenize(q))
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(idx, float(sc)) for idx, sc in ranked[:top_k] if sc > 0]

    def get_doc(self, idx: int) -> dict[str, Any]:
        return self._docs[idx]

    @property
    def size(self) -> int:
        return len(self._docs)
