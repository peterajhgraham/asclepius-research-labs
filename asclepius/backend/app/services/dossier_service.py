"""Disease dossier / paper context memory service.

Provides SQLite-backed storage for user research sessions:
- Save and retrieve queries with structured results
- Build disease-specific dossiers that accumulate insights
- Attach notes to queries and dossiers
- Export dossiers as structured JSON
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)


class _PGCursorAdapter:
    """Wraps a psycopg2 RealDictCursor to match sqlite3's execute-returns-cursor API."""

    def __init__(self, cur: Any) -> None:
        self._cur = cur

    def execute(self, sql: str, params: tuple = ()) -> "_PGCursorAdapter":
        self._cur.execute(sql.replace("?", "%s"), params)
        return self

    def fetchone(self) -> Optional[Dict[str, Any]]:
        return self._cur.fetchone()

    def fetchall(self) -> List[Dict[str, Any]]:
        return self._cur.fetchall()

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount


class DossierEntry:
    """A single entry in a disease dossier (one query + result + notes)."""

    def __init__(
        self,
        query: str,
        response: Dict[str, Any],
        notes: str = "",
    ) -> None:
        self.id = str(uuid.uuid4())
        self.query = query
        self.response = response
        self.notes = notes
        self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "query": self.query,
            "response": self.response,
            "notes": self.notes,
            "created_at": self.created_at,
        }


