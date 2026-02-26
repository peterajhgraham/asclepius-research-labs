"""
SQLAlchemy database engine and session configuration.

In development / tests, set DATABASE_URL to a SQLite URL:
    sqlite:///./asclepius.db   (file-based)
    sqlite:///:memory:         (in-memory)

In production set it to the PostgreSQL URL:
    postgresql://user:password@db:5432/asclepius
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "sqlite:///./asclepius.db",
)

# SQLite needs check_same_thread=False when used with multiple threads
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy ORM models."""


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables defined via *Base* subclasses."""
    from asclepius import db_models  # noqa: F401 – registers models with Base
    Base.metadata.create_all(bind=engine)
