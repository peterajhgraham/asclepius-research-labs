"""Cross-encoder reranker using ms-marco-MiniLM-L-6-v2."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_CE_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@dataclass
class CrossEncoderReranker:
    _model: Any = field(default=None, init=False)
    _model_loaded: bool = field(default=False, init=False)

    def _load(self) -> None:
        if self._model_loaded:
            return
        self._model_loaded = True
        try:
            from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]
            self._model = CrossEncoder(_CE_MODEL)
            logger.info("CrossEncoder reranker loaded: %s", _CE_MODEL)
        except Exception:
            logger.warning(
                "sentence-transformers failed to load (missing or incompatible version) "
                "— reranking disabled, using RRF order",
                exc_info=True,
            )

    def rerank(
        self,
        query: str,
        docs: list[dict[str, Any]],
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Rerank docs by cross-encoder relevance score.

        Falls back to RRF-fused order when cross-encoder is unavailable.
        """
        self._load()
        if not self._model or not docs:
            return docs[:top_k]
        try:
            pairs = [(query, d["text"]) for d in docs]
            scores = self._model.predict(pairs)
            scored = sorted(zip(scores, docs), key=lambda x: float(x[0]), reverse=True)
            return [
                {**d, "rerank_score": float(sc)}
                for sc, d in scored[:top_k]
            ]
        except Exception:
            logger.warning("Reranking failed — using RRF order", exc_info=True)
            return docs[:top_k]
