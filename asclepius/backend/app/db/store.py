"""Async SQLite store for propositions and papers."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_engine: Any = None
_session_factory: Any = None


async def _init_engine(database_url: str) -> None:
    global _engine, _session_factory
    if _engine is not None:
        return
    try:
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker

        from app.db.models import Base

        # Ensure the data directory exists for SQLite
        if database_url.startswith("sqlite"):
            db_path = database_url.split("///")[-1]
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        _engine = create_async_engine(database_url, echo=False)
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Safe column migration — add new columns if the DB was created before this schema version
        import sqlite3 as _sqlite3
        if database_url.startswith("sqlite"):
            db_path = database_url.split("///")[-1]
            try:
                _conn = _sqlite3.connect(db_path)
                existing = [row[1] for row in _conn.execute("PRAGMA table_info(propositions)").fetchall()]
                if "image_data" not in existing:
                    _conn.execute("ALTER TABLE propositions ADD COLUMN image_data TEXT")
                if "image_media_type" not in existing:
                    _conn.execute("ALTER TABLE propositions ADD COLUMN image_media_type VARCHAR(32)")
                _conn.commit()
                _conn.close()
            except Exception:
                pass  # non-critical, table may not exist yet

        _session_factory = sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False
        )
        logger.info("Async SQLite store initialised: %s", database_url)
    except Exception:
        logger.warning("Async DB init failed — persistence disabled", exc_info=True)


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
    ) -> None:
        if not self._ready or _session_factory is None:
            return
        try:
            from app.db.models import Proposition

            async with _session_factory() as session:
                prop = Proposition(
                    text=text,
                    source_type=metadata.get("type", ""),
                    source_id=str(metadata.get("source_id", "")),
                    metadata_json=json.dumps(metadata),
                    extraction=metadata.get("extraction", "unknown"),
                    image_data=image_data,
                    image_media_type=image_media_type,
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
                    }
                    for r in rows
                ]
        except Exception:
            logger.warning("Failed to load propositions from DB", exc_info=True)
            return []
