"""Multimodal document ingestion.

For every ingested PDF, this service drives three parallel pipelines:

    text   →  layout-aware chunker  →  Haiku proposition extractor
              (falls back to sliding window if Haiku unavailable)

    image  →  PyMuPDF embedded-image extractor
              →  content-addressed disk store  +  CLIP image embedding
              →  Haiku-vision caption  →  atomic figure propositions

    table  →  pdfplumber detector  →  markdown + raw rows
              →  rendered PNG raster of the table region
              →  CLIP embedding of the raster (cross-modal retrieval)
              →  markdown indexed as text proposition

All propositions land in the SQLite store with their `content_type`,
`image_hash`, `clip_embedding`, and (for tables) `table_markdown`, then
get pushed into the live `RetrievalPipeline` so subsequent queries can
hit them. The pipeline is rebuilt incrementally — we never throw away
previously-indexed documents.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def ingest_document(
    pdf_bytes: bytes,
    filename: str,
    source_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from app.chunking.document_parser import DocumentParser
    from app.chunking.image_captioner import caption_images, _shared_clip
    from app.chunking.layout_chunker import chunk_blocks
    from app.chunking.proposition_extractor import extract_propositions
    from app.chunking.table_extractor import extract_tables, render_table_image
    from app.core.config import settings
    from app.db.store import PropositionStore
    from app.services.retrieval_service import get_pipeline
    from app.storage.image_store import get_image_store

    meta = {
        "source_type": "document",
        "filename": filename,
        **(source_metadata or {}),
    }

    parser = DocumentParser()
    text_blocks, image_blocks = parser.parse_pdf_bytes(pdf_bytes, filename)

    # --- Layout-aware text chunks ---
    # Group page-ordered text blocks into ~1800-char sentence-bounded chunks
    # before sending to Haiku for proposition extraction. This produces ~5-10x
    # fewer chunks than the old per-block call pattern with no loss of recall.
    layout_chunks = chunk_blocks(text_blocks, target_chars=1800, max_chars=2400)
    text_props: list[dict[str, Any]] = []
    for chunk in layout_chunks:
        chunk_meta = {**meta, "page": chunk.page, "content_type": "text"}
        text_props.extend(extract_propositions(chunk.text, chunk_meta))

    # --- Image propositions (figures, with CLIP embedding) ---
    image_props = caption_images(image_blocks, meta)

    # --- Table propositions ---
    table_props: list[dict[str, Any]] = []
    table_blocks = extract_tables(pdf_bytes)
    image_store = get_image_store()
    clip = _shared_clip()

    for table in table_blocks:
        table_meta = {
            **meta,
            "page": table.page,
            "type": "table",
            "n_rows": table.n_rows,
            "n_cols": table.n_cols,
            "table_markdown": table.markdown,
        }
        image_hash: str | None = None
        image_bytes: bytes | None = None
        clip_emb = None

        # Render the table region as a PNG so the LLM can see actual layout
        if table.bbox is not None:
            rendered = render_table_image(pdf_bytes, table.page, table.bbox)
            if rendered is not None:
                image_bytes, media_type = rendered
                image_hash, _path, _mt = image_store.save(image_bytes, media_type)
                if clip is not None:
                    clip_emb = await asyncio.to_thread(clip.encode_image, image_bytes)

        # The "text" of a table proposition is its markdown rendering — this
        # is what BM25 and the dense text encoder will index against. It also
        # gets passed to the LLM as plain markdown for grounded reasoning.
        table_text = f"Table on page {table.page} ({table.n_rows}×{table.n_cols}):\n{table.markdown}"
        table_props.append({
            "text": table_text,
            "metadata": {**table_meta, "extraction": "pdfplumber_table"},
            "content_type": "table",
            "image_hash": image_hash,
            "image_bytes": image_bytes,
            "image_media_type": "image/png" if image_hash else None,
            "clip_embedding": clip_emb,
            "table_markdown": table.markdown,
            "bbox": table.bbox,
        })

    all_props = text_props + image_props + table_props

    # --- Persist to SQLite ---
    store = PropositionStore(settings.database_url)
    await store.init()
    for prop in all_props:
        ctype = prop.get("content_type", "text")
        await store.save_proposition(
            text=prop["text"],
            metadata=prop["metadata"],
            image_data=None,  # we use disk storage now, not blob
            image_media_type=prop.get("image_media_type"),
            content_type=ctype,
            image_hash=prop.get("image_hash"),
            clip_embedding=prop.get("clip_embedding"),
            table_markdown=prop.get("table_markdown"),
            bbox=prop.get("bbox"),
        )

    # --- Stream into the live retrieval pipeline ---
    pipeline = get_pipeline()
    # If the pipeline isn't ready, the warm-up routine will load these from
    # the DB on first query. If it is, we add now and rebuild incrementally.
    if pipeline.is_ready or pipeline.doc_count > 0:
        for prop in all_props:
            pipeline.add_document(
                text=prop["text"],
                metadata=prop["metadata"],
                content_type=prop.get("content_type", "text"),
                image_hash=prop.get("image_hash"),
                image_bytes=prop.get("image_bytes"),
                clip_embedding=prop.get("clip_embedding"),
            )
        pipeline.build()
        logger.info(
            "Live index rebuilt after ingesting %s: +%d text, +%d images, +%d tables",
            filename, len(text_props), len(image_props), len(table_props),
        )

    pages = max(
        (b.page for b in text_blocks),
        default=0,
    )
    return {
        "propositions_indexed": len(text_props),
        "images_captioned": len(image_props),
        "tables_indexed": len(table_props),
        "pages": pages,
        "filename": filename,
    }
