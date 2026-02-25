"""
SQLite-backed storage for biological data objects.

Uses a simple key-value store approach: each entity type gets its own
table with a primary key and a JSON blob.  This keeps the schema stable
as models evolve, while still allowing indexed queries on common fields.

A version_log table records the content hash of every experiment snapshot,
providing a lightweight audit trail.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional

from asclepius.models.batch import Batch
from asclepius.models.ontology import OntologyTerm, OntologyNamespace
from asclepius.models.perturbation import Perturbation
from asclepius.models.rnaseq import RNASeqExperiment


_DDL = """
CREATE TABLE IF NOT EXISTS experiments (
    experiment_id   TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    data            TEXT NOT NULL   -- JSON blob
);

CREATE TABLE IF NOT EXISTS batches (
    batch_id        TEXT PRIMARY KEY,
    experiment_id   TEXT NOT NULL,
    data            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS perturbations (
    perturbation_id     TEXT PRIMARY KEY,
    perturbation_type   TEXT NOT NULL,
    data                TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ontology_terms (
    term_id     TEXT PRIMARY KEY,
    namespace   TEXT NOT NULL,
    label       TEXT NOT NULL,
    is_deprecated INTEGER NOT NULL DEFAULT 0,
    data        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS version_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id   TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    recorded_at     TEXT NOT NULL
);
"""


class Database:
    """
    Persistent store for biological data objects.

    Parameters
    ----------
    path:
        File-system path to the SQLite database file.
        Pass ``":memory:"`` for an in-memory database (useful in tests).
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._path = str(path)
        self._conn: sqlite3.Connection = sqlite3.connect(
            self._path, check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._bootstrap()

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def _bootstrap(self) -> None:
        with self._conn:
            self._conn.executescript(_DDL)

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------ #
    # Experiments                                                          #
    # ------------------------------------------------------------------ #

    def save_experiment(self, experiment: RNASeqExperiment) -> None:
        """Insert or replace an experiment and log its content hash."""
        data = json.dumps(experiment.to_dict())
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO experiments (experiment_id, name, created_at, data)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(experiment_id) DO UPDATE SET
                    name = excluded.name,
                    created_at = excluded.created_at,
                    data = excluded.data
                """,
                (
                    experiment.experiment_id,
                    experiment.name,
                    experiment.created_at.isoformat(),
                    data,
                ),
            )
            self._conn.execute(
                """
                INSERT INTO version_log (experiment_id, content_hash, recorded_at)
                VALUES (?, ?, ?)
                """,
                (
                    experiment.experiment_id,
                    experiment.content_hash(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def get_experiment(self, experiment_id: str) -> Optional[RNASeqExperiment]:
        row = self._conn.execute(
            "SELECT data FROM experiments WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchone()
        if row is None:
            return None
        return RNASeqExperiment.from_dict(json.loads(row["data"]))

    def list_experiments(self) -> List[RNASeqExperiment]:
        rows = self._conn.execute(
            "SELECT data FROM experiments ORDER BY created_at"
        ).fetchall()
        return [RNASeqExperiment.from_dict(json.loads(r["data"])) for r in rows]

    def get_version_history(self, experiment_id: str) -> List[dict]:
        """Return all recorded content hashes for an experiment, oldest first."""
        rows = self._conn.execute(
            """
            SELECT content_hash, recorded_at FROM version_log
            WHERE experiment_id = ? ORDER BY id
            """,
            (experiment_id,),
        ).fetchall()
        return [{"content_hash": r["content_hash"], "recorded_at": r["recorded_at"]} for r in rows]

    # ------------------------------------------------------------------ #
    # Batches                                                              #
    # ------------------------------------------------------------------ #

    def save_batch(self, batch: Batch) -> None:
        data = json.dumps(batch.to_dict())
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO batches (batch_id, experiment_id, data)
                VALUES (?, ?, ?)
                ON CONFLICT(batch_id) DO UPDATE SET
                    experiment_id = excluded.experiment_id,
                    data = excluded.data
                """,
                (batch.batch_id, batch.experiment_id, data),
            )

    def get_batch(self, batch_id: str) -> Optional[Batch]:
        row = self._conn.execute(
            "SELECT data FROM batches WHERE batch_id = ?", (batch_id,)
        ).fetchone()
        if row is None:
            return None
        return Batch.from_dict(json.loads(row["data"]))

    def list_batches(self, experiment_id: Optional[str] = None) -> List[Batch]:
        if experiment_id:
            rows = self._conn.execute(
                "SELECT data FROM batches WHERE experiment_id = ? ORDER BY batch_id",
                (experiment_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT data FROM batches ORDER BY batch_id"
            ).fetchall()
        return [Batch.from_dict(json.loads(r["data"])) for r in rows]

    # ------------------------------------------------------------------ #
    # Perturbations                                                        #
    # ------------------------------------------------------------------ #

    def save_perturbation(self, perturbation: Perturbation) -> None:
        data = json.dumps(perturbation.to_dict())
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO perturbations (perturbation_id, perturbation_type, data)
                VALUES (?, ?, ?)
                ON CONFLICT(perturbation_id) DO UPDATE SET
                    perturbation_type = excluded.perturbation_type,
                    data = excluded.data
                """,
                (
                    perturbation.perturbation_id,
                    perturbation.perturbation_type.value,
                    data,
                ),
            )

    def get_perturbation(self, perturbation_id: str) -> Optional[Perturbation]:
        row = self._conn.execute(
            "SELECT data FROM perturbations WHERE perturbation_id = ?",
            (perturbation_id,),
        ).fetchone()
        if row is None:
            return None
        return Perturbation.from_dict(json.loads(row["data"]))

    def list_perturbations(self) -> List[Perturbation]:
        rows = self._conn.execute(
            "SELECT data FROM perturbations ORDER BY perturbation_id"
        ).fetchall()
        return [Perturbation.from_dict(json.loads(r["data"])) for r in rows]

    # ------------------------------------------------------------------ #
    # Ontology terms                                                       #
    # ------------------------------------------------------------------ #

    def save_ontology_term(self, term: OntologyTerm) -> None:
        data = json.dumps(term.to_dict())
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO ontology_terms (term_id, namespace, label, is_deprecated, data)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(term_id) DO UPDATE SET
                    namespace = excluded.namespace,
                    label = excluded.label,
                    is_deprecated = excluded.is_deprecated,
                    data = excluded.data
                """,
                (
                    term.term_id,
                    term.namespace.value,
                    term.label,
                    int(term.is_deprecated),
                    data,
                ),
            )

    def get_ontology_term(self, term_id: str) -> Optional[OntologyTerm]:
        row = self._conn.execute(
            "SELECT data FROM ontology_terms WHERE term_id = ?", (term_id,)
        ).fetchone()
        if row is None:
            return None
        return OntologyTerm.from_dict(json.loads(row["data"]))

    def list_ontology_terms(
        self,
        namespace: Optional[OntologyNamespace] = None,
        include_deprecated: bool = True,
    ) -> List[OntologyTerm]:
        query = "SELECT data FROM ontology_terms WHERE 1=1"
        params: list = []
        if namespace:
            query += " AND namespace = ?"
            params.append(namespace.value)
        if not include_deprecated:
            query += " AND is_deprecated = 0"
        query += " ORDER BY term_id"
        rows = self._conn.execute(query, params).fetchall()
        return [OntologyTerm.from_dict(json.loads(r["data"])) for r in rows]
