"""SQLAlchemy async models for proposition and paper storage."""

from __future__ import annotations

import json
from datetime import datetime

from typing import Optional

from sqlalchemy import DateTime, Float, Integer, LargeBinary, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Proposition(Base):
    __tablename__ = "propositions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    source_id: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    extraction: Mapped[str] = mapped_column(String(32), nullable=False, default="sliding_window")
    # Legacy: base64-encoded image payload. Retained for backward compatibility,
    # but new ingestions write to image_hash + image_store on disk instead.
    image_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    image_media_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, default=None)
    # Multimodal extensions (added 2026-05).
    content_type: Mapped[str] = mapped_column(String(16), nullable=False, default="text")  # text | image | table
    image_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None, index=True)
    clip_embedding: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True, default=None)
    table_markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    bbox_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    @property
    def metadata_dict(self) -> dict:
        try:
            return json.loads(self.metadata_json)
        except Exception:
            return {}

    @metadata_dict.setter
    def metadata_dict(self, value: dict) -> None:
        self.metadata_json = json.dumps(value)


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pmid: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    abstract: Mapped[str] = mapped_column(Text, nullable=False, default="")
    authors_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    journal: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    year: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    doi: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="pubmed")
    indexed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
