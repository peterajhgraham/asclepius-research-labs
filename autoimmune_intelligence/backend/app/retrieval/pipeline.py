"""Unified hybrid retrieval pipeline: BM25 + Dense → RRF → CrossEncoder."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.retrieval.bm25_index import BM25Index
from app.retrieval.dense_index import DenseIndex
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.reranker import CrossEncoderReranker

logger = logging.getLogger(__name__)


@dataclass
class RetrievedProposition:
    text: str
    metadata: dict[str, Any]
    score: float        # RRF fusion score
    rerank_score: float = 0.0  # CrossEncoder score (higher = more relevant)


class RetrievalPipeline:
    """Hybrid BM25 + Dense retrieval with RRF fusion and CrossEncoder reranking."""

    def __init__(self) -> None:
        self._bm25 = BM25Index()
        self._dense = DenseIndex()
        self._reranker = CrossEncoderReranker()
        self._built = False

    def add_document(self, text: str, metadata: dict[str, Any]) -> None:
        """Stage a document for indexing (call build() afterwards)."""
        self._bm25.add(text, metadata)
        self._dense.add(text, metadata)
        self._built = False

    def build(self) -> None:
        """Build BM25 and FAISS indexes over all staged documents."""
        logger.info("Building retrieval indexes over %d documents...", self._bm25.size)
        self._bm25.build()
        self._dense.build()
        self._built = True
        logger.info("Retrieval indexes ready")

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        rrf_k: int = 60,
        candidate_multiplier: int = 3,
    ) -> list[RetrievedProposition]:
        """Full pipeline: BM25 + Dense → RRF(k=60) → CrossEncoder → top_k.

        Returns empty list if no indexes built yet.
        """
        if not self._built:
            return []

        candidates_k = top_k * candidate_multiplier
        bm25_hits = self._bm25.query(query, top_k=candidates_k)
        dense_hits = self._dense.query(query, top_k=candidates_k)

        # RRF fusion: combine lexical + semantic ranked lists
        fused = reciprocal_rank_fusion(bm25_hits, dense_hits, k=rrf_k)

        # Fetch candidate docs (up to 2x top_k to give reranker headroom)
        candidates: list[dict[str, Any]] = []
        for doc_id, rrf_score in fused[: top_k * 2]:
            doc = self._bm25.get_doc(doc_id)
            candidates.append({**doc, "rrf_score": rrf_score})

        # CrossEncoder reranking
        reranked = self._reranker.rerank(query, candidates, top_k=top_k)

        return [
            RetrievedProposition(
                text=d["text"],
                metadata=d.get("metadata", {}),
                score=d.get("rrf_score", 0.0),
                rerank_score=d.get("rerank_score", 0.0),
            )
            for d in reranked
        ]

    @property
    def is_ready(self) -> bool:
        return self._built and self._bm25.size > 0

    @property
    def doc_count(self) -> int:
        return self._bm25.size
