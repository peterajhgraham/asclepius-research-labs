"""Unified hybrid retrieval pipeline: BM25 + Dense + CLIP → RRF → CrossEncoder.

Three retrieval signals are combined via Reciprocal Rank Fusion:

  1. **BM25** — lexical, catches exact gene/protein/drug strings the
     embedder will smear together (e.g. "IL-17A" vs "IL-17").
  2. **Dense (MiniLM)** — semantic text similarity over all proposition
     texts including image captions and table renderings.
  3. **CLIP (ViT-B/32)** — cross-modal: a text query is encoded into the
     CLIP joint space and compared directly to image embeddings, which
     surfaces figures the captioner missed or worded too generically.
     This is the real "multimodal" leg of the retriever.

After RRF fusion, the candidate pool is reranked by a cross-encoder
(ms-marco-MiniLM) over text. Image-only candidates surfaced exclusively
by CLIP carry their caption text into the reranker; if no caption
exists, the metadata filename + page label is used. This means an image
hit always has *something* the cross-encoder can score against.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from app.retrieval.bm25_index import BM25Index
from app.retrieval.clip_index import ClipIndex
from app.retrieval.dense_index import DenseIndex
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.reranker import CrossEncoderReranker

logger = logging.getLogger(__name__)


@dataclass
class RetrievedProposition:
    text: str
    metadata: dict[str, Any]
    score: float
    rerank_score: float = 0.0
    content_type: str = "text"  # text | image | table
    image_hash: str | None = None


class RetrievalPipeline:
    """Hybrid BM25 + Dense + CLIP retrieval with RRF and cross-encoder reranking."""

    def __init__(self) -> None:
        self._bm25 = BM25Index()
        self._dense = DenseIndex()
        self._clip = ClipIndex()
        self._reranker = CrossEncoderReranker()
        # Map BM25/dense doc index -> (content_type, image_hash) for routing
        self._doc_extras: list[dict[str, Any]] = []
        # Map CLIP entry index -> BM25/dense doc index so a CLIP hit can join
        # back to the text-side proposition without duplicating storage.
        self._clip_to_doc: dict[int, int] = {}
        self._built = False

    def add_document(
        self,
        text: str,
        metadata: dict[str, Any],
        content_type: str = "text",
        image_hash: str | None = None,
        image_bytes: bytes | None = None,
        clip_embedding: Any = None,
    ) -> int:
        """Add a document; returns the assigned BM25/dense doc index.

        For images/tables, `image_hash` lets the frontend render the figure
        and `image_bytes`/`clip_embedding` route into the CLIP index.
        """
        self._bm25.add(text, metadata)
        self._dense.add(text, metadata)
        doc_idx = len(self._doc_extras)
        self._doc_extras.append({"content_type": content_type, "image_hash": image_hash})
        if content_type == "image" and (image_bytes is not None or clip_embedding is not None):
            self._clip.add(image_bytes, metadata, precomputed_embedding=clip_embedding)
            self._clip_to_doc[self._clip.size - 1] = doc_idx
        self._built = False
        return doc_idx

    def build(self) -> None:
        logger.info(
            "Building retrieval indexes over %d documents (%d images)...",
            self._bm25.size, self._clip.size,
        )
        self._bm25.build()
        self._dense.build()
        self._clip.build()
        self._built = True
        logger.info("Retrieval indexes ready")

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        rrf_k: int = 60,
        candidate_multiplier: int = 3,
        query_image_bytes: bytes | None = None,
    ) -> list[RetrievedProposition]:
        """Full pipeline. Pass `query_image_bytes` to add image→image retrieval."""
        if not self._built:
            return []

        candidates_k = top_k * candidate_multiplier
        bm25_hits = self._bm25.query(query, top_k=candidates_k)
        dense_hits = self._dense.query(query, top_k=candidates_k)

        # CLIP text→image: surface figures by semantic match to the query
        clip_text_hits_raw = self._clip.query_text(query, top_k=candidates_k)
        clip_text_hits = [
            (self._clip_to_doc[idx], score)
            for idx, score in clip_text_hits_raw
            if idx in self._clip_to_doc
        ]

        ranked_lists = [bm25_hits, dense_hits, clip_text_hits]

        # Optional image→image leg (user uploaded a probe figure)
        if query_image_bytes is not None and self._clip.size > 0:
            clip_img_hits_raw = self._clip.query_image(query_image_bytes, top_k=candidates_k)
            clip_img_hits = [
                (self._clip_to_doc[idx], score)
                for idx, score in clip_img_hits_raw
                if idx in self._clip_to_doc
            ]
            ranked_lists.append(clip_img_hits)

        fused = reciprocal_rank_fusion(*ranked_lists, k=rrf_k)

        candidates: list[dict[str, Any]] = []
        for doc_id, rrf_score in fused[: top_k * 2]:
            doc = self._bm25.get_doc(doc_id)
            extras = self._doc_extras[doc_id] if doc_id < len(self._doc_extras) else {}
            candidates.append({
                **doc,
                "rrf_score": rrf_score,
                "content_type": extras.get("content_type", "text"),
                "image_hash": extras.get("image_hash"),
            })

        reranked = self._reranker.rerank(query, candidates, top_k=top_k)

        return [
            RetrievedProposition(
                text=d["text"],
                metadata=d.get("metadata", {}),
                score=d.get("rrf_score", 0.0),
                rerank_score=d.get("rerank_score", 0.0),
                content_type=d.get("content_type", "text"),
                image_hash=d.get("image_hash"),
            )
            for d in reranked
        ]

    @property
    def is_ready(self) -> bool:
        return self._built and self._bm25.size > 0

    @property
    def doc_count(self) -> int:
        return self._bm25.size

    @property
    def image_count(self) -> int:
        return self._clip.size
