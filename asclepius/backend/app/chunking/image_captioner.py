"""Scientific figure captioner using Claude Haiku vision.

Converts extracted PDF images into text propositions that can be indexed
in the existing BM25+FAISS text retrieval pipeline.
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
    "and key results visible in the image. Be specific."
)


def caption_image(
    image_bytes: bytes,
    media_type: str,
    source_metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Caption a single image and return proposition dicts with image_data embedded.

    Falls back to an empty list (silently) when Anthropic is unavailable.
    """
    import base64

    meta = source_metadata or {}
    image_b64 = base64.b64encode(image_bytes).decode()

    try:
        import anthropic
        from app.core.config import settings

        if not settings.anthropic_api_key:
            return []

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
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": _SYSTEM},
                ],
            }],
        )

        caption_text = response.content[0].text.strip()
        # Split into sentences as separate propositions
        sentences = [s.strip() for s in caption_text.split(".") if len(s.strip()) > 20]
        return [
            {
                "text": s + ".",
                "metadata": {**meta, "extraction": "haiku_vision", "type": "figure_caption"},
                "image_data": image_b64,
                "image_media_type": media_type,
            }
            for s in sentences
        ]
    except Exception:
        logger.debug("Image captioning failed", exc_info=True)
        return []


def caption_images(
    image_blocks: list,  # list[ImageBlock] from document_parser
    source_metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Caption a list of ImageBlock objects, returns all proposition dicts."""
    all_props = []
    for block in image_blocks:
        page_meta = {**(source_metadata or {}), "page": block.page}
        props = caption_image(block.image_bytes, block.media_type, page_meta)
        all_props.extend(props)
    return all_props
