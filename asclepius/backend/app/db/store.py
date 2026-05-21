"""Async SQLite store for propositions and papers.

The store carries a forward-compatible migration block: when the DB file
was created by an older schema (pre-multimodal columns), the missing
columns are added in-place via `ALTER TABLE` statements. This avoids the
need for a heavyweight migration tool (alembic) while still letting the
backend evolve safely across deploys.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_engine: Any = None
_session_factory: Any = None


_MIGRATIONS = [
    ("image_data", "TEXT"),
    ("image_media_type", "VARCHAR(32)"),
    ("content_type", "VARCHAR(16) DEFAULT 'text'"),
    ("image_hash", "VARCHAR(64)"),
    ("clip_embedding", "BLOB"),
    ("table_markdown", "TEXT"),
    ("bbox_json", "TEXT"),
]


async def _init_engine(database_url: str) -> None:
    global _engine, _session_factory
    if _engine is not None:
        return
    try:
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker

        from app.db.models import Base

        if database_url.startswith("sqlite"):
            db_path = database_url.split("///")[-1]
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        _engine = create_async_engine(database_url, echo=False)
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Column-level migration for older DBs created before this schema version.
        import sqlite3 as _sqlite3
        if database_url.startswith("sqlite"):
            db_path = database_url.split("///")[-1]
            try:
                _conn = _sqlite3.connect(db_path)
                existing = [row[1] for row in _conn.execute("PRAGMA table_info(propositions)").fetchall()]
                for col, col_type in _MIGRATIONS:
                    if col not in existing:
                        _conn.execute(f"ALTER TABLE propositions ADD COLUMN {col} {col_type}")
                        logger.info("Migrated propositions: added column %s %s", col, col_type)
                try:
                    _conn.execute("CREATE INDEX IF NOT EXISTS ix_propositions_image_hash ON propositions(image_hash)")
                    _conn.execute("CREATE INDEX IF NOT EXISTS ix_propositions_content_type ON propositions(content_type)")
                except Exception:
                    pass
                _conn.commit()
                _conn.close()
            except Exception:
                logger.debug("Schema migration step skipped", exc_info=True)

        _session_factory = sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False
        )
        logger.info("Async SQLite store initialised: %s", database_url)
    except Exception:
        logger.warning("Async DB init failed — persistence disabled", exc_info=True)


def _embedding_to_bytes(emb: Any) -> bytes | None:
    if emb is None:
        return None
    try:
        import numpy as np
        if isinstance(emb, (bytes, bytearray)):
            return bytes(emb)
        arr = np.asarray(emb, dtype=np.float32)
        return arr.tobytes()
    except Exception:
        return None


def _bytes_to_embedding(buf: bytes | None) -> Any:
    if not buf:
        return None
    try:
        import numpy as np
        return np.frombuffer(buf, dtype=np.float32).copy()
    except Exception:
        return None


class PropositionStore:
    """Async CRUD interface for the propositions table."""

    def __init__(self, database_url: str = "sqlite+aiosqlite:///./data/asclepius.db") -> None:
        self._url = database_url
        self._ready = False

    async def init(self) -> None:
        await _init_engine(self._url)
        self._ready = _engine is not None

    async def save_proposition(
        self,
        text: str,
        metadata: dict[str, Any],
        image_data: str | None = None,
        image_media_type: str | None = None,
        content_type: str = "text",
        image_hash: str | None = None,
        clip_embedding: Any = None,
        table_markdown: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> None:
        if not self._ready or _session_factory is None:
            return
        try:
            from app.db.models import Proposition

            async with _session_factory() as session:
                prop = Proposition(
                    text=text,
                    source_type=metadata.get("type") or metadata.get("source_type") or "",
                    source_id=str(metadata.get("source_id", "")),
                    metadata_json=json.dumps(metadata),
                    extraction=metadata.get("extraction", "unknown"),
                    image_data=image_data,
                    image_media_type=image_media_type,
                    content_type=content_type,
                    image_hash=image_hash,
                    clip_embedding=_embedding_to_bytes(clip_embedding),
                    table_markdown=table_markdown,
                    bbox_json=json.dumps(list(bbox)) if bbox else None,
                )
                session.add(prop)
                await session.commit()
        except Exception:
            logger.debug("Failed to persist proposition", exc_info=True)

    async def load_all_propositions(self) -> list[dict[str, Any]]:
        if not self._ready or _session_factory is None:
            return []
        try:
            from sqlalchemy import select

            from app.db.models import Proposition

            async with _session_factory() as session:
                result = await session.execute(select(Proposition))
                rows = result.scalars().all()
                return [
                    {
                        "text": r.text,
                        "metadata": r.metadata_dict,
                        "image_data": r.image_data,
                        "image_media_type": r.image_media_type,
                        "content_type": r.content_type,
                        "image_hash": r.image_hash,
                        "clip_embedding": _bytes_to_embedding(r.clip_embedding),
                        "table_markdown": r.table_markdown,
                    }
                    for r in rows
                ]
        except Exception:
            logger.warning("Failed to load propositions from DB", exc_info=True)
            return []
