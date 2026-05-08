"""PDF document parser using PyMuPDF.

Extracts text blocks and embedded images from PDF files.
Text blocks feed into the existing proposition_extractor pipeline.
Images are returned as raw bytes for Haiku vision captioning.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TextBlock:
    text: str
    page: int
    block_type: str = "text"  # "text" or "table"


@dataclass
class ImageBlock:
    image_bytes: bytes
    media_type: str  # "image/jpeg" or "image/png"
    page: int
    width: int
    height: int
    block_type: str = "image"

    def to_base64(self) -> str:
        return base64.b64encode(self.image_bytes).decode()


class DocumentParser:
    MIN_TEXT_LENGTH = 50   # ignore tiny fragments
    MIN_IMAGE_DIM = 100    # ignore tiny images (icons, bullets)
    MAX_IMAGES_PER_DOC = 20

    def parse_pdf(self, path: str | Path) -> tuple[list[TextBlock], list[ImageBlock]]:
        """Parse a PDF into text blocks and image blocks."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise RuntimeError("pymupdf is required: pip install pymupdf")

        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)

        text_blocks: list[TextBlock] = []
        image_blocks: list[ImageBlock] = []

        doc = fitz.open(str(path))
        try:
            for page_num, page in enumerate(doc):
                # Text extraction
                blocks = page.get_text("blocks")
                for block in blocks:
                    # block = (x0, y0, x1, y1, text, block_no, block_type)
                    if len(block) >= 5 and isinstance(block[4], str):
                        text = block[4].strip()
                        if len(text) >= self.MIN_TEXT_LENGTH:
                            text_blocks.append(TextBlock(text=text, page=page_num + 1))

                # Image extraction
                if len(image_blocks) < self.MAX_IMAGES_PER_DOC:
                    for img_info in page.get_images(full=True):
                        xref = img_info[0]
                        try:
                            base_image = doc.extract_image(xref)
                            w, h = base_image["width"], base_image["height"]
                            if w < self.MIN_IMAGE_DIM or h < self.MIN_IMAGE_DIM:
                                continue
                            ext = base_image["ext"].lower()
                            media_type = "image/png" if ext == "png" else "image/jpeg"
                            image_blocks.append(ImageBlock(
                                image_bytes=base_image["image"],
                                media_type=media_type,
                                page=page_num + 1,
                                width=w,
                                height=h,
                            ))
                            if len(image_blocks) >= self.MAX_IMAGES_PER_DOC:
                                break
                        except Exception:
                            logger.debug("Failed to extract image xref=%d", xref, exc_info=True)
        finally:
            doc.close()

        logger.info(
            "Parsed PDF %s: %d text blocks, %d images across %d pages",
            path.name, len(text_blocks), len(image_blocks), len(doc)
        )
        return text_blocks, image_blocks

    def parse_pdf_bytes(self, data: bytes, filename: str = "upload.pdf") -> tuple[list[TextBlock], list[ImageBlock]]:
        """Parse a PDF from raw bytes (for direct upload handling)."""
        import fitz

        text_blocks: list[TextBlock] = []
        image_blocks: list[ImageBlock] = []

        doc = fitz.open(stream=data, filetype="pdf")
        try:
            for page_num, page in enumerate(doc):
                blocks = page.get_text("blocks")
                for block in blocks:
                    if len(block) >= 5 and isinstance(block[4], str):
                        text = block[4].strip()
                        if len(text) >= self.MIN_TEXT_LENGTH:
                            text_blocks.append(TextBlock(text=text, page=page_num + 1))

                if len(image_blocks) < self.MAX_IMAGES_PER_DOC:
                    for img_info in page.get_images(full=True):
                        xref = img_info[0]
                        try:
                            base_image = doc.extract_image(xref)
                            w, h = base_image["width"], base_image["height"]
                            if w < self.MIN_IMAGE_DIM or h < self.MIN_IMAGE_DIM:
                                continue
                            ext = base_image["ext"].lower()
                            media_type = "image/png" if ext == "png" else "image/jpeg"
                            image_blocks.append(ImageBlock(
                                image_bytes=base_image["image"],
                                media_type=media_type,
                                page=page_num + 1,
                                width=w,
                                height=h,
                            ))
                            if len(image_blocks) >= self.MAX_IMAGES_PER_DOC:
                                break
                        except Exception:
                            logger.debug("Failed to extract image xref=%d", xref, exc_info=True)
        finally:
            doc.close()

        return text_blocks, image_blocks
