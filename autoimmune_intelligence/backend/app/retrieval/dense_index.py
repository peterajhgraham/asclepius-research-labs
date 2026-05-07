"""Dense retrieval index using FAISS IndexFlatIP + sentence-transformers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass
class DenseIndex:
    _docs: list[dict[str, Any]] = field(default_factory=list)
    _index: Any = field(default=None, init=False)
    _model: Any = field(default=None, init=False)
    _model_loaded: bool = field(default=False, init=False)

    def _load_model(self) -> None:
        if self._model_loaded:
            return
        self._model_loaded = True
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
            self._model = SentenceTransformer(_EMBED_MODEL)
            logger.info("Dense retrieval model loaded: %s", _EMBED_MODEL)
        except ImportError:
            logger.warning("sentence-transformers not installed — dense retrieval disabled")

    def add(self, text: str, metadata: dict[str, Any]) -> None:
        self._docs.append({"text": text, "metadata": metadata})
        self._index = None  # invalidate cached index

    def build(self) -> None:
        """Build FAISS index from all added documents."""
        self._load_model()
        if not self._model or not self._docs:
            return
        try:
            import faiss  # type: ignore[import-untyped]
            import numpy as np

            texts = [d["text"] for d in self._docs]
            embeddings = self._model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
                batch_size=64,
            )
            dim = embeddings.shape[1]
            self._index = faiss.IndexFlatIP(dim)
            self._index.add(embeddings.astype(np.float32))
            logger.info("Dense index built: %d vectors, dim=%d", len(texts), dim)
        except Exception:
            logger.warning("FAISS index build failed — dense retrieval disabled", exc_info=True)

    def query(self, q: str, top_k: int = 20) -> list[tuple[int, float]]:
        """Return (doc_index, score) pairs sorted by descending cosine similarity."""
        if self._index is None or self._model is None:
            return []
        try:
            import numpy as np

            q_emb = self._model.encode([q], normalize_embeddings=True)
            distances, indices = self._index.search(q_emb.astype(np.float32), top_k)
            return [
                (int(i), float(d))
                for i, d in zip(indices[0], distances[0])
                if i >= 0 and d > 0
            ]
        except Exception:
            logger.warning("Dense query failed", exc_info=True)
            return []

    def get_doc(self, idx: int) -> dict[str, Any]:
        return self._docs[idx]

    @property
    def size(self) -> int:
        return len(self._docs)
