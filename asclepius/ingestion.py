"""
Build a data ingestion module for single-cell RNA-seq datasets.

Requirements:
- Load gene expression count matrix (mtx or csv)
- Load cell metadata table
- Validate required fields:
    - cell_id
    - experiment_id
    - assay_type
    - organism
- Normalize column names to snake_case
- Return structured Python objects

Focus on clarity over optimization.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_snake_case(name: str) -> str:
    """Convert a column name to snake_case."""
    name = name.strip()
    name = re.sub(r"[\s\-]+", "_", name)
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    name = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name)
    return name.lower()


def _normalize_columns(row: Dict[str, str]) -> Dict[str, str]:
    """Return a copy of *row* with all keys converted to snake_case."""
    return {_to_snake_case(k): v for k, v in row.items()}


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {"cell_id", "experiment_id", "assay_type", "organism"}


@dataclass
class CellRecord:
    """A single cell observation with its metadata."""

    cell_id: str
    experiment_id: str
    assay_type: str
    organism: str
    extra: Dict[str, str] = field(default_factory=dict)


@dataclass
class ExpressionMatrix:
    """
    A gene expression count matrix loaded from CSV or MTX.

    Attributes
    ----------
    cell_ids : list of str
        Ordered cell identifiers (rows).
    gene_ids : list of str
        Ordered gene identifiers (columns).
    counts : list of list of float
        counts[i][j] is the count for cell i, gene j.
    source_path : str
        Original file path for provenance.
    """

    cell_ids: List[str]
    gene_ids: List[str]
    counts: List[List[float]]
    source_path: str = ""


@dataclass
class IngestionResult:
    """The structured output of a successful ingestion run."""

    cells: List[CellRecord]
    matrix: Optional[ExpressionMatrix]
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """Raised when required metadata fields are missing."""


def _validate_row(row: Dict[str, str], line_number: int) -> None:
    missing = REQUIRED_FIELDS - set(row.keys())
    if missing:
        raise ValidationError(
            f"Line {line_number}: missing required fields: {sorted(missing)}"
        )


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_metadata_csv(path: str | Path) -> List[CellRecord]:
    """
    Load cell metadata from a CSV file.

    Parameters
    ----------
    path : str or Path
        Path to a CSV file with at least the columns:
        cell_id, experiment_id, assay_type, organism.

    Returns
    -------
    list of CellRecord
    """
    path = Path(path)
    records: List[CellRecord] = []

    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for i, raw_row in enumerate(reader, start=2):  # line 1 = header
            row = _normalize_columns(raw_row)
            _validate_row(row, i)
            known = {f: row.pop(f) for f in REQUIRED_FIELDS}
            records.append(
                CellRecord(
                    cell_id=known["cell_id"],
                    experiment_id=known["experiment_id"],
                    assay_type=known["assay_type"],
                    organism=known["organism"],
                    extra=row,
                )
            )

    return records


def load_expression_csv(path: str | Path) -> ExpressionMatrix:
    """
    Load a dense gene expression matrix from a CSV file.

    The CSV is expected to have cell IDs as the first column (header: 'cell_id')
    and gene IDs as the remaining column headers.

    Parameters
    ----------
    path : str or Path

    Returns
    -------
    ExpressionMatrix
    """
    path = Path(path)
    cell_ids: List[str] = []
    gene_ids: List[str] = []
    counts: List[List[float]] = []

    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValidationError(f"Empty expression matrix: {path}")
        headers = [_to_snake_case(h) for h in reader.fieldnames]
        if not headers or headers[0] not in {"cell_id", "barcode", "obs_id"}:
            raise ValidationError(
                "First column must be 'cell_id', 'barcode', or 'obs_id'."
            )
        gene_ids = headers[1:]

        for raw_row in reader:
            row = {_to_snake_case(k): v for k, v in raw_row.items()}
            row_key = headers[0]
            cell_ids.append(row[row_key])
            counts.append([float(row.get(g, 0.0)) for g in gene_ids])

    return ExpressionMatrix(
        cell_ids=cell_ids,
        gene_ids=gene_ids,
        counts=counts,
        source_path=str(path),
    )


def ingest(
    metadata_path: str | Path,
    expression_path: Optional[str | Path] = None,
) -> IngestionResult:
    """
    High-level ingestion entry point.

    Parameters
    ----------
    metadata_path : str or Path
        Path to cell metadata CSV.
    expression_path : str or Path, optional
        Path to gene expression CSV.  If omitted, `matrix` will be None.

    Returns
    -------
    IngestionResult
    """
    warnings: List[str] = []

    cells = load_metadata_csv(metadata_path)

    matrix: Optional[ExpressionMatrix] = None
    if expression_path is not None:
        matrix = load_expression_csv(expression_path)
        # Cross-check cell IDs
        meta_ids = {c.cell_id for c in cells}
        expr_ids = set(matrix.cell_ids)
        only_meta = meta_ids - expr_ids
        only_expr = expr_ids - meta_ids
        if only_meta:
            warnings.append(
                f"{len(only_meta)} cell(s) in metadata but not in expression matrix."
            )
        if only_expr:
            warnings.append(
                f"{len(only_expr)} cell(s) in expression matrix but not in metadata."
            )

    return IngestionResult(cells=cells, matrix=matrix, warnings=warnings)
