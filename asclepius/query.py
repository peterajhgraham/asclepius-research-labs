"""
Cross-experiment query engine.

All query functions accept an open SQLAlchemy ``Session`` and return ORM
objects.  Results can be serialised to plain dicts via the helper
``to_dict`` or converted to a DataFrame in the calling layer.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from asclepius.db_models import Dataset, Experiment, Sample


# ---------------------------------------------------------------------------
# Sample queries
# ---------------------------------------------------------------------------


def query_samples(
    session: Session,
    cell_type: Optional[str] = None,
    condition: Optional[str] = None,
    assay_type: Optional[str] = None,
    organism: Optional[str] = None,
) -> list[Sample]:
    """
    Query samples across all experiments with optional filters.

    Parameters
    ----------
    session : Session
    cell_type : str, optional
        Exact match on ``Sample.cell_type``.
    condition : str, optional
        Exact match on ``Sample.condition``.
    assay_type : str, optional
        Exact match on ``Experiment.assay_type``.
    organism : str, optional
        Exact match on ``Experiment.organism``.

    Returns
    -------
    list[Sample]
    """
    q = session.query(Sample).join(Experiment)

    if cell_type is not None:
        q = q.filter(Sample.cell_type == cell_type)
    if condition is not None:
        q = q.filter(Sample.condition == condition)
    if assay_type is not None:
        q = q.filter(Experiment.assay_type == assay_type)
    if organism is not None:
        q = q.filter(Experiment.organism == organism)

    return q.all()


# ---------------------------------------------------------------------------
# Dataset / lineage queries
# ---------------------------------------------------------------------------


def get_lineage(session: Session, dataset_id: UUID | str) -> list[UUID]:
    """
    Return the full ancestor chain for a dataset, oldest first.

    Traverses ``Dataset.parent_dataset_id`` pointers back to the root
    and returns the ordered list of dataset UUIDs.

    Parameters
    ----------
    session : Session
    dataset_id : UUID or str

    Returns
    -------
    list of UUID
    """
    lineage: list[UUID] = []
    current = session.get(Dataset, dataset_id)
    while current is not None:
        lineage.append(current.id)
        current = current.parent
    lineage.reverse()
    return lineage


def query_datasets(
    session: Session,
    experiment_id: Optional[UUID | str] = None,
    pipeline_id: Optional[UUID | str] = None,
) -> list[Dataset]:
    """
    Return datasets with optional filters.

    Parameters
    ----------
    session : Session
    experiment_id : UUID or str, optional
    pipeline_id : UUID or str, optional

    Returns
    -------
    list[Dataset]
    """
    q = session.query(Dataset)
    if experiment_id is not None:
        q = q.filter(Dataset.experiment_id == experiment_id)
    if pipeline_id is not None:
        q = q.filter(Dataset.pipeline_id == pipeline_id)
    return q.all()
