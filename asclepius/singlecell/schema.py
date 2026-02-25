"""
Unified single-cell schema — "what structure would a model wish existed?"

This module answers the central question of the problem statement by defining
``UnifiedCell`` and ``UnifiedDataset``, a schema that:

1. Uses stable, unambiguous identifiers everywhere (Ensembl gene IDs, ontology
   CURIEs for cell type / tissue / disease / organism / assay).
2. Separates raw counts from normalised layers so that any normalisation can
   be applied retrospectively.
3. Records provenance all the way from the sequencing run to the final
   embedding — so a model always knows where a cell came from.
4. Exposes the metadata a model needs as first-class typed fields, not as
   free-text strings buried in an ``extra_metadata`` dict.

Design rationale ("if I were a model, what structure would I wish existed?")
----------------------------------------------------------------------------
A model doing cross-dataset learning needs:

* A consistent feature space  – use Ensembl stable IDs as the var index.
  Gene symbols change; Ensembl IDs are versioned and stable.

* Unambiguous cell labels – use ontology CURIEs (CL, UBERON, MONDO/PATO,
  NCBITaxon, EFO) for every biological concept.  Free-text strings cannot
  be compared across datasets.

* Raw counts always available – normalisation choices differ; a model
  should be able to apply its own normalisation strategy.

* Provenance chain – knowing which sequencing run, library, donor, and
  preprocessing pipeline produced each cell is essential for modelling
  technical covariates (batch effects, protocol differences).

* No implicit information – every field that a model might condition on
  must be present and explicitly typed.  Nothing should need to be
  inferred from context (e.g. tissue from the project name).

* A validation layer – the schema should be machine-checkable, not just
  documentation.  ``SchemaValidator`` provides this.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ------------------------------------------------------------------ #
# Controlled vocabulary enums                                         #
# ------------------------------------------------------------------ #


class GeneIdFormat(str, Enum):
    """Canonical gene identifier format expected in the unified schema."""

    ENSEMBL_HUMAN = "ensembl_human"   # ENSG…
    ENSEMBL_MOUSE = "ensembl_mouse"   # ENSMUSG…
    ENSEMBL_OTHER = "ensembl_other"   # Any other Ensembl species


class NormalisationStrategy(str, Enum):
    """
    The normalisation applied to a data layer.

    The unified schema stores at least two layers per dataset:
    - ``RAW``        : integer UMI / read counts, never modified
    - ``LOG1P_CP10K``: log1p(counts / total_counts * 10000)
    - ``SCRAN``      : scran pooling-based normalisation (log-transformed)
    - ``PEARSON``    : analytic Pearson residuals (normalised + variance-stabilised)
    """

    RAW = "raw"
    LOG1P_CP10K = "log1p_cp10k"
    SCRAN = "scran"
    PEARSON = "pearson_residuals"


class SuspensionType(str, Enum):
    """Whether the assay measured whole cells or nuclei."""

    CELL = "cell"
    NUCLEUS = "nucleus"
    BULK = "bulk"


class Sex(str, Enum):
    """Biological sex encoded as a PATO ontology CURIE."""

    FEMALE = "PATO:0000383"
    MALE = "PATO:0000384"
    UNKNOWN = "unknown"


# ------------------------------------------------------------------ #
# Gene (variable) metadata                                            #
# ------------------------------------------------------------------ #


@dataclass
class UnifiedGene:
    """
    Metadata for a single gene in the unified feature space.

    ``feature_id`` is the primary key — always an Ensembl stable ID.
    ``feature_name`` is the HGNC / MGI symbol, present for human readability
    but never used as a join key.
    """

    feature_id: str                         # e.g. "ENSG00000243485"
    feature_name: str                       # e.g. "MIR1302-2HG"
    gene_id_format: GeneIdFormat
    organism_ontology_term_id: str          # e.g. "NCBITaxon:9606"
    ensembl_version: str                    # e.g. "Ensembl_110"
    is_highly_variable: bool = False
    extra_metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "feature_id": self.feature_id,
            "feature_name": self.feature_name,
            "gene_id_format": self.gene_id_format.value,
            "organism_ontology_term_id": self.organism_ontology_term_id,
            "ensembl_version": self.ensembl_version,
            "is_highly_variable": self.is_highly_variable,
            "extra_metadata": self.extra_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UnifiedGene":
        data = dict(data)
        data["gene_id_format"] = GeneIdFormat(data["gene_id_format"])
        return cls(**data)


# ------------------------------------------------------------------ #
# Cell (observation) metadata                                         #
# ------------------------------------------------------------------ #


@dataclass
class UnifiedCell:
    """
    The per-cell metadata record that a model would wish existed.

    Every field is either:
    - a stable ontology CURIE (e.g. ``cell_type_ontology_term_id = "CL:0000084"``)
    - a typed scalar (e.g. ``n_counts: int``)
    - a provenance identifier linking back to the raw data

    Rationale for each field
    ------------------------
    cell_id
        Globally unique cell barcode within this dataset.
    dataset_id
        Links back to the source ``PublicDataset`` / ``UnifiedDataset``.
    donor_id
        De-identified donor.  Required for modelling donor-level effects.
    sample_id
        Library / capture identifier within a donor.  One donor may have
        multiple samples from different tissues or time points.
    organism_ontology_term_id
        NCBITaxon CURIE — never an informal string like "human".
    tissue_ontology_term_id
        UBERON CURIE — never a free-text organ name.
    cell_type_ontology_term_id
        CL CURIE — the most specific term the annotator was confident in.
    disease_ontology_term_id
        MONDO CURIE or PATO:0000461 for healthy.  Always present.
    assay_ontology_term_id
        EFO CURIE identifying the assay (10x 3' v3, Smart-seq2, …).
    sex
        PATO CURIE from ``Sex`` enum; not a free-text 'M'/'F'.
    suspension_type
        Whether the protocol measured whole cells or nuclei.
    n_counts
        Total UMI / read counts before any filtering.
    n_genes
        Number of genes detected.
    pct_counts_mito
        Mitochondrial read fraction — essential for QC provenance.
    doublet_score
        Scrublet / DoubletFinder score; None if not computed.
    batch_id
        Technical batch identifier (e.g. flow cell or plate ID).
    preprocessing_pipeline_id
        Links to the ``PreprocessingPipeline`` applied to this cell's dataset.
    extra_metadata
        Escape hatch for dataset-specific fields not yet in the schema.
    """

    cell_id: str
    dataset_id: str
    donor_id: str
    sample_id: str
    organism_ontology_term_id: str          # NCBITaxon CURIE
    tissue_ontology_term_id: str            # UBERON CURIE
    cell_type_ontology_term_id: str         # CL CURIE
    disease_ontology_term_id: str           # MONDO CURIE or PATO:0000461
    assay_ontology_term_id: str             # EFO CURIE
    sex: Sex
    suspension_type: SuspensionType
    n_counts: int
    n_genes: int
    pct_counts_mito: float
    batch_id: str
    preprocessing_pipeline_id: str
    doublet_score: Optional[float] = None
    extra_metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "cell_id": self.cell_id,
            "dataset_id": self.dataset_id,
            "donor_id": self.donor_id,
            "sample_id": self.sample_id,
            "organism_ontology_term_id": self.organism_ontology_term_id,
            "tissue_ontology_term_id": self.tissue_ontology_term_id,
            "cell_type_ontology_term_id": self.cell_type_ontology_term_id,
            "disease_ontology_term_id": self.disease_ontology_term_id,
            "assay_ontology_term_id": self.assay_ontology_term_id,
            "sex": self.sex.value,
            "suspension_type": self.suspension_type.value,
            "n_counts": self.n_counts,
            "n_genes": self.n_genes,
            "pct_counts_mito": self.pct_counts_mito,
            "batch_id": self.batch_id,
            "preprocessing_pipeline_id": self.preprocessing_pipeline_id,
            "doublet_score": self.doublet_score,
            "extra_metadata": self.extra_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UnifiedCell":
        data = dict(data)
        data["sex"] = Sex(data["sex"])
        data["suspension_type"] = SuspensionType(data["suspension_type"])
        return cls(**data)


# ------------------------------------------------------------------ #
# Dataset-level metadata                                              #
# ------------------------------------------------------------------ #


@dataclass
class DataLayer:
    """
    A named matrix layer within a dataset (e.g. raw counts, normalised values).

    Parameters
    ----------
    name:
        Layer name, e.g. ``"counts"``, ``"log1p_cp10k"``.
    normalisation:
        The normalisation strategy applied to produce this layer.
    ensembl_version:
        Ensembl annotation version used for alignment.
    genome_assembly:
        Reference genome assembly, e.g. ``"GRCh38"``.
    notes:
        Any additional provenance notes.
    """

    name: str
    normalisation: NormalisationStrategy
    ensembl_version: str
    genome_assembly: str
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "normalisation": self.normalisation.value,
            "ensembl_version": self.ensembl_version,
            "genome_assembly": self.genome_assembly,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DataLayer":
        data = dict(data)
        data["normalisation"] = NormalisationStrategy(data["normalisation"])
        return cls(**data)


@dataclass
class UnifiedDataset:
    """
    A dataset expressed in the unified schema.

    A ``UnifiedDataset`` is the container that a model would wish to receive.
    It holds:
    - ``cells``: list of ``UnifiedCell`` records (obs metadata)
    - ``genes``: list of ``UnifiedGene`` records (var metadata)
    - ``layers``: list of ``DataLayer`` descriptors explaining what matrices
      are available (the actual matrices are not stored here — this is a
      metadata model)
    - Dataset-level ontology terms and provenance fields
    """

    dataset_id: str
    title: str
    source_accession: str
    layers: List[DataLayer] = field(default_factory=list)
    cells: List[UnifiedCell] = field(default_factory=list)
    genes: List[UnifiedGene] = field(default_factory=list)
    extra_metadata: Dict[str, str] = field(default_factory=dict)

    def add_cell(self, cell: UnifiedCell) -> None:
        self.cells.append(cell)

    def add_gene(self, gene: UnifiedGene) -> None:
        self.genes.append(gene)

    def n_cells(self) -> int:
        return len(self.cells)

    def n_genes(self) -> int:
        return len(self.genes)

    def layer_names(self) -> List[str]:
        return [la.name for la in self.layers]

    def to_dict(self) -> dict:
        return {
            "dataset_id": self.dataset_id,
            "title": self.title,
            "source_accession": self.source_accession,
            "layers": [la.to_dict() for la in self.layers],
            "cells": [c.to_dict() for c in self.cells],
            "genes": [g.to_dict() for g in self.genes],
            "extra_metadata": self.extra_metadata,
        }


# ------------------------------------------------------------------ #
# Schema validator                                                    #
# ------------------------------------------------------------------ #


@dataclass
class ValidationError:
    """A single schema validation error."""

    field: str
    message: str
    cell_id: Optional[str] = None

    def __str__(self) -> str:
        prefix = f"[cell={self.cell_id}] " if self.cell_id else ""
        return f"{prefix}{self.field}: {self.message}"


class SchemaValidator:
    """
    Validates ``UnifiedCell`` records against the unified schema rules.

    Rules enforced
    --------------
    - ``organism_ontology_term_id`` must start with ``"NCBITaxon:"``
    - ``tissue_ontology_term_id`` must start with ``"UBERON:"``
    - ``cell_type_ontology_term_id`` must start with ``"CL:"``
    - ``disease_ontology_term_id`` must start with ``"MONDO:"``, ``"PATO:"``
    - ``assay_ontology_term_id`` must start with ``"EFO:"``
    - ``n_counts`` must be a non-negative integer
    - ``n_genes`` must be a non-negative integer
    - ``pct_counts_mito`` must be between 0.0 and 100.0
    - ``doublet_score``, if present, must be between 0.0 and 1.0
    """

    _CURIE_PREFIXES: Dict[str, List[str]] = {
        "organism_ontology_term_id": ["NCBITaxon:"],
        "tissue_ontology_term_id": ["UBERON:"],
        "cell_type_ontology_term_id": ["CL:"],
        "disease_ontology_term_id": ["MONDO:", "PATO:"],
        "assay_ontology_term_id": ["EFO:"],
    }

    def validate_cell(self, cell: UnifiedCell) -> List[ValidationError]:
        """Return a list of validation errors for a single cell.  Empty = valid."""
        errors: List[ValidationError] = []

        # CURIE prefix checks
        for field_name, allowed_prefixes in self._CURIE_PREFIXES.items():
            value: str = getattr(cell, field_name)
            if not any(value.startswith(p) for p in allowed_prefixes):
                errors.append(
                    ValidationError(
                        field=field_name,
                        message=(
                            f"Expected one of prefixes {allowed_prefixes}, "
                            f"got '{value}'"
                        ),
                        cell_id=cell.cell_id,
                    )
                )

        # Numeric range checks
        if cell.n_counts < 0:
            errors.append(ValidationError("n_counts", "Must be >= 0", cell.cell_id))
        if cell.n_genes < 0:
            errors.append(ValidationError("n_genes", "Must be >= 0", cell.cell_id))
        if not (0.0 <= cell.pct_counts_mito <= 100.0):
            errors.append(
                ValidationError(
                    "pct_counts_mito",
                    f"Must be in [0, 100], got {cell.pct_counts_mito}",
                    cell.cell_id,
                )
            )
        if cell.doublet_score is not None and not (0.0 <= cell.doublet_score <= 1.0):
            errors.append(
                ValidationError(
                    "doublet_score",
                    f"Must be in [0, 1] if provided, got {cell.doublet_score}",
                    cell.cell_id,
                )
            )

        return errors

    def validate_dataset(self, dataset: UnifiedDataset) -> List[ValidationError]:
        """Return all validation errors across every cell in a dataset."""
        errors: List[ValidationError] = []

        # Require at least a raw counts layer
        layer_norms = {la.normalisation for la in dataset.layers}
        if NormalisationStrategy.RAW not in layer_norms:
            errors.append(
                ValidationError(
                    "layers",
                    "Dataset must include a 'raw' (RAW) counts layer.",
                )
            )

        for cell in dataset.cells:
            errors.extend(self.validate_cell(cell))

        return errors

    def is_valid_cell(self, cell: UnifiedCell) -> bool:
        """Return True if the cell passes all validation rules."""
        return len(self.validate_cell(cell)) == 0

    def is_valid_dataset(self, dataset: UnifiedDataset) -> bool:
        """Return True if the dataset and all its cells pass validation."""
        return len(self.validate_dataset(dataset)) == 0
