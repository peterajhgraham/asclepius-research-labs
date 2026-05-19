"""Document ingestion service.

Accepts raw PDF bytes, runs the full multimodal RAG pipeline:
  PDF → text blocks + image blocks
  text blocks → proposition_extractor (Haiku) or sliding_window fallback
  image blocks → image_captioner (Haiku vision) → text propositions
  all propositions → SQLite DB → live BM25+FAISS index
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def ingest_document(
    pdf_bytes: bytes,
    filename: str,
    source_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ingest a PDF document into the retrieval pipeline.

    Returns a summary dict: {propositions_added, figures_captioned, pages}.
    """
    from app.chunking.document_parser import DocumentParser
    from app.chunking.image_captioner import caption_images
    from app.chunking.proposition_extractor import extract_propositions
    from app.db.store import PropositionStore
    from app.core.config import settings
    from app.services.retrieval_service import get_pipeline

    meta = {
        "source_type": "document",
        "filename": filename,
        **(source_metadata or {}),
    }

    parser = DocumentParser()
    text_blocks, image_blocks = parser.parse_pdf_bytes(pdf_bytes, filename)

    # --- Text propositions ---
    text_props: list[dict[str, Any]] = []
    for block in text_blocks:
        block_meta = {**meta, "page": block.page}
        text_props.extend(extract_propositions(block.text, block_meta))

    # --- Image propositions (Haiku vision captions) ---
    image_props = caption_images(image_blocks, meta)

    all_props = text_props + image_props

    # --- Persist to DB ---
    store = PropositionStore(settings.database_url)
    await store.init()
    for prop in all_props:
        await store.save_proposition(
            text=prop["text"],
            metadata=prop["metadata"],
            image_data=prop.get("image_data"),
            image_media_type=prop.get("image_media_type"),
        )

    # --- Add to live retrieval index ---
    pipeline = get_pipeline()
    if pipeline.is_ready:
        for prop in all_props:
            pipeline.add_document(prop["text"], prop["metadata"])
        pipeline.build()  # rebuild indexes with new docs
        logger.info("Live index rebuilt after ingesting %s", filename)

    return {
        "propositions_indexed": len(text_props),
        "images_captioned": len(image_props),
        "pages": len(set(b.page for b in text_blocks)),
        "filename": filename,
    }
