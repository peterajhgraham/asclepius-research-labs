"""CLIP-based multimodal index.

CLIP (ViT-B/32) projects images and short texts into the same 512-dim
embedding space, so a textual query like "kaplan-meier survival curve for
TNF blockade" can directly retrieve figures from ingested papers without
needing a caption. Captions are still computed (Haiku vision) for the
text retrieval path, but CLIP provides a complementary cross-modal
signal that catches figures the captioner missed or worded differently.

Why CLIP and not a hosted multimodal embedder (Voyage, OpenAI)?
  - No external API dependency at index time (ingestion stays offline-friendly).
  - Free at inference, deterministic across runs.
  - ~150 MB model, runs CPU-only on Railway free tier.

The index is built lazily on first query (loading the CLIP weights and
encoding all stored images takes a few seconds), and is rebuilt
incrementally as new documents are ingested.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

_CLIP_MODEL = "sentence-transformers/clip-ViT-B-32"
_EMB_DIM = 512


@dataclass
class ClipEntry:
    image_bytes: bytes | None  # may be None if loaded purely from a cached embedding
    metadata: dict[str, Any]
    embedding: Optional["Any"] = None  # numpy.ndarray (float32, normalized)


@dataclass
class ClipIndex:
    """A cross-modal text↔image retrieval index."""

    _entries: list[ClipEntry] = field(default_factory=list)
    _index: Any = field(default=None, init=False)
    _model: Any = field(default=None, init=False)
    _model_loaded: bool = field(default=False, init=False)
    _model_failed: bool = field(default=False, init=False)

    def _load_model(self) -> None:
        if self._model_loaded or self._model_failed:
            return
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
            self._model = SentenceTransformer(_CLIP_MODEL)
            self._model_loaded = True
            logger.info("CLIP model loaded: %s", _CLIP_MODEL)
        except Exception:
            self._model_failed = True
            logger.warning("CLIP model unavailable — multimodal retrieval disabled", exc_info=True)

    def encode_image(self, image_bytes: bytes) -> Optional["Any"]:
        """Encode a single image to a normalized 512-dim float32 vector."""
        self._load_model()
        if not self._model:
            return None
        try:
            from PIL import Image  # type: ignore[import-untyped]
            import numpy as np

            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            emb = self._model.encode([img], normalize_embeddings=True, show_progress_bar=False)
            return emb[0].astype(np.float32)
        except Exception:
            logger.debug("CLIP image encode failed", exc_info=True)
            return None

    def encode_text(self, text: str) -> Optional["Any"]:
        self._load_model()
        if not self._model:
            return None
        try:
            import numpy as np
            emb = self._model.encode([text], normalize_embeddings=True, show_progress_bar=False)
            return emb[0].astype(np.float32)
        except Exception:
            logger.debug("CLIP text encode failed", exc_info=True)
            return None

    def add(
        self,
        image_bytes: bytes | None,
        metadata: dict[str, Any],
        precomputed_embedding: Optional["Any"] = None,
    ) -> Optional["Any"]:
        """Add an image entry. Returns the embedding (so callers can persist it).

        If `precomputed_embedding` is supplied, no model call is made.
        """
        if precomputed_embedding is not None:
            emb = precomputed_embedding
        else:
            if image_bytes is None:
                return None
            emb = self.encode_image(image_bytes)
            if emb is None:
                return None
        self._entries.append(ClipEntry(
            image_bytes=image_bytes,
            metadata=metadata,
            embedding=emb,
        ))
        self._index = None  # invalidate
        return emb

    def build(self) -> None:
        if not self._entries:
            return
        try:
            import faiss  # type: ignore[import-untyped]
            import numpy as np

            vecs = np.stack([e.embedding for e in self._entries if e.embedding is not None]).astype(np.float32)
            if vecs.size == 0:
                return
            self._index = faiss.IndexFlatIP(vecs.shape[1])
            self._index.add(vecs)
            logger.info("CLIP index built: %d image vectors, dim=%d", vecs.shape[0], vecs.shape[1])
        except Exception:
            logger.warning("CLIP FAISS build failed", exc_info=True)

    def query_text(self, query: str, top_k: int = 8, min_score: float = 0.18) -> list[tuple[int, float]]:
        """Text→image search. Returns (entry_index, cosine_similarity)."""
        if self._index is None or not self._entries:
            return []
        emb = self.encode_text(query)
        if emb is None:
            return []
        return self._search(emb, top_k=top_k, min_score=min_score)

    def query_image(self, image_bytes: bytes, top_k: int = 8, min_score: float = 0.40) -> list[tuple[int, float]]:
        """Image→image search (used when the user uploads a probe figure)."""
        if self._index is None or not self._entries:
            return []
        emb = self.encode_image(image_bytes)
        if emb is None:
            return []
        return self._search(emb, top_k=top_k, min_score=min_score)

    def _search(self, query_emb: "Any", top_k: int, min_score: float) -> list[tuple[int, float]]:
        try:
            import numpy as np
            d, i = self._index.search(query_emb.reshape(1, -1).astype(np.float32), top_k)
            return [
                (int(idx), float(score))
                for idx, score in zip(i[0], d[0])
                if idx >= 0 and score >= min_score
            ]
        except Exception:
            return []

    @property
    def size(self) -> int:
        return len(self._entries)
