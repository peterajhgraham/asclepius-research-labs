"""
Pretraining / export preparation layer.

Produces aligned (samples × genes) expression matrices and associated
metadata tables that can be fed directly into downstream ML pipelines.

v0: in-memory export from files stored on the local filesystem.
Future: stream from S3-compatible object storage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from asclepius.db_models import Dataset, File, Sample
from asclepius.ingestion import ExpressionMatrix, load_expression_csv


def export_expression_matrix(
    session: Session,
    dataset_id: UUID | str,
) -> tuple[ExpressionMatrix, list[dict]]:
    """
    Export the expression matrix and aligned metadata for a dataset.

    Loads all CSV expression files linked to the dataset's samples,
    concatenates them, and returns the unified matrix together with a
    list of per-cell metadata dicts.

    Parameters
    ----------
    session : Session
    dataset_id : UUID or str

    Returns
    -------
    tuple of (ExpressionMatrix, list[dict])
        - ExpressionMatrix with rows = cells, columns = genes
        - list of metadata dicts with keys: cell_index, sample_id,
          cell_type, condition, replicate, batch_id

    Raises
    ------
    ValueError
        If no expression files are found for the dataset.
    """
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise ValueError(f"Dataset {dataset_id!r} not found.")

    # Collect all CSV expression files for this experiment's samples
    samples: list[Sample] = (
        session.query(Sample)
        .filter(Sample.experiment_id == dataset.experiment_id)
        .all()
    )

    all_cell_ids: list[str] = []
    all_counts: list[list[float]] = []
    gene_ids: list[str] = []
    metadata_rows: list[dict] = []

    for sample in samples:
        csv_files: list[File] = [
            f for f in sample.files if f.file_type == "expression_csv"
        ]
        for file_rec in csv_files:
            path = Path(file_rec.file_path)
            if not path.exists():
                continue
            mat = load_expression_csv(path)
            if not gene_ids:
                gene_ids = mat.gene_ids
            all_cell_ids.extend(mat.cell_ids)
            all_counts.extend(mat.counts)
            for cell_id in mat.cell_ids:
                metadata_rows.append(
                    {
                        "cell_id": cell_id,
                        "sample_id": str(sample.id),
                        "cell_type": sample.cell_type,
                        "condition": sample.condition,
                        "replicate": sample.replicate,
                        "batch_id": sample.batch_id,
                    }
                )

    if not all_cell_ids:
        raise ValueError(
            f"No expression CSV files found for dataset {dataset_id!r}."
        )

    matrix = ExpressionMatrix(
        cell_ids=all_cell_ids,
        gene_ids=gene_ids,
        counts=all_counts,
        source_path=f"dataset:{dataset_id}",
    )
    return matrix, metadata_rows
