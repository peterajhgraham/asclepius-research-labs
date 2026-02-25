"""
Single-cell dataset observation, preprocessing provenance, and unified schema.

This sub-package captures three public single-cell RNA-seq datasets, traces
their preprocessing steps, documents the metadata inconsistencies found across
them, and proposes a unified schema answering the question:

    "If I were a model, what structure would I wish existed?"

Sub-modules
-----------
datasets
    Catalogue of the three public datasets and their raw metadata fields.
preprocessing
    Models for preprocessing steps and an inconsistency detector.
schema
    The unified ``UnifiedCell`` schema that a downstream model would prefer.
"""

from asclepius.singlecell.datasets import (
    DatasetCatalogue,
    PublicDataset,
    PBMC3K,
    TABULA_MURIS,
    CELLXGENE_LUNG,
)
from asclepius.singlecell.preprocessing import (
    PreprocessingStep,
    PreprocessingPipeline,
    MetadataField,
    MetadataInconsistency,
    InconsistencyDetector,
)
from asclepius.singlecell.schema import (
    GeneIdFormat,
    NormalisationStrategy,
    UnifiedCell,
    UnifiedDataset,
    SchemaValidator,
)

__all__ = [
    "DatasetCatalogue",
    "PublicDataset",
    "PBMC3K",
    "TABULA_MURIS",
    "CELLXGENE_LUNG",
    "PreprocessingStep",
    "PreprocessingPipeline",
    "MetadataField",
    "MetadataInconsistency",
    "InconsistencyDetector",
    "GeneIdFormat",
    "NormalisationStrategy",
    "UnifiedCell",
    "UnifiedDataset",
    "SchemaValidator",
]
