"""Simple in-memory retrieval layer for DMI.

Embeds abstracts with TF-IDF vectors and retrieves top relevant chunks
for extraction prompts. Uses lightweight in-memory approach for MVP.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Any

from app.services.pubmed_service import PubMedArticle

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer, lowercased."""
    return re.findall(r"[a-z0-9]+", text.lower())


class SimpleRetriever:
    """TF-IDF based in-memory retriever for PubMed abstracts."""

    def __init__(self, articles: list[PubMedArticle]) -> None:
        self.articles = articles
        self.docs: list[dict[str, Any]] = []
        self._idf: dict[str, float] = {}
        self._doc_vecs: list[dict[str, float]] = []
        self._build_index()

    def _build_index(self) -> None:
        """Build TF-IDF index from article abstracts."""
        doc_freq: Counter[str] = Counter()

        for article in self.articles:
            text = f"{article.title} {article.abstract}"
            tokens = _tokenize(text)
            tf = Counter(tokens)
            unique_tokens = set(tokens)
            for t in unique_tokens:
                doc_freq[t] += 1
            self.docs.append({
                "article": article,
                "tokens": tokens,
                "tf": tf,
                "text": text,
            })

        n = len(self.docs) or 1
        self._idf = {
            term: math.log(n / (1 + freq))
            for term, freq in doc_freq.items()
        }

        for doc in self.docs:
            vec: dict[str, float] = {}
            total = len(doc["tokens"]) or 1
            for term, count in doc["tf"].items():
                tf_val = count / total
                idf_val = self._idf.get(term, 0)
                vec[term] = tf_val * idf_val
            self._doc_vecs.append(vec)

    def retrieve(self, query: str, top_k: int = 20) -> list[PubMedArticle]:
        """Retrieve top-k articles most relevant to the query."""
        if not self.docs:
            return []

        query_tokens = _tokenize(query)
        query_tf = Counter(query_tokens)
        total = len(query_tokens) or 1
        query_vec: dict[str, float] = {}
        for term, count in query_tf.items():
            tf_val = count / total
            idf_val = self._idf.get(term, 0)
            query_vec[term] = tf_val * idf_val

        scores: list[tuple[int, float]] = []
        for i, doc_vec in enumerate(self._doc_vecs):
            score = sum(
                query_vec.get(t, 0) * doc_vec.get(t, 0)
                for t in set(query_vec) | set(doc_vec)
                if query_vec.get(t, 0) > 0 and doc_vec.get(t, 0) > 0
            )
            scores.append((i, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [self.docs[i]["article"] for i, _ in scores[:top_k]]
