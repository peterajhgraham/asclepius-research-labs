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

Supported formats:
- CSV (dense matrix)
- 10x Genomics MTX directory (barcodes.tsv.gz, features.tsv.gz, matrix.mtx.gz)
- 10x Genomics HDF5 (.h5)

Focus on clarity over optimization.
"""

from __future__ import annotations

import csv
import gzip
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


def load_10x_mtx(directory_path: str | Path) -> ExpressionMatrix:
    """
    Load a 10x Genomics feature-barcode matrix from a directory.

    Expects the directory to contain:
      - barcodes.tsv or barcodes.tsv.gz
      - features.tsv or features.tsv.gz
      - matrix.mtx or matrix.mtx.gz

    The matrix is stored genes × cells (rows × columns) in MTX format and is
    transposed to cells × genes in the returned ExpressionMatrix.

    .. note::
        The counts are stored as a dense ``List[List[float]]``.  For datasets
        with many cells or genes this can require significant memory (cells ×
        genes × 8 bytes).  The 3k PBMC dataset (≈ 2 752 cells × 54 950 genes)
        uses roughly 1.2 GB in this representation.

    Parameters
    ----------
    directory_path : str or Path

    Returns
    -------
    ExpressionMatrix
    """
    try:
        import scipy.io
    except ImportError as exc:
        raise ImportError("scipy is required for MTX loading: pip install scipy") from exc

    directory = Path(directory_path)

    def _open_tsv(stem: str):
        gz = directory / (stem + ".gz")
        plain = directory / stem
        if gz.exists():
            return gzip.open(gz, "rt")
        if plain.exists():
            return open(plain, "r", encoding="utf-8")
        raise FileNotFoundError(f"Neither {gz} nor {plain} exists")

    with _open_tsv("barcodes.tsv") as fh:
        barcodes = [line.strip() for line in fh if line.strip()]

    with _open_tsv("features.tsv") as fh:
        gene_ids = [line.strip().split("\t")[0] for line in fh if line.strip()]

    mtx_gz = directory / "matrix.mtx.gz"
    mtx_plain = directory / "matrix.mtx"
    if mtx_gz.exists():
        with gzip.open(mtx_gz, "rb") as fh:
            mat = scipy.io.mmread(fh)
    elif mtx_plain.exists():
        mat = scipy.io.mmread(str(mtx_plain))
    else:
        raise FileNotFoundError(f"matrix.mtx not found in {directory}")

    # MTX is genes × cells; transpose to cells × genes
    counts = mat.T.toarray().tolist()

    return ExpressionMatrix(
        cell_ids=barcodes,
        gene_ids=gene_ids,
        counts=counts,
        source_path=str(directory),
    )


def load_10x_h5(h5_path: str | Path) -> ExpressionMatrix:
    """
    Load a 10x Genomics feature-barcode matrix from an HDF5 file.

    The file must follow the CellRanger HDF5 convention where the sparse
    matrix is stored under the ``matrix`` group.

    .. note::
        The counts are stored as a dense ``List[List[float]]``.  For datasets
        with many cells or genes this can require significant memory (cells ×
        genes × 8 bytes).  The 3k PBMC dataset (≈ 2 752 cells × 54 950 genes)
        uses roughly 1.2 GB in this representation.

    Parameters
    ----------
    h5_path : str or Path

    Returns
    -------
    ExpressionMatrix
    """
    try:
        import h5py
        import scipy.sparse
    except ImportError as exc:
        raise ImportError("h5py and scipy are required for HDF5 loading: pip install h5py scipy") from exc

    path = Path(h5_path)
    with h5py.File(path, "r") as f:
        grp = f["matrix"]
        barcodes = [b.decode("utf-8") if isinstance(b, bytes) else b for b in grp["barcodes"][:]]
        gene_ids = [g.decode("utf-8") if isinstance(g, bytes) else g for g in grp["features"]["id"][:]]
        data = grp["data"][:]
        indices = grp["indices"][:]
        indptr = grp["indptr"][:]
        shape = tuple(grp["shape"][:])

    # CellRanger stores the matrix as genes × cells (CSC); transpose to cells × genes
    mat = scipy.sparse.csc_matrix((data, indices, indptr), shape=shape)
    counts = mat.T.toarray().tolist()

    return ExpressionMatrix(
        cell_ids=barcodes,
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
