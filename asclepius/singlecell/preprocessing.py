"""
Preprocessing step models and cross-dataset metadata inconsistency detection.

``PreprocessingStep`` records a single operation in a single-cell pipeline
(e.g. doublet detection, normalisation, dimensionality reduction) together
with its parameters and software versions.

``PreprocessingPipeline`` is an ordered list of steps applied to one dataset.

``MetadataInconsistency`` describes a single discrepancy found when comparing
two or more datasets — e.g. the same biological concept encoded differently.

``InconsistencyDetector`` inspects a ``DatasetCatalogue`` and returns all
discovered inconsistencies, grouped by category.

Observed preprocessing step sequences
--------------------------------------
PBMC 3k (Seurat v3 / scanpy tutorial)
    1. Cell Ranger alignment (GRCh38, Ensembl 93)
    2. Quality filter  — min_genes=200, max_genes=2500, pct_mito<5 %
    3. Normalise       — log1p(CP10K)  (NormalizeData in Seurat)
    4. Feature select  — top 2000 HVGs (FindVariableFeatures, vst)
    5. Scale           — zero-mean unit-variance (ScaleData)
    6. PCA             — 50 components
    7. Neighbours      — k=10, cosine metric
    8. Cluster         — Louvain, resolution=0.5
    9. Embed           — tSNE / UMAP

Tabula Muris (mixed Seurat / custom)
    1. STAR alignment (mm10, Ensembl 93) [Smart-seq2] or
       Cell Ranger (mm10) [10x]
    2. Quality filter  — min_genes=500 (Smart-seq2) or 200 (10x)
    3. Normalise       — log1p(CP10K) [separate per tissue × method]
    4. Feature select  — per-tissue HVG selection
    5. Scale
    6. PCA
    7. Cluster         — Louvain per tissue
    8. Annotation      — manual curator review

CELLxGENE Lung Atlas (Scanpy / scVI integration)
    1. STARsolo alignment (GRCh38, Ensembl 104) per study
    2. Quality filter  — min_genes=200, pct_mito<20 %, doublet score<0.25
    3. Normalise       — scran pooling-based normalisation per study
    4. Feature select  — 4000 HVGs (Scanpy highly_variable_genes, batch_key)
    5. Integration     — scVI (VAE, 30 latent dimensions)
    6. Neighbours      — on scVI latent embedding
    7. Cluster         — Leiden, resolution=1.0
    8. Embed           — UMAP on scVI latent
    9. Annotation      — automated (scANVI) + manual curation

Key differences to surface
    - Alignment reference: GRCh38/Ensembl 93 vs Ensembl 104; mm10 vs GRCh38
    - QC thresholds: pct_mito<5 % vs <20 %
    - Normalisation: log1p(CP10K) vs scran
    - Integration: none vs scVI
    - Clustering algorithm: Louvain vs Leiden
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from asclepius.singlecell.datasets import DatasetCatalogue, PublicDataset


# ------------------------------------------------------------------ #
# Preprocessing step models                                           #
# ------------------------------------------------------------------ #


class StepCategory(str, Enum):
    """High-level category of a preprocessing step."""

    ALIGNMENT = "alignment"
    QUALITY_FILTER = "quality_filter"
    DOUBLET_DETECTION = "doublet_detection"
    NORMALISATION = "normalisation"
    FEATURE_SELECTION = "feature_selection"
    SCALING = "scaling"
    DIMENSIONALITY_REDUCTION = "dimensionality_reduction"
    BATCH_INTEGRATION = "batch_integration"
    CLUSTERING = "clustering"
    EMBEDDING = "embedding"
    ANNOTATION = "annotation"


@dataclass
class PreprocessingStep:
    """
    A single step in a single-cell preprocessing pipeline.

    Parameters
    ----------
    name:
        Short human-readable name, e.g. ``"log1p normalisation"``.
    category:
        High-level category from ``StepCategory``.
    tool:
        Software tool used, e.g. ``"Seurat"``, ``"Scanpy"``, ``"scVI"``.
    tool_version:
        Version string of the tool, e.g. ``"4.3.0"``.
    parameters:
        Key-value pairs of the parameters used for this step.
    reference:
        Reference genome / annotation used (for alignment steps).
    notes:
        Free-text annotation about this step.
    """

    name: str
    category: StepCategory
    tool: str
    tool_version: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    reference: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category.value,
            "tool": self.tool,
            "tool_version": self.tool_version,
            "parameters": self.parameters,
            "reference": self.reference,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PreprocessingStep":
        data = dict(data)
        data["category"] = StepCategory(data["category"])
        return cls(**data)


@dataclass
class PreprocessingPipeline:
    """
    An ordered sequence of preprocessing steps applied to one dataset.

    Parameters
    ----------
    dataset_id:
        ID of the dataset this pipeline was applied to.
    steps:
        Ordered list of ``PreprocessingStep`` objects.
    """

    dataset_id: str
    steps: List[PreprocessingStep] = field(default_factory=list)

    def add_step(self, step: PreprocessingStep) -> None:
        """Append a step to the pipeline."""
        self.steps.append(step)

    def steps_by_category(self, category: StepCategory) -> List[PreprocessingStep]:
        """Return all steps belonging to the given category."""
        return [s for s in self.steps if s.category == category]

    def summary(self) -> List[str]:
        """Return a one-line description of each step."""
        return [f"[{s.category.value}] {s.name} ({s.tool} {s.tool_version})" for s in self.steps]


# ------------------------------------------------------------------ #
# Known preprocessing pipelines for the three public datasets        #
# ------------------------------------------------------------------ #

PBMC3K_PIPELINE = PreprocessingPipeline(
    dataset_id="pbmc3k",
    steps=[
        PreprocessingStep(
            name="Cell Ranger alignment",
            category=StepCategory.ALIGNMENT,
            tool="Cell Ranger",
            tool_version="2.1.0",
            reference="GRCh38 / Ensembl 93",
        ),
        PreprocessingStep(
            name="Basic quality filter",
            category=StepCategory.QUALITY_FILTER,
            tool="Seurat",
            tool_version="3.2.3",
            parameters={"min_genes": 200, "max_genes": 2500, "max_pct_mito": 5.0},
        ),
        PreprocessingStep(
            name="log1p(CP10K) normalisation",
            category=StepCategory.NORMALISATION,
            tool="Seurat",
            tool_version="3.2.3",
            parameters={"scale_factor": 10000, "log_transform": True},
            notes="NormalizeData with default LogNormalize method.",
        ),
        PreprocessingStep(
            name="Highly variable gene selection",
            category=StepCategory.FEATURE_SELECTION,
            tool="Seurat",
            tool_version="3.2.3",
            parameters={"n_top_genes": 2000, "method": "vst"},
        ),
        PreprocessingStep(
            name="Scale to zero mean / unit variance",
            category=StepCategory.SCALING,
            tool="Seurat",
            tool_version="3.2.3",
            parameters={"max_value": 10},
        ),
        PreprocessingStep(
            name="PCA",
            category=StepCategory.DIMENSIONALITY_REDUCTION,
            tool="Seurat",
            tool_version="3.2.3",
            parameters={"n_pcs": 50},
        ),
        PreprocessingStep(
            name="Louvain clustering",
            category=StepCategory.CLUSTERING,
            tool="Seurat",
            tool_version="3.2.3",
            parameters={"resolution": 0.5, "algorithm": "louvain"},
        ),
        PreprocessingStep(
            name="UMAP embedding",
            category=StepCategory.EMBEDDING,
            tool="Seurat",
            tool_version="3.2.3",
            parameters={"n_neighbours": 10, "metric": "cosine"},
        ),
        PreprocessingStep(
            name="Manual cluster annotation",
            category=StepCategory.ANNOTATION,
            tool="manual",
            tool_version="N/A",
            notes="Cluster labels assigned by visual inspection of marker genes.",
        ),
    ],
)

TABULA_MURIS_PIPELINE = PreprocessingPipeline(
    dataset_id="tabula_muris",
    steps=[
        PreprocessingStep(
            name="STAR alignment (Smart-seq2) / Cell Ranger (10x)",
            category=StepCategory.ALIGNMENT,
            tool="STAR / Cell Ranger",
            tool_version="2.5.3a / 2.0.0",
            reference="mm10 / Ensembl 93",
            notes=(
                "Two separate aligners used depending on protocol; "
                "FACS plates aligned with STAR, droplet libraries with Cell Ranger."
            ),
        ),
        PreprocessingStep(
            name="Per-technology quality filter",
            category=StepCategory.QUALITY_FILTER,
            tool="Seurat",
            tool_version="2.3.4",
            parameters={
                "min_genes_smartseq2": 500,
                "min_genes_10x": 200,
                "max_pct_mito": 10.0,
            },
            notes="Thresholds differ between Smart-seq2 and 10x data.",
        ),
        PreprocessingStep(
            name="log1p(CP10K) normalisation (per tissue)",
            category=StepCategory.NORMALISATION,
            tool="Seurat",
            tool_version="2.3.4",
            parameters={"scale_factor": 10000, "log_transform": True},
            notes="Normalisation applied independently per tissue compartment.",
        ),
        PreprocessingStep(
            name="Per-tissue highly variable gene selection",
            category=StepCategory.FEATURE_SELECTION,
            tool="Seurat",
            tool_version="2.3.4",
            parameters={"method": "dispersion"},
            notes="Gene selection done independently per tissue — HVG sets are not comparable across tissues.",
        ),
        PreprocessingStep(
            name="PCA (per tissue)",
            category=StepCategory.DIMENSIONALITY_REDUCTION,
            tool="Seurat",
            tool_version="2.3.4",
            parameters={"n_pcs": 20},
        ),
        PreprocessingStep(
            name="Louvain clustering (per tissue)",
            category=StepCategory.CLUSTERING,
            tool="Seurat",
            tool_version="2.3.4",
            parameters={"resolution": 0.5, "algorithm": "louvain"},
        ),
        PreprocessingStep(
            name="Manual + ontology-guided annotation",
            category=StepCategory.ANNOTATION,
            tool="manual",
            tool_version="N/A",
            notes=(
                "Curators assigned CL ontology IDs where possible; "
                "~30 % of cells remain unannotated."
            ),
        ),
    ],
)

CELLXGENE_LUNG_PIPELINE = PreprocessingPipeline(
    dataset_id="cellxgene_lung",
    steps=[
        PreprocessingStep(
            name="STARsolo alignment (per contributing study)",
            category=StepCategory.ALIGNMENT,
            tool="STARsolo",
            tool_version="2.7.10a",
            reference="GRCh38 / Ensembl 104",
            notes="Each contributing study aligned independently; Ensembl 104 used uniformly.",
        ),
        PreprocessingStep(
            name="Ambient RNA removal (SoupX)",
            category=StepCategory.QUALITY_FILTER,
            tool="SoupX",
            tool_version="1.6.2",
            parameters={"contamination_range": [0.01, 0.8]},
        ),
        PreprocessingStep(
            name="Doublet detection (scrublet)",
            category=StepCategory.DOUBLET_DETECTION,
            tool="scrublet",
            tool_version="0.2.3",
            parameters={"doublet_score_threshold": 0.25},
        ),
        PreprocessingStep(
            name="Quality filter",
            category=StepCategory.QUALITY_FILTER,
            tool="Scanpy",
            tool_version="1.9.3",
            parameters={"min_genes": 200, "max_pct_mito": 20.0},
            notes="Higher pct_mito threshold (20 %) than PBMC 3k (5 %) to accommodate lung tissue.",
        ),
        PreprocessingStep(
            name="scran pooling-based normalisation",
            category=StepCategory.NORMALISATION,
            tool="scran",
            tool_version="1.24.0",
            parameters={"min_mean": 0.1},
            notes=(
                "scran normalisation instead of CP10K; produces size factors "
                "that better handle compositional biases in mixed cell type populations."
            ),
        ),
        PreprocessingStep(
            name="Highly variable gene selection (batch-aware)",
            category=StepCategory.FEATURE_SELECTION,
            tool="Scanpy",
            tool_version="1.9.3",
            parameters={"n_top_genes": 4000, "batch_key": "study_id", "flavor": "seurat_v3"},
        ),
        PreprocessingStep(
            name="scVI integration",
            category=StepCategory.BATCH_INTEGRATION,
            tool="scVI-tools",
            tool_version="0.20.0",
            parameters={"n_latent": 30, "n_layers": 2, "n_epochs": 400},
            notes="Variational autoencoder trained on raw counts with study and assay as covariates.",
        ),
        PreprocessingStep(
            name="Leiden clustering (on scVI latent)",
            category=StepCategory.CLUSTERING,
            tool="leidenalg",
            tool_version="0.9.1",
            parameters={"resolution": 1.0, "algorithm": "leiden"},
        ),
        PreprocessingStep(
            name="UMAP embedding (on scVI latent)",
            category=StepCategory.EMBEDDING,
            tool="UMAP",
            tool_version="0.5.3",
            parameters={"n_neighbours": 15, "min_dist": 0.5},
        ),
        PreprocessingStep(
            name="scANVI automated annotation + manual curation",
            category=StepCategory.ANNOTATION,
            tool="scVI-tools (scANVI)",
            tool_version="0.20.0",
            notes="Semi-supervised model trained on manually labelled reference cells.",
        ),
    ],
)


# ------------------------------------------------------------------ #
# Metadata inconsistency models                                       #
# ------------------------------------------------------------------ #


class InconsistencyCategory(str, Enum):
    """Type of cross-dataset metadata inconsistency."""

    GENE_ID_FORMAT = "gene_id_format"
    ORGANISM_ENCODING = "organism_encoding"
    CELL_TYPE_ENCODING = "cell_type_encoding"
    TISSUE_ENCODING = "tissue_encoding"
    DISEASE_ENCODING = "disease_encoding"
    QC_THRESHOLD = "qc_threshold"
    NORMALISATION_METHOD = "normalisation_method"
    INTEGRATION_STRATEGY = "integration_strategy"
    CLUSTERING_ALGORITHM = "clustering_algorithm"
    MISSING_FIELD = "missing_field"
    ONTOLOGY_MISMATCH = "ontology_mismatch"


@dataclass
class MetadataField:
    """A single metadata field as it appears in a specific dataset."""

    dataset_id: str
    field_name: str
    encoding: str
    example_value: str


@dataclass
class MetadataInconsistency:
    """
    A documented inconsistency between two or more datasets.

    Parameters
    ----------
    category:
        The class of inconsistency (gene ID format, organism encoding, …).
    description:
        Human-readable summary of the problem.
    affected_datasets:
        Dataset IDs involved.
    affected_fields:
        The specific fields where the inconsistency appears.
    impact:
        Why this matters for downstream analysis or model training.
    recommendation:
        The preferred canonical encoding that resolves the inconsistency.
    """

    category: InconsistencyCategory
    description: str
    affected_datasets: List[str]
    affected_fields: List[MetadataField]
    impact: str
    recommendation: str

    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "description": self.description,
            "affected_datasets": self.affected_datasets,
            "affected_fields": [
                {
                    "dataset_id": f.dataset_id,
                    "field_name": f.field_name,
                    "encoding": f.encoding,
                    "example_value": f.example_value,
                }
                for f in self.affected_fields
            ],
            "impact": self.impact,
            "recommendation": self.recommendation,
        }


# ------------------------------------------------------------------ #
# Inconsistency detector                                              #
# ------------------------------------------------------------------ #


class InconsistencyDetector:
    """
    Inspects a ``DatasetCatalogue`` and enumerates cross-dataset inconsistencies.

    Call ``detect()`` to obtain a list of all ``MetadataInconsistency`` objects.
    ``detect_by_category()`` filters to a specific ``InconsistencyCategory``.
    """

    # Hard-coded catalogue of known inconsistencies for the three public datasets.
    # In a production system this would be derived programmatically from the data.
    _KNOWN: List[MetadataInconsistency] = [
        MetadataInconsistency(
            category=InconsistencyCategory.GENE_ID_FORMAT,
            description=(
                "PBMC 3k and CELLxGENE Lung use Ensembl stable IDs "
                "(e.g. ENSG00000243485) as the primary gene identifier, "
                "while Tabula Muris uses MGI gene symbols (e.g. 'Gapdh'). "
                "Human and mouse gene symbols also follow different capitalisation "
                "conventions (ALL_CAPS vs Title_case)."
            ),
            affected_datasets=["pbmc3k", "tabula_muris", "cellxgene_lung"],
            affected_fields=[
                MetadataField("pbmc3k", "gene_ids", "ensembl_id", "ENSG00000243485"),
                MetadataField("tabula_muris", "gene_symbol", "mgi_gene_symbol", "Gapdh"),
                MetadataField("cellxgene_lung", "feature_id", "ensembl_id", "ENSG00000243485"),
            ],
            impact=(
                "Gene matrices cannot be concatenated or compared without a "
                "symbol-to-Ensembl mapping step.  Ortholog mapping adds an "
                "additional layer of ambiguity for cross-species analysis."
            ),
            recommendation=(
                "Use Ensembl stable IDs (e.g. ENSG00000243485 for human, "
                "ENSMUSG00000057666 for mouse) as the canonical var index. "
                "Store HGNC / MGI symbols as an additional var column."
            ),
        ),
        MetadataInconsistency(
            category=InconsistencyCategory.ORGANISM_ENCODING,
            description=(
                "Organism is encoded as 'human' (PBMC 3k), 'Mus musculus' "
                "(Tabula Muris), and 'NCBITaxon:9606' (CELLxGENE Lung). "
                "Three different representations for the same concept."
            ),
            affected_datasets=["pbmc3k", "tabula_muris", "cellxgene_lung"],
            affected_fields=[
                MetadataField("pbmc3k", "organism", "free_text", "human"),
                MetadataField("tabula_muris", "organism", "binomial_name", "Mus musculus"),
                MetadataField("cellxgene_lung", "organism_ontology_term_id", "ncbi_taxon_id", "NCBITaxon:9606"),
            ],
            impact=(
                "Automated pipelines that filter or join on organism must "
                "special-case each encoding.  A model trained on concatenated "
                "data would receive contradictory organism tokens."
            ),
            recommendation=(
                "Store organism as an NCBITaxon CURIE (NCBITaxon:9606 for "
                "Homo sapiens, NCBITaxon:10090 for Mus musculus)."
            ),
        ),
        MetadataInconsistency(
            category=InconsistencyCategory.CELL_TYPE_ENCODING,
            description=(
                "Cell type is a free-text cluster nickname in PBMC 3k "
                "('CD4 T cells'), a mix of CL IDs and free text in "
                "Tabula Muris (CL:0000084 / 'unknown'), and an enforced "
                "CL CURIE in CELLxGENE Lung (CL:0000583)."
            ),
            affected_datasets=["pbmc3k", "tabula_muris", "cellxgene_lung"],
            affected_fields=[
                MetadataField("pbmc3k", "cell_type", "free_text", "CD4 T cells"),
                MetadataField("tabula_muris", "cell_ontology_id", "CL_ontology_id", "CL:0000084"),
                MetadataField("tabula_muris", "cell_ontology_class", "free_text", "T cell"),
                MetadataField("cellxgene_lung", "cell_type_ontology_term_id", "CL_ontology_id", "CL:0000583"),
            ],
            impact=(
                "Cell-type grouping across datasets requires string matching "
                "or a manual synonym table.  Models that embed cell-type tokens "
                "cannot generalise across all three datasets without alignment."
            ),
            recommendation=(
                "Store cell type as a CL ontology CURIE in a dedicated column "
                "'cell_type_ontology_term_id'.  Keep a human-readable 'cell_type' "
                "column as well, derived from the CL term label."
            ),
        ),
        MetadataInconsistency(
            category=InconsistencyCategory.TISSUE_ENCODING,
            description=(
                "Tissue is absent (PBMC 3k — assumed from context), a "
                "free-text internal label (Tabula Muris: 'Brain_Myeloid'), "
                "or a UBERON CURIE (CELLxGENE Lung: 'UBERON:0002048')."
            ),
            affected_datasets=["pbmc3k", "tabula_muris", "cellxgene_lung"],
            affected_fields=[
                MetadataField("pbmc3k", "(absent)", "N/A", "(not recorded)"),
                MetadataField("tabula_muris", "tissue", "free_text", "Brain_Myeloid"),
                MetadataField("cellxgene_lung", "tissue_ontology_term_id", "UBERON_ontology_id", "UBERON:0002048"),
            ],
            impact=(
                "Tissue grouping and filtering is impossible across all three "
                "datasets without manual curation of the Tabula Muris tissue "
                "labels and inference of PBMC 3k tissue."
            ),
            recommendation=(
                "Require a 'tissue_ontology_term_id' UBERON CURIE for every cell. "
                "PBMC 3k = UBERON:0013756 (venous blood)."
            ),
        ),
        MetadataInconsistency(
            category=InconsistencyCategory.DISEASE_ENCODING,
            description=(
                "Disease status is absent in PBMC 3k and Tabula Muris. "
                "CELLxGENE Lung uses PATO:0000461 for healthy cells and "
                "MONDO terms for disease — which differs from the DOID "
                "namespace used in the Asclepius models."
            ),
            affected_datasets=["pbmc3k", "tabula_muris", "cellxgene_lung"],
            affected_fields=[
                MetadataField("pbmc3k", "(absent)", "N/A", "(not recorded)"),
                MetadataField("tabula_muris", "(absent)", "N/A", "(not recorded)"),
                MetadataField("cellxgene_lung", "disease_ontology_term_id", "MONDO_or_PATO_ontology_id", "PATO:0000461"),
            ],
            impact=(
                "Models trained to predict disease state cannot use PBMC 3k "
                "or Tabula Muris as labelled healthy controls unless disease "
                "status is imputed."
            ),
            recommendation=(
                "Require a 'disease_ontology_term_id' for every cell. "
                "Healthy cells should use PATO:0000461 ('normal'). "
                "Note: Asclepius currently uses DOID; migrate to MONDO for "
                "consistency with CELLxGENE."
            ),
        ),
        MetadataInconsistency(
            category=InconsistencyCategory.QC_THRESHOLD,
            description=(
                "Mitochondrial read fraction threshold differs across datasets: "
                "5 % (PBMC 3k), 10 % (Tabula Muris), 20 % (CELLxGENE Lung). "
                "Minimum gene count differs too: 200 vs 500 depending on technology."
            ),
            affected_datasets=["pbmc3k", "tabula_muris", "cellxgene_lung"],
            affected_fields=[
                MetadataField("pbmc3k", "percent_mito", "float_percentage", "<5"),
                MetadataField("tabula_muris", "percent_mito", "float_percentage", "<10"),
                MetadataField("cellxgene_lung", "percent_mito", "float_percentage", "<20"),
            ],
            impact=(
                "Concatenating filtered datasets introduces systematic biases: "
                "PBMC 3k will have stricter cell quality than the lung atlas. "
                "This inflates apparent differences between cell types."
            ),
            recommendation=(
                "Record QC thresholds as dataset-level provenance metadata. "
                "Provide raw, unfiltered counts alongside filtered data so that "
                "unified thresholds can be applied retrospectively."
            ),
        ),
        MetadataInconsistency(
            category=InconsistencyCategory.NORMALISATION_METHOD,
            description=(
                "PBMC 3k and Tabula Muris use log1p(CP10K) normalisation. "
                "CELLxGENE Lung uses scran pooling-based normalisation. "
                "The two methods produce different value scales and are not "
                "directly comparable."
            ),
            affected_datasets=["pbmc3k", "tabula_muris", "cellxgene_lung"],
            affected_fields=[
                MetadataField("pbmc3k", "X (normalised layer)", "log1p_cp10k", "log1p(count/sum * 10000)"),
                MetadataField("tabula_muris", "X (normalised layer)", "log1p_cp10k", "log1p(count/sum * 10000)"),
                MetadataField("cellxgene_lung", "X (normalised layer)", "log1p_scran", "log1p(count/size_factor)"),
            ],
            impact=(
                "Gene expression values in the normalised matrix are on "
                "incompatible scales.  A model reading the 'X' slot across "
                "datasets will be comparing incommensurable numbers."
            ),
            recommendation=(
                "Always store raw counts in a dedicated layer (e.g. 'counts'). "
                "Record the normalisation method and parameters as uns metadata. "
                "Apply a unified normalisation (e.g. scran) at integration time."
            ),
        ),
        MetadataInconsistency(
            category=InconsistencyCategory.MISSING_FIELD,
            description=(
                "Suspension type (single cell vs single nucleus) is recorded "
                "only in CELLxGENE Lung.  It is absent in PBMC 3k and "
                "Tabula Muris, even though Tabula Muris contains both FACS "
                "and microfluidic (droplet) protocols."
            ),
            affected_datasets=["pbmc3k", "tabula_muris", "cellxgene_lung"],
            affected_fields=[
                MetadataField("pbmc3k", "(absent)", "N/A", "(not recorded)"),
                MetadataField("tabula_muris", "method", "free_text", "facs / microfluidic"),
                MetadataField("cellxgene_lung", "suspension_type", "free_text", "cell / nucleus"),
            ],
            impact=(
                "Suspension type affects ambient RNA fraction, doublet rates, "
                "and cell-type recovery.  Without this field, batch-correction "
                "algorithms cannot model this technical covariate."
            ),
            recommendation=(
                "Require 'suspension_type' with controlled vocabulary: "
                "'cell', 'nucleus', or 'bulk' for every observation."
            ),
        ),
    ]

    def __init__(self, catalogue: Optional[DatasetCatalogue] = None) -> None:
        from asclepius.singlecell.datasets import DEFAULT_CATALOGUE
        self._catalogue = catalogue if catalogue is not None else DEFAULT_CATALOGUE

    def detect(self) -> List[MetadataInconsistency]:
        """Return all known inconsistencies for the catalogue's datasets."""
        ids = set(self._catalogue.dataset_ids())
        return [
            inc for inc in self._KNOWN
            if any(ds_id in ids for ds_id in inc.affected_datasets)
        ]

    def detect_by_category(
        self, category: InconsistencyCategory
    ) -> List[MetadataInconsistency]:
        """Return inconsistencies filtered to the given category."""
        return [inc for inc in self.detect() if inc.category == category]

    def summary_report(self) -> str:
        """Return a multi-line human-readable summary of all inconsistencies."""
        lines = ["=== Cross-Dataset Metadata Inconsistency Report ===\n"]
        for i, inc in enumerate(self.detect(), start=1):
            lines.append(f"{i}. [{inc.category.value}]")
            lines.append(f"   Datasets: {', '.join(inc.affected_datasets)}")
            lines.append(f"   Problem : {inc.description}")
            lines.append(f"   Impact  : {inc.impact}")
            lines.append(f"   Fix     : {inc.recommendation}")
            lines.append("")
        return "\n".join(lines)
