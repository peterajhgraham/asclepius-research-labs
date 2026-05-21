"""Content-addressed image store on local disk.

Images extracted from ingested PDFs (figures, table screenshots, page rasters)
are persisted as files named by their SHA-256 hash. Storing on disk rather
than as base64 blobs in SQLite keeps the database small, makes images
streamable to the frontend via a simple URL endpoint, and deduplicates
identical figures that appear in multiple documents.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_DIR = Path("./data/images")


def _ext_for(media_type: str) -> str:
    mt = (media_type or "").lower()
    if "png" in mt:
        return "png"
    if "webp" in mt:
        return "webp"
    if "gif" in mt:
        return "gif"
    return "jpg"


class ImageStore:
    """Content-addressed image filesystem store."""

    def __init__(self, root: str | Path = _DEFAULT_DIR) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, image_bytes: bytes, media_type: str = "image/jpeg") -> tuple[str, str, str]:
        """Persist `image_bytes` and return (hash, relative_path, media_type).

        Returns the existing path if the same image was already stored.
        """
        digest = hashlib.sha256(image_bytes).hexdigest()
        ext = _ext_for(media_type)
        # Shard into 2-char prefix to avoid one huge directory
        shard = self.root / digest[:2]
        shard.mkdir(parents=True, exist_ok=True)
        path = shard / f"{digest}.{ext}"
        if not path.exists():
            try:
                path.write_bytes(image_bytes)
            except OSError:
                logger.warning("Failed to write image %s", path, exc_info=True)
        return digest, str(path), media_type

    def path_for(self, image_hash: str) -> Path | None:
        """Resolve a stored image's path from its hash, scanning known extensions."""
        if not image_hash or "/" in image_hash or "\\" in image_hash:
            return None
        shard = self.root / image_hash[:2]
        if not shard.exists():
            return None
        for ext in ("jpg", "png", "webp", "gif", "jpeg"):
            candidate = shard / f"{image_hash}.{ext}"
            if candidate.exists():
                return candidate
        return None

    def read(self, image_hash: str) -> tuple[bytes, str] | None:
        """Load image bytes and media-type by hash."""
        path = self.path_for(image_hash)
        if path is None:
            return None
        suffix = path.suffix.lstrip(".").lower()
        media_type = {
            "png": "image/png",
            "webp": "image/webp",
            "gif": "image/gif",
        }.get(suffix, "image/jpeg")
        try:
            return path.read_bytes(), media_type
        except OSError:
            return None


_default_store: ImageStore | None = None


def get_image_store() -> ImageStore:
    global _default_store
    if _default_store is None:
        _default_store = ImageStore()
    return _default_store