class Dossier:
    """A disease dossier that accumulates structured research insights."""

    def __init__(
        self,
        name: str,
        description: str = "",
    ) -> None:
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.entries: List[DossierEntry] = []
        self.tags: List[str] = []
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at

    def add_entry(
        self,
        query: str,
        response: Dict[str, Any],
        notes: str = "",
    ) -> DossierEntry:
        entry = DossierEntry(query=query, response=response, notes=notes)
        self.entries.append(entry)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return entry

    def update_entry_notes(self, entry_id: str, notes: str) -> bool:
        for entry in self.entries:
            if entry.id == entry_id:
                entry.notes = notes
                self.updated_at = datetime.now(timezone.utc).isoformat()
                return True
        return False

    def remove_entry(self, entry_id: str) -> bool:
        for i, entry in enumerate(self.entries):
            if entry.id == entry_id:
                self.entries.pop(i)
                self.updated_at = datetime.now(timezone.utc).isoformat()
                return True
        return False

    def get_accumulated_insights(self) -> Dict[str, Any]:
        """Aggregate structured reasoning across all entries."""
        all_entities: List[str] = []
        all_mechanisms: List[str] = []
        all_pathways: List[str] = []
        all_targets: List[str] = []
        all_genes: List[str] = []
        all_hypotheses: List[str] = []
        all_sources: List[str] = []
        queries: List[str] = []

        for entry in self.entries:
            queries.append(entry.query)
            resp = entry.response
            reasoning = resp.get("reasoning", {})
            all_entities.extend(reasoning.get("key_entities", []))
            all_mechanisms.extend(reasoning.get("key_mechanisms", []))
            all_pathways.extend(reasoning.get("pathways", []))
            all_targets.extend(reasoning.get("therapeutic_targets", []))
            all_genes.extend(reasoning.get("genes", []))
            all_hypotheses.extend(reasoning.get("open_questions", []))
            all_sources.extend(resp.get("sources", []))

        return {
            "total_queries": len(self.entries),
            "queries": queries,
            "key_entities": _dedupe(all_entities),
            "key_mechanisms": _dedupe(all_mechanisms),
            "pathways": _dedupe(all_pathways),
            "therapeutic_targets": _dedupe(all_targets),
            "genes": _dedupe(all_genes),
            "hypotheses": _dedupe(all_hypotheses),
            "sources": _dedupe(all_sources),
            "notes": [
                {"entry_id": e.id, "query": e.query, "notes": e.notes}
                for e in self.entries if e.notes
            ],
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "entry_count": len(self.entries),
            "entries": [e.to_dict() for e in self.entries],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_summary(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "entry_count": len(self.entries),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class DossierStore:
    """SQLite-backed store for disease dossiers."""

    def __init__(self) -> None:
        _default = str(Path(__file__).parents[2] / "data" / "asclepius.db")
        db_url = f"sqlite:///{_default}"
        try:
            from app.core.config import settings
            db_url = settings.database_url
        except Exception:
            pass
        self._is_postgres = db_url.startswith(("postgresql://", "postgres://"))
        if self._is_postgres:
            self._pg_url = db_url
            try:
                from psycopg2 import pool as _pg_pool
                self._pg_pool = _pg_pool.ThreadedConnectionPool(1, 10, self._pg_url)
            except ImportError:
                logger.error("psycopg2 not installed — cannot use PostgreSQL DATABASE_URL. Install psycopg2-binary.")
                raise RuntimeError("psycopg2 required for PostgreSQL but not installed") from None
            except Exception as exc:
                logger.error("Failed to connect to PostgreSQL: %s", exc)
                raise
        else:
            raw = db_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
            self._db_path = raw
            import os
            db_path = db_url.replace("sqlite:///", "").replace("sqlite+aiosqlite:///", "")
            if db_path and not db_path.startswith(":"):  # not in-memory
                os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_db()

    @contextmanager
    def _cursor(self) -> Generator:
        if self._is_postgres:
            import psycopg2.extras
            conn = self._pg_pool.getconn()
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    yield _PGCursorAdapter(cur)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                self._pg_pool.putconn(conn)
        else:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self._db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init_db(self) -> None:
        try:
            with self._cursor() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS dossiers (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        tags_json TEXT NOT NULL DEFAULT '[]',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS dossier_entries (
                        id TEXT PRIMARY KEY,
                        dossier_id TEXT NOT NULL REFERENCES dossiers(id) ON DELETE CASCADE,
                        query TEXT NOT NULL,
                        response_json TEXT NOT NULL DEFAULT '{}',
                        notes TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS ix_dossier_entries_dossier_id "
                    "ON dossier_entries(dossier_id)"
                )
        except Exception:
            logger.warning("Dossier DB init failed", exc_info=True)

    def _row_to_dossier(self, row: Any, entries: List[DossierEntry]) -> Dossier:
        d = Dossier.__new__(Dossier)
        d.id = row["id"]
        d.name = row["name"]
        d.description = row["description"]
        d.tags = json.loads(row["tags_json"])
        d.entries = entries
        d.created_at = row["created_at"]
        d.updated_at = row["updated_at"]
        return d

    def _row_to_entry(self, row: Any) -> DossierEntry:
        e = DossierEntry.__new__(DossierEntry)
        e.id = row["id"]
        e.query = row["query"]
        e.response = json.loads(row["response_json"])
        e.notes = row["notes"]
        e.created_at = row["created_at"]
        return e

    def create_dossier(
        self,
        name: str,
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> Dossier:
        dossier = Dossier(name=name, description=description)
        if tags:
            dossier.tags = tags
        with self._cursor() as conn:
            conn.execute(
                "INSERT INTO dossiers (id, name, description, tags_json, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?)",
                (
                    dossier.id,
                    dossier.name,
                    dossier.description,
                    json.dumps(dossier.tags),
                    dossier.created_at,
                    dossier.updated_at,
                ),
            )
        logger.info("Created dossier: %s (%s)", name, dossier.id)
        return dossier

    def get_dossier(self, dossier_id: str) -> Optional[Dossier]:
        try:
            with self._cursor() as conn:
                row = conn.execute(
                    "SELECT * FROM dossiers WHERE id=?", (dossier_id,)
                ).fetchone()
                if not row:
                    return None
                entry_rows = conn.execute(
                    "SELECT * FROM dossier_entries WHERE dossier_id=? ORDER BY created_at",
                    (dossier_id,),
                ).fetchall()
                entries = [self._row_to_entry(r) for r in entry_rows]
                return self._row_to_dossier(row, entries)
        except Exception:
            logger.warning("Failed to load dossier %s", dossier_id, exc_info=True)
            return None

    def list_dossiers(self) -> List[Dict[str, Any]]:
        try:
            with self._cursor() as conn:
                rows = conn.execute(
                    "SELECT d.id, d.name, d.description, d.tags_json, "
                    "d.created_at, d.updated_at, COUNT(e.id) AS entry_count "
                    "FROM dossiers d "
                    "LEFT JOIN dossier_entries e ON d.id=e.dossier_id "
                    "GROUP BY d.id, d.name, d.description, d.tags_json, "
                    "d.created_at, d.updated_at "
                    "ORDER BY d.updated_at DESC"
                ).fetchall()
                return [
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "description": r["description"],
                        "tags": json.loads(r["tags_json"]),
                        "entry_count": r["entry_count"],
                        "created_at": r["created_at"],
                        "updated_at": r["updated_at"],
                    }
                    for r in rows
                ]
        except Exception:
            logger.warning("Failed to list dossiers", exc_info=True)
            return []

    def delete_dossier(self, dossier_id: str) -> bool:
        try:
            with self._cursor() as conn:
                result = conn.execute(
                    "DELETE FROM dossiers WHERE id=?", (dossier_id,)
                )
                return result.rowcount > 0
        except Exception:
            logger.warning("Failed to delete dossier %s", dossier_id, exc_info=True)
            return False

    def add_to_dossier(
        self,
        dossier_id: str,
        query: str,
        response: Dict[str, Any],
        notes: str = "",
    ) -> Optional[Dict[str, Any]]:
        try:
            with self._cursor() as conn:
                exists = conn.execute(
                    "SELECT id FROM dossiers WHERE id=?", (dossier_id,)
                ).fetchone()
                if not exists:
                    return None
                entry = DossierEntry(query=query, response=response, notes=notes)
                conn.execute(
                    "INSERT INTO dossier_entries (id, dossier_id, query, response_json, notes, created_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        entry.id,
                        dossier_id,
                        entry.query,
                        json.dumps(entry.response),
                        entry.notes,
                        entry.created_at,
                    ),
                )
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "UPDATE dossiers SET updated_at=? WHERE id=?", (now, dossier_id)
                )
                return entry.to_dict()
        except Exception:
            logger.warning("Failed to add entry to dossier %s", dossier_id, exc_info=True)
            return None

    def update_entry_notes(self, dossier_id: str, entry_id: str, notes: str) -> bool:
        try:
            with self._cursor() as conn:
                result = conn.execute(
                    "UPDATE dossier_entries SET notes=? WHERE id=? AND dossier_id=?",
                    (notes, entry_id, dossier_id),
                )
                return result.rowcount > 0
        except Exception:
            logger.warning("Failed to update entry notes %s", entry_id, exc_info=True)
            return False

    def get_insights(self, dossier_id: str) -> Optional[Dict[str, Any]]:
        dossier = self.get_dossier(dossier_id)
        if not dossier:
            return None
        return dossier.get_accumulated_insights()


def _dedupe(items: List[str]) -> List[str]:
    """Deduplicate while preserving order."""
    seen: set = set()
    result: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


# Singleton store
dossier_store = DossierStore()
