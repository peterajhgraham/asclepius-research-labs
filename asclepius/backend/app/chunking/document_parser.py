"""PDF document parser — extracts text, embedded images, and tables.

The parser produces three complementary streams of content from a PDF:

  - `TextBlock`s carry paragraph-level text with the page number. A
    layout-aware chunker downstream packs them into semantically coherent
    chunks; we deliberately do not chunk here so a higher-level chunker
    can see whole-page context.
  - `ImageBlock`s carry embedded raster images that survive PDF
    decompression filters PyMuPDF supports (FlateDecode, DCTDecode, JPX).
    Tiny images (icons, bullets, gradient artefacts) are filtered out by
    dimension. We also dedupe images by content hash so the same logo
    appearing on every page only embeds once.
  - `TableBlock`s carry reconstructed tables (markdown + raw rows) — see
    `table_extractor` for the pdfplumber-based detector.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TextBlock:
    text: str
    page: int
    block_type: str = "text"


@dataclass
class ImageBlock:
    image_bytes: bytes
    media_type: str
    page: int
    width: int
    height: int
    block_type: str = "image"
    sha256: str = ""

    def __post_init__(self) -> None:
        if not self.sha256:
            self.sha256 = hashlib.sha256(self.image_bytes).hexdigest()

    def to_base64(self) -> str:
        return base64.b64encode(self.image_bytes).decode()


class DocumentParser:
    MIN_TEXT_LENGTH = 30
    MIN_IMAGE_DIM = 120
    MIN_IMAGE_BYTES = 4_000  # skip mostly-blank thumbnails
    MAX_IMAGES_PER_DOC = 32

    def parse_pdf(self, path: str | Path) -> tuple[list[TextBlock], list[ImageBlock]]:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)
        return self.parse_pdf_bytes(path.read_bytes(), filename=path.name)

    def parse_pdf_bytes(
        self, data: bytes, filename: str = "upload.pdf"
    ) -> tuple[list[TextBlock], list[ImageBlock]]:
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise RuntimeError("pymupdf is required: pip install pymupdf")

        text_blocks: list[TextBlock] = []
        image_blocks: list[ImageBlock] = []
        seen_hashes: set[str] = set()

        doc = fitz.open(stream=data, filetype="pdf")
        try:
            page_count = len(doc)
            for page_num, page in enumerate(doc):
                # --- Text (reading-order blocks) ---
                blocks = page.get_text("blocks") or []
                # PyMuPDF returns blocks unsorted; sort by (y, x) for reading order
                blocks_sorted = sorted(
                    [b for b in blocks if len(b) >= 5 and isinstance(b[4], str)],
                    key=lambda b: (round(b[1], 1), round(b[0], 1)),
                )
                for block in blocks_sorted:
                    text = block[4].strip()
                    if len(text) >= self.MIN_TEXT_LENGTH:
                        text_blocks.append(TextBlock(text=text, page=page_num + 1))

                # --- Embedded images ---
                if len(image_blocks) >= self.MAX_IMAGES_PER_DOC:
                    continue
                for img_info in page.get_images(full=True):
                    xref = img_info[0]
                    try:
                        base_image = doc.extract_image(xref)
                    except Exception:
                        logger.debug("Failed extract_image xref=%d", xref, exc_info=True)
                        continue
                    w, h = base_image.get("width", 0), base_image.get("height", 0)
                    if w < self.MIN_IMAGE_DIM or h < self.MIN_IMAGE_DIM:
                        continue
                    img_bytes = base_image.get("image", b"")
                    if len(img_bytes) < self.MIN_IMAGE_BYTES:
                        continue
                    digest = hashlib.sha256(img_bytes).hexdigest()
                    if digest in seen_hashes:
                        continue
                    seen_hashes.add(digest)
                    ext = (base_image.get("ext") or "").lower()
                    media_type = "image/png" if ext == "png" else "image/jpeg"
                    image_blocks.append(ImageBlock(
                        image_bytes=img_bytes,
                        media_type=media_type,
                        page=page_num + 1,
                        width=w,
                        height=h,
                        sha256=digest,
                    ))
                    if len(image_blocks) >= self.MAX_IMAGES_PER_DOC:
                        break
        finally:
            doc.close()

        logger.info(
            "Parsed %s: %d text blocks, %d unique images over %d pages",
            filename, len(text_blocks), len(image_blocks), page_count,
        )
        return text_blocks, image_blocks

    def render_page(self, data: bytes, page: int, zoom: float = 1.5) -> tuple[bytes, str] | None:
        """Rasterize a whole page to PNG — useful as fallback figure context."""
        try:
            import fitz
        except ImportError:
            return None
        try:
            doc = fitz.open(stream=data, filetype="pdf")
            try:
                if page - 1 >= len(doc):
                    return None
                pix = doc[page - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                return pix.tobytes("png"), "image/png"
            finally:
                doc.close()
        except Exception:
            return None
