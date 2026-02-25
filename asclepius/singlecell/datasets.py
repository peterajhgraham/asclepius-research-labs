"""
Catalogue of three public single-cell RNA-seq datasets.

Each ``PublicDataset`` entry records:
- Where the data comes from (DOI / accession)
- Observed metadata fields and their encodings *as found in the source*
- Which preprocessing pipeline was applied
- Known metadata quirks / inconsistencies

The three datasets chosen span different labs, technologies, organisms, and
annotation conventions — making them ideal for exposing cross-dataset friction.

Dataset 1 – 10x Genomics PBMC 3k (Zheng et al., 2017)
    2,700 peripheral blood mononuclear cells from a healthy donor.
    The canonical beginner tutorial dataset.  Gene IDs are Ensembl IDs;
    cell types are free-text Seurat cluster labels.

Dataset 2 – Tabula Muris (Tabula Muris Consortium, 2018)
    ~100 k cells across 20 mouse organs sequenced with Smart-seq2 and
    10x Chromium.  Uses Cell Ontology IDs for some tissues, free-text
    labels for others; organism is encoded as "Mus musculus".

Dataset 3 – CELLxGENE Human Lung Cell Atlas (Sikkema et al., 2023)
    ~2.4 M cells from the human lung.  Hosted on CZ CELLxGENE, enforcing
    their schema (ontology-backed fields, Ensembl gene IDs).  Uses
    UBERON for tissue, CL for cell type, EFO for assay.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class MetadataColumn:
    """
    A single metadata column as it actually appears in a public dataset.

    Parameters
    ----------
    name:
        Column name in the source file (e.g. ``"cell_type"``).
    observed_values:
        Representative values seen in the data.
    encoding:
        How the value is expressed (e.g. ``"free_text"``, ``"CL_ontology_id"``,
        ``"ensembl_id"``, ``"ncbi_taxon_id"``).
    notes:
        Any caveats about this column.
    """

    name: str
    observed_values: List[str]
    encoding: str
    notes: Optional[str] = None


@dataclass
class PublicDataset:
    """
    A public single-cell dataset together with its observed metadata structure.

    This is a *catalogue entry*, not a data container.  It describes what
    metadata fields exist and how they are encoded so that downstream code can
    detect and resolve cross-dataset inconsistencies.
    """

    dataset_id: str
    title: str
    citation: str
    accession: str                          # GEO / ArrayExpress / CELLxGENE ID
    organism: str                           # As encoded in the source
    n_cells_approx: int
    technology: str                         # e.g. "10x Chromium v2"
    gene_id_format: str                     # "ensembl_id", "gene_symbol", "entrez_id"
    obs_columns: List[MetadataColumn] = field(default_factory=list)
    var_columns: List[MetadataColumn] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def obs_column_names(self) -> List[str]:
        """Return the list of observation (cell) metadata column names."""
        return [c.name for c in self.obs_columns]

    def var_column_names(self) -> List[str]:
        """Return the list of variable (gene) metadata column names."""
        return [c.name for c in self.var_columns]

    def obs_encoding_map(self) -> Dict[str, str]:
        """Return a mapping of column name → encoding for obs metadata."""
        return {c.name: c.encoding for c in self.obs_columns}


# ------------------------------------------------------------------ #
# Dataset 1 – 10x PBMC 3k                                            #
# ------------------------------------------------------------------ #

PBMC3K = PublicDataset(
    dataset_id="pbmc3k",
    title="Massively parallel digital transcriptional profiling of single cells",
    citation="Zheng et al., Nature Communications, 2017",
    accession="GSE96315",
    organism="human",                       # NOTE: informal string, not NCBITaxon
    n_cells_approx=2700,
    technology="10x Chromium v2",
    gene_id_format="ensembl_id",
    obs_columns=[
        MetadataColumn(
            name="cell_type",
            observed_values=[
                "CD4 T cells", "CD14+ Monocytes", "B cells",
                "CD8 T cells", "NK cells", "FCGR3A+ Monocytes",
                "Dendritic cells", "Megakaryocytes",
            ],
            encoding="free_text",
            notes=(
                "Labels are Seurat cluster names assigned post-hoc; "
                "no ontology identifier is recorded."
            ),
        ),
        MetadataColumn(
            name="n_genes",
            observed_values=["200", "201", "4352"],
            encoding="integer_count",
            notes="Minimum threshold of 200 genes applied during QC.",
        ),
        MetadataColumn(
            name="n_counts",
            observed_values=["500", "501", "15000"],
            encoding="integer_count",
        ),
        MetadataColumn(
            name="percent_mito",
            observed_values=["0.0", "0.5", "4.9"],
            encoding="float_percentage",
            notes="Cells with >5 % mitochondrial reads were removed.",
        ),
        MetadataColumn(
            name="louvain",
            observed_values=["0", "1", "2", "3", "4", "5", "6", "7"],
            encoding="integer_cluster_label",
            notes="Louvain cluster index; mapped to cell_type separately.",
        ),
    ],
    var_columns=[
        MetadataColumn(
            name="gene_ids",
            observed_values=["ENSG00000243485", "ENSG00000237613"],
            encoding="ensembl_id",
        ),
        MetadataColumn(
            name="gene_names",
            observed_values=["MIR1302-10", "FAM138A", "GAPDH"],
            encoding="hgnc_gene_symbol",
        ),
        MetadataColumn(
            name="n_cells",
            observed_values=["3", "10", "2638"],
            encoding="integer_count",
        ),
    ],
    notes=[
        "Donor metadata (age, sex, disease status) is absent.",
        "Organism recorded as the informal string 'human', not NCBITaxon:9606.",
        "No tissue ontology term; assumed PBMC from context.",
        "Cell-type labels are cluster nicknames, not CL ontology terms.",
        "Raw counts stored; normalisation is log1p(CP10K) applied in-memory.",
    ],
)


# ------------------------------------------------------------------ #
# Dataset 2 – Tabula Muris                                            #
# ------------------------------------------------------------------ #

TABULA_MURIS = PublicDataset(
    dataset_id="tabula_muris",
    title="Single-cell transcriptomics of 20 mouse organs creates a Tabula Muris",
    citation="Tabula Muris Consortium, Nature, 2018",
    accession="GSE109774",
    organism="Mus musculus",                # NOTE: binomial name, not NCBITaxon
    n_cells_approx=100605,
    technology="Smart-seq2 + 10x Chromium v2 (mixed)",
    gene_id_format="gene_symbol",           # NOTE: symbols, not Ensembl IDs
    obs_columns=[
        MetadataColumn(
            name="cell_ontology_class",
            observed_values=[
                "T cell", "B cell", "macrophage",
                "endothelial cell", "hepatocyte",
            ],
            encoding="free_text",
            notes=(
                "Human-readable cell class; present for most but not all "
                "cells — some are labelled 'unknown'."
            ),
        ),
        MetadataColumn(
            name="cell_ontology_id",
            observed_values=["CL:0000084", "CL:0000236", "CL:0000235"],
            encoding="CL_ontology_id",
            notes=(
                "CL term present for ~70 % of cells; remaining cells have "
                "NaN or the placeholder 'CL:0000000' (root term)."
            ),
        ),
        MetadataColumn(
            name="tissue",
            observed_values=["Liver", "Lung", "Heart", "Brain_Myeloid"],
            encoding="free_text",
            notes=(
                "Tissue is a free-text label (not UBERON); capitalisation "
                "and compound names (e.g. 'Brain_Myeloid') vary by organ."
            ),
        ),
        MetadataColumn(
            name="mouse.sex",
            observed_values=["M", "F"],
            encoding="single_character_code",
            notes="'M'/'F' — differs from 'male'/'female' convention elsewhere.",
        ),
        MetadataColumn(
            name="mouse.id",
            observed_values=["3_10_M", "3_38_F"],
            encoding="lab_internal_id",
            notes="Internal mouse identifier; no mapping to an external registry.",
        ),
        MetadataColumn(
            name="subtissue",
            observed_values=["T cell zone", "germinal center", "portal"],
            encoding="free_text",
        ),
        MetadataColumn(
            name="method",
            observed_values=["facs", "microfluidic"],
            encoding="free_text",
            notes=(
                "Indicates Smart-seq2 (facs) or 10x (microfluidic); "
                "affects count distributions and QC thresholds."
            ),
        ),
    ],
    var_columns=[
        MetadataColumn(
            name="gene_symbol",
            observed_values=["Gapdh", "Actb", "Cd3e"],
            encoding="mgi_gene_symbol",
            notes=(
                "Mouse gene symbols (MGI convention); cannot be directly "
                "compared to human HGNC symbols without a mapping table."
            ),
        ),
    ],
    notes=[
        "Gene identifiers are MGI symbols, not Ensembl IDs — requires "
        "ortholog mapping to compare with human datasets.",
        "Mixed technologies (Smart-seq2 and 10x) in the same dataset "
        "produce different count distributions; 'method' column must be "
        "used to stratify QC thresholds.",
        "Cell ontology IDs absent for ~30 % of cells.",
        "Tissue labels use internal naming conventions, not UBERON CURIEs.",
        "Organism encoded as binomial name 'Mus musculus', not NCBITaxon:10090.",
        "No disease status field — all mice are assumed healthy.",
    ],
)


# ------------------------------------------------------------------ #
# Dataset 3 – CELLxGENE Human Lung Cell Atlas                         #
# ------------------------------------------------------------------ #

CELLXGENE_LUNG = PublicDataset(
    dataset_id="cellxgene_lung",
    title=(
        "An integrated cell atlas of the human lung in health and disease "
        "(LungMAP / CELLxGENE)"
    ),
    citation="Sikkema et al., Nature Medicine, 2023",
    accession="CXG:lung_atlas_v1",
    organism="Homo sapiens",                # NCBITaxon enforced by CELLxGENE schema
    n_cells_approx=2400000,
    technology="10x Chromium v2/v3 + Smart-seq2 (integrated)",
    gene_id_format="ensembl_id",            # CELLxGENE enforces Ensembl IDs
    obs_columns=[
        MetadataColumn(
            name="cell_type_ontology_term_id",
            observed_values=["CL:0000583", "CL:0002063", "CL:0000775"],
            encoding="CL_ontology_id",
            notes="CELLxGENE schema enforces a valid CL term for every cell.",
        ),
        MetadataColumn(
            name="cell_type",
            observed_values=["alveolar macrophage", "type II pneumocyte", "neutrophil"],
            encoding="free_text",
            notes="Human-readable label; derived from the CL term label.",
        ),
        MetadataColumn(
            name="tissue_ontology_term_id",
            observed_values=["UBERON:0002048", "UBERON:0001004"],
            encoding="UBERON_ontology_id",
        ),
        MetadataColumn(
            name="disease_ontology_term_id",
            observed_values=["PATO:0000461", "MONDO:0004979"],
            encoding="MONDO_or_PATO_ontology_id",
            notes=(
                "Healthy cells use PATO:0000461 ('normal'); "
                "diseased cells use MONDO terms."
            ),
        ),
        MetadataColumn(
            name="assay_ontology_term_id",
            observed_values=["EFO:0009899", "EFO:0010010"],
            encoding="EFO_ontology_id",
            notes="EFO:0009899 = 10x 3' v2, EFO:0010010 = 10x 3' v3.",
        ),
        MetadataColumn(
            name="organism_ontology_term_id",
            observed_values=["NCBITaxon:9606"],
            encoding="ncbi_taxon_id",
        ),
        MetadataColumn(
            name="sex_ontology_term_id",
            observed_values=["PATO:0000383", "PATO:0000384"],
            encoding="PATO_ontology_id",
            notes="PATO:0000383 = female, PATO:0000384 = male.",
        ),
        MetadataColumn(
            name="donor_id",
            observed_values=["D001", "D002"],
            encoding="lab_internal_id",
            notes="De-identified donor identifier; no cross-study linkage.",
        ),
        MetadataColumn(
            name="suspension_type",
            observed_values=["cell", "nucleus"],
            encoding="free_text",
            notes="Distinguishes single-cell from single-nucleus protocols.",
        ),
    ],
    var_columns=[
        MetadataColumn(
            name="feature_id",
            observed_values=["ENSG00000243485", "ENSG00000223972"],
            encoding="ensembl_id",
            notes="CELLxGENE enforces Ensembl stable gene IDs.",
        ),
        MetadataColumn(
            name="feature_name",
            observed_values=["MIR1302-2HG", "DDX11L1", "GAPDH"],
            encoding="hgnc_gene_symbol",
        ),
        MetadataColumn(
            name="feature_biotype",
            observed_values=["gene", "spike-in"],
            encoding="free_text",
        ),
    ],
    notes=[
        "CELLxGENE schema enforces ontology-backed fields, making this the "
        "most consistently annotated of the three datasets.",
        "Raw counts are stored alongside normalised embeddings.",
        "Mixed assay types (10x v2, v3, Smart-seq2) require assay-aware "
        "normalisation before integration.",
        "Disease status is encoded with MONDO / PATO — a different ontology "
        "from DOID used in the Asclepius models.",
        "Suspension type (cell vs nucleus) affects ambient RNA and doublet "
        "rates but is absent in PBMC 3k and Tabula Muris.",
    ],
)


# ------------------------------------------------------------------ #
# Catalogue                                                            #
# ------------------------------------------------------------------ #


@dataclass
class DatasetCatalogue:
    """
    A collection of ``PublicDataset`` entries.

    Provides convenience look-up and comparison methods used by
    ``InconsistencyDetector``.
    """

    datasets: List[PublicDataset] = field(default_factory=list)

    def add(self, dataset: PublicDataset) -> None:
        """Add a dataset to the catalogue."""
        self.datasets.append(dataset)

    def get(self, dataset_id: str) -> Optional[PublicDataset]:
        """Return the dataset with the given ID, or None."""
        for ds in self.datasets:
            if ds.dataset_id == dataset_id:
                return ds
        return None

    def dataset_ids(self) -> List[str]:
        """Return all dataset IDs in insertion order."""
        return [ds.dataset_id for ds in self.datasets]

    def obs_column_union(self) -> Dict[str, List[str]]:
        """
        Return a mapping of obs column name → list of dataset IDs that have it.

        Useful for identifying which fields are present in some datasets but
        missing in others.
        """
        result: Dict[str, List[str]] = {}
        for ds in self.datasets:
            for col in ds.obs_columns:
                result.setdefault(col.name, []).append(ds.dataset_id)
        return result

    def gene_id_formats(self) -> Dict[str, str]:
        """Return a mapping of dataset_id → gene_id_format."""
        return {ds.dataset_id: ds.gene_id_format for ds in self.datasets}

    def organism_encodings(self) -> Dict[str, str]:
        """Return a mapping of dataset_id → organism string as encoded in source."""
        return {ds.dataset_id: ds.organism for ds in self.datasets}


# Default catalogue containing all three datasets.
DEFAULT_CATALOGUE = DatasetCatalogue(datasets=[PBMC3K, TABULA_MURIS, CELLXGENE_LUNG])
