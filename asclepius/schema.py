"""
Define a minimal biological data schema.

We want to represent:

Experiment
    - id
    - organism
    - assay_type
    - date
    - pipeline_version

Sample
    - id
    - experiment_id
    - perturbation
    - dose
    - timepoint

CellState
    - id
    - sample_id
    - cell_type_label
    - gene_expression_vector_reference
    - embedding_reference
    - processing_version

Use dataclasses or pydantic models.

Goal:
Create enforceable structure for biological experiments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Experiment:
    """A single biological experiment."""

    id: str
    organism: str
    assay_type: str
    date: date
    lab: str = ""
    pipeline_version: str = "1.0.0"


@dataclass
class Sample:
    """A biological sample derived from an experiment."""

    id: str
    experiment_id: str
    perturbation_type: str = ""
    perturbation_target: str = ""
    dose: Optional[float] = None
    timepoint: Optional[float] = None


@dataclass
class CellState:
    """The observed state of a single cell."""

    id: str
    sample_id: str
    raw_data_pointer: str = ""
    processed_data_pointer: str = ""
    embedding_pointer: str = ""
    annotation_label: str = ""
    processing_version: str = "1.0.0"


@dataclass
class ProcessingPipeline:
    """A versioned preprocessing pipeline."""

    id: str
    reference_genome: str
    normalization_method: str
    batch_correction_method: str = ""
    software_version: str = "1.0.0"
