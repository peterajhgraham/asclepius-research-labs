"""
SQLAlchemy ORM models for Asclepius v0.

Entities
--------
Experiment    – top-level container for a biological experiment
Sample        – a sample within an experiment
File          – raw or processed file associated with a sample
Pipeline      – a versioned preprocessing pipeline
Dataset       – a versioned processed dataset (forms a version tree)
OntologyTerm  – lookup table mapping raw terms to normalised equivalents
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import relationship

from asclepius.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Experiment(Base):
    """Top-level container for a biological experiment."""

    __tablename__ = "experiments"
    __allow_unmapped__ = True

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(Text)
    organism = Column(String)
    assay_type = Column(String)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    samples = relationship("Sample", back_populates="experiment")
    datasets = relationship("Dataset", back_populates="experiment")


class Sample(Base):
    """A biological sample within an experiment."""

    __tablename__ = "samples"
    __allow_unmapped__ = True

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    experiment_id = Column(Uuid, ForeignKey("experiments.id"), nullable=False)
    cell_type = Column(String)
    condition = Column(String)
    replicate = Column(String)
    batch_id = Column(String)
    metadata_ = Column("metadata", JSON)

    experiment = relationship("Experiment", back_populates="samples")
    files = relationship("File", back_populates="sample")


class File(Base):
    """A raw or processed file linked to a sample."""

    __tablename__ = "files"
    __allow_unmapped__ = True

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    sample_id = Column(Uuid, ForeignKey("samples.id"), nullable=False)
    file_type = Column(String)
    file_path = Column(String)
    checksum = Column(String)
    pipeline_version = Column(String)

    sample = relationship("Sample", back_populates="files")


class Pipeline(Base):
    """A versioned preprocessing pipeline identified by its git commit hash."""

    __tablename__ = "pipelines"
    __allow_unmapped__ = True

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    git_commit_hash = Column(String)
    parameters = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    datasets = relationship("Dataset", back_populates="pipeline")


class Dataset(Base):
    """
    A versioned processed dataset.

    ``parent_dataset_id`` creates a version-tree so that every reprocessing
    step is traceable back to the original ingestion.
    """

    __tablename__ = "datasets"
    __allow_unmapped__ = True

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    experiment_id = Column(Uuid, ForeignKey("experiments.id"), nullable=False)
    pipeline_id = Column(Uuid, ForeignKey("pipelines.id"), nullable=False)
    parent_dataset_id = Column(
        Uuid, ForeignKey("datasets.id"), nullable=True
    )
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    experiment = relationship("Experiment", back_populates="datasets")
    pipeline = relationship("Pipeline", back_populates="datasets")
    parent = relationship(
        "Dataset", remote_side="Dataset.id", back_populates="children", foreign_keys="[Dataset.parent_dataset_id]"
    )
    children = relationship("Dataset", back_populates="parent", foreign_keys="[Dataset.parent_dataset_id]")


class OntologyTerm(Base):
    """
    Lookup table mapping raw biological terms to canonical ontology terms.

    Example rows:
        raw_term="T cell"   → normalized_term="CL:0000084"  namespace="cell_type"
        raw_term="human"    → normalized_term="NCBITaxon:9606" namespace="organism"
    """

    __tablename__ = "ontology_terms"
    __allow_unmapped__ = True

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    raw_term = Column(String, nullable=False)
    normalized_term = Column(String, nullable=False)
    namespace = Column(String)
