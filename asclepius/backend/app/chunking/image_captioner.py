"""Scientific figure captioner + CLIP embedder.

This is the bridge between extracted figure bytes and indexable
multimodal propositions. For each `ImageBlock` we produce:

  - A content-addressed disk location (via `ImageStore`) so the frontend
    can stream the image directly without ballooning the DB.
  - A CLIP image embedding for the cross-modal retrieval leg, computed
    once at ingestion time and persisted as a float32 blob so the index
    can be rebuilt cheaply on restart.
  - A short Haiku-vision caption split into 2-4 atomic propositions for
    the BM25 / dense text retrieval legs.

If Anthropic / Haiku is unavailable, captioning silently degrades to a
single placeholder proposition derived from the source filename + page
— enough to keep the figure reachable via CLIP and metadata search.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_HAIKU_MODEL = "claude-haiku-4-5-20251001"
_SYSTEM = (
    "You are a scientific figure analyst. Given an image from a scientific paper, "
    "describe what the figure shows in 2-4 atomic, self-contained factual sentences "
    "suitable for indexing as retrieval propositions. Each sentence must stand alone "
    "without referring to 'the figure' or 'panel A' — state the scientific claim directly. "
    "Focus on quantitative findings, biological relationships, experimental conditions, "
    "axis labels, and key results visible in the image. Be specific."
)


def _haiku_caption(image_bytes: bytes, media_type: str) -> str:
    try:
        import base64

        import anthropic
        from app.core.config import settings

        if not settings.anthropic_api_key:
            return ""

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=_HAIKU_MODEL,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64.b64encode(image_bytes).decode(),
                        },
                    },
                    {"type": "text", "text": _SYSTEM},
                ],
            }],
        )
        return (response.content[0].text or "").strip()
    except Exception:
        logger.debug("Haiku caption failed", exc_info=True)
        return ""


def caption_image_block(
    image_block: Any,
    source_metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Process a single ImageBlock → list of multimodal proposition dicts.

    Each dict carries: text, metadata, content_type='image', image_hash,
    image_bytes, clip_embedding, media_type.
    """
    from app.retrieval.clip_index import ClipIndex
    from app.storage.image_store import get_image_store

    meta_base = {**(source_metadata or {}), "page": image_block.page, "type": "figure"}
    store = get_image_store()
    image_hash, _path, _mt = store.save(image_block.image_bytes, image_block.media_type)

    # CLIP embedding (used by the multimodal retrieval leg)
    # We instantiate a transient ClipIndex purely as an encoder facade so this
    # function stays decoupled from the main retrieval pipeline singleton.
    clip = _shared_clip()
    embedding = clip.encode_image(image_block.image_bytes) if clip else None

    # Caption → atomic sentences
    caption = _haiku_caption(image_block.image_bytes, image_block.media_type)
    sentences: list[str] = []
    if caption:
        sentences = [s.strip() for s in caption.replace("\n", " ").split(". ") if len(s.strip()) > 18]
    if not sentences:
        # Fallback proposition so the figure remains discoverable via CLIP
        filename = meta_base.get("filename", "document")
        sentences = [f"Figure on page {image_block.page} of {filename}."]

    props: list[dict[str, Any]] = []
    for s in sentences:
        text = s if s.endswith(".") else s + "."
        props.append({
            "text": text,
            "metadata": {**meta_base, "extraction": "haiku_vision", "image_hash": image_hash},
            "content_type": "image",
            "image_hash": image_hash,
            "image_bytes": image_block.image_bytes,
            "image_media_type": image_block.media_type,
            "clip_embedding": embedding,
        })
    return props


def caption_images(
    image_blocks: list,
    source_metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Caption a list of ImageBlock objects → flat list of proposition dicts."""
    all_props: list[dict[str, Any]] = []
    for block in image_blocks:
        all_props.extend(caption_image_block(block, source_metadata))
    return all_props


_clip_singleton: Any = None


def _shared_clip():
    """Return a shared ClipIndex purely for encoding (not for storage).

    We do not add to this index — it just hosts the loaded model so we
    avoid paying the load cost per image.
    """
    global _clip_singleton
    if _clip_singleton is None:
        from app.retrieval.clip_index import ClipIndex
        _clip_singleton = ClipIndex()
    return _clip_singleton
