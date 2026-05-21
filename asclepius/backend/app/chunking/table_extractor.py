"""Table extraction from PDFs using pdfplumber.

Tables are notoriously hard to recover from PDF text streams: rows get
flattened, columns merge, headers are lost. `pdfplumber` walks the page's
line/character primitives and reconstructs cell grids, which is far more
reliable than `page.get_text()` heuristics. We convert each detected table
to two artifacts:

  1. A markdown rendering — small, embedding-friendly, and trivial to
     re-render in the UI.
  2. A bounding box — so the page raster can be cropped for the LLM to see
     the actual visual layout when retrieved.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TableBlock:
    page: int
    markdown: str
    rows: list[list[str]] = field(default_factory=list)
    bbox: Optional[tuple[float, float, float, float]] = None  # (x0, top, x1, bottom)
    block_type: str = "table"

    @property
    def n_rows(self) -> int:
        return len(self.rows)

    @property
    def n_cols(self) -> int:
        return max((len(r) for r in self.rows), default=0)


def _rows_to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    normalized = [[(c or "").strip().replace("|", "\\|").replace("\n", " ") for c in r] + [""] * (width - len(r)) for r in rows]
    header, *body = normalized
    if not any(c for c in header):
        header = [f"col{i+1}" for i in range(width)]
        body = normalized
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * width) + " |"]
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def extract_tables(pdf_bytes: bytes, max_tables: int = 20) -> list[TableBlock]:
    """Extract tables from PDF bytes. Returns [] if pdfplumber is missing or broken.

    We catch BaseException because pdfplumber's transitive imports (pdfminer →
    cryptography pyo3 bindings) can panic with non-Exception types on some
    Linux environments — and we never want table extraction to take down
    the rest of the ingestion pipeline.
    """
    try:
        import pdfplumber  # type: ignore[import-untyped]
    except BaseException:
        logger.warning("pdfplumber unavailable — skipping table extraction", exc_info=True)
        return []

    import io

    tables: list[TableBlock] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as doc:
            for page_idx, page in enumerate(doc.pages):
                try:
                    found = page.find_tables()
                except Exception:
                    found = []
                for t in found:
                    if len(tables) >= max_tables:
                        break
                    try:
                        rows = t.extract() or []
                    except Exception:
                        continue
                    # Filter trivial tables (< 2 rows or < 2 cols)
                    clean_rows = [[(c or "") for c in r] for r in rows if any((c or "").strip() for c in r)]
                    if len(clean_rows) < 2 or max(len(r) for r in clean_rows) < 2:
                        continue
                    md = _rows_to_markdown(clean_rows)
                    if len(md) < 30:
                        continue
                    bbox = tuple(t.bbox) if getattr(t, "bbox", None) else None
                    tables.append(TableBlock(
                        page=page_idx + 1,
                        markdown=md,
                        rows=clean_rows,
                        bbox=bbox,  # type: ignore[arg-type]
                    ))
                if len(tables) >= max_tables:
                    break
    except Exception:
        logger.warning("Table extraction failed", exc_info=True)
    logger.info("Extracted %d tables from PDF", len(tables))
    return tables


def render_table_image(pdf_bytes: bytes, page: int, bbox: tuple[float, float, float, float]) -> tuple[bytes, str] | None:
    """Render the bounding box of a table on its source page to a PNG byte string.

    Uses PyMuPDF for rasterization (already a dependency) so the LLM can see
    the visual table layout — useful when the table contains numerical
    cell color/highlight semantics that markdown cannot convey.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            if page - 1 >= len(doc):
                return None
            p = doc[page - 1]
            # pdfplumber bbox uses top-left origin, PyMuPDF uses the same here
            clip = fitz.Rect(*bbox)
            # 2x zoom for legible render
            mat = fitz.Matrix(2.0, 2.0)
            pix = p.get_pixmap(matrix=mat, clip=clip, alpha=False)
            return pix.tobytes("png"), "image/png"
        finally:
            doc.close()
    except Exception:
        logger.debug("Table raster failed for page %d", page, exc_info=True)
        return None
