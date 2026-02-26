# Asclepius Research Labs — Monogenic Neurology Variant → Pathway Platform

## What This Is

> A modular, neurology-focused platform that maps genetic variants to biological pathways, built as the foundation for a rare-disease AI MVP.

The platform ingests public variant databases (ClinVar, gnomAD) and pathway
resources (KEGG, Reactome), normalises all identifiers to a canonical form,
and scores each pathway by the cumulative impact of variants mapped to its
member genes.

---

## Neurology Variant → Pathway Module

### Repository Layout

```
asclepius-neuro/
├── data_ingestion/
│   ├── load_clinvar.py          ← ClinVar variant–disease records
│   ├── load_gnomad.py           ← gnomAD population frequencies (file + API)
│   └── load_pathways.py         ← KEGG and Reactome pathway sets
├── preprocessing/
│   ├── normalize_variants.py    ← Canonical chrom:pos:ref:alt representation
│   ├── gene_to_pathway_mapping.py ← Gene ↔ pathway bidirectional index
│   └── ontology_normalization.py  ← HPO / OMIM / MONDO / MedGen term parsing
├── models/
│   ├── variant_pathway_model.py ← VariantPathwayGraph (bipartite graph)
│   └── scoring.py               ← Pathway impact scoring + ranking
├── experiments/
│   ├── notebook_1_variant_pathway.ipynb  ← End-to-end mapping demo
│   └── evaluation.ipynb                  ← P@K, Recall@K, MRR metrics
├── utils/
│   ├── helpers.py               ← to_snake_case, build_variant_key, chunked, …
│   └── config.py                ← API URLs, weights, project paths
├── README.md
└── requirements.txt
```

### Quick Start

```bash
pip install -e .
```

#### Run the end-to-end demo (offline synthetic data)

```python
from data_ingestion.load_clinvar import ClinVarRecord
from data_ingestion.load_pathways import Pathway
from preprocessing.normalize_variants import normalize_clinvar_records
from preprocessing.gene_to_pathway_mapping import build_gene_pathway_map
from models.variant_pathway_model import build_variant_pathway_graph
from models.scoring import rank_pathways

# 1. Load variants (swap for load_clinvar_tsv in production)
records = [
    ClinVarRecord(variant_id='1388948', gene_symbol='LRRK2', chrom='12',
                  pos=40340400, ref='G', alt='A',
                  clinical_significance='Pathogenic',
                  condition='Parkinson disease, late-onset',
                  review_status='criteria provided, single submitter'),
]

# 2. Load pathways (swap for load_kegg_pathways in production)
pathways = [
    Pathway(pathway_id='hsa05012', name='Parkinson disease',
            source='KEGG', gene_symbols=['LRRK2', 'PINK1', 'PARK7', 'SNCA']),
]

# 3. Normalise → index → graph → score
variants  = normalize_clinvar_records(records)
gene_map  = build_gene_pathway_map(pathways)
graph     = build_variant_pathway_graph(variants, gene_map)
ranked    = rank_pathways(graph)

for ps in ranked:
    print(ps.pathway_id, ps.normalised_score, ps.pathway_name)
```

#### Load real ClinVar data

```python
from data_ingestion.load_clinvar import load_clinvar_tsv

# Download variant_summary.txt.gz from:
# https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz
records = load_clinvar_tsv("data/raw/variant_summary.txt.gz", neurology_only=True)
print(f"{len(records)} neurology variants loaded")
```

#### Fetch gnomAD variants via API

```python
from data_ingestion.load_gnomad import fetch_gnomad_gene_variants

records = fetch_gnomad_gene_variants("LRRK2", dataset="gnomad_r4")
print(f"{len(records)} gnomAD variants for LRRK2")
```

#### Load KEGG pathways

```python
from data_ingestion.load_pathways import load_kegg_pathways

pathways = load_kegg_pathways("hsa", fetch_genes=True)
print(f"{len(pathways)} human KEGG pathways loaded")
```

### Architecture

```
ClinVar / gnomAD
       │
       ▼
data_ingestion          ← raw records (ClinVarRecord, GnomadRecord, Pathway)
       │
       ▼
preprocessing           ← NormalizedVariant + GenePathwayMap + OntologyTerm
       │
       ▼
models                  ← VariantPathwayGraph + PathwayScore
       │
       ▼
experiments             ← Jupyter notebooks (demo + evaluation)
```

### Scoring

Each variant contributes a weight to every pathway its gene participates in:

| Variant class         | Weight | Criteria                     |
|-----------------------|--------|------------------------------|
| High-confidence LoF   | 2.0    | `lof == "HC"`                |
| Pathogenic            | 1.0    | ClinVar pathogenic/LP        |
| VUS                   | 0.1    | Variant of uncertain significance |
| Benign                | 0.0    | Excluded                     |

Raw scores are burden-normalised by `log2(pathway_gene_count + 1)` to
reduce bias towards large pathways.

### Extensibility

The modular design supports future expansion into:

- **Gene Therapy Target Prioritisation** – prioritise genes with high
  pathway burden and druggable annotations
- **Mechanistic Disease Modelling** – integrate protein interaction
  networks for multi-hop pathway reasoning
- **Rare Oncology** – swap neurology filters for oncology phenotype terms
- **Immunology** – plug in immune pathway gene sets (Reactome immune
  pathways, InnateDB)

---

## Legacy scRNA-seq Data Layer

> The sections below describe the original single-cell RNA-seq structured
> data layer.  It remains fully functional alongside the new neurology
> module.

### What This Was

> You are building a structured, versioned data layer that makes biological experiments reproducible, queryable, and model-ready.

You are **not** discovering drugs.  
You are turning messy experimental outputs into clean, relational state graphs.

---

## Project Layout

```
asclepius-research-labs/
│
├── data/
│   ├── raw/            ← original, unmodified source files
│   └── processed/      ← outputs of ingestion / preprocessing
│
├── notebooks/
│   ├── 01_dataset_autopsy.ipynb    ← structural analysis of PBMC 3k
│   └── 02_schema_mapping.ipynb     ← map raw fields → Asclepius v1 schema
│
├── asclepius/
│   ├── schema.py       ← Experiment, Sample, CellState, ProcessingPipeline
│   ├── models.py       ← BiologicalStateGraph
│   ├── ingestion.py    ← load & validate scRNA-seq data
│   └── versioning.py   ← git-like dataset lineage tracking
│
├── docs/
│   ├── pain_points.md      ← concrete problems this project solves
│   ├── schema_v1.md        ← formal schema specification
│   └── landscape_map.md    ← tool landscape & where Asclepius fits
│
├── experiments/        ← ad-hoc experiment scripts (not notebooks)
│
└── README.md
```

---

## Core Concepts

### Schema (`asclepius/schema.py`)

Four entities form the biological state graph:

| Entity | Description |
|---|---|
| `Experiment` | Top-level container (organism, assay, date, pipeline version) |
| `Sample` | A sample within an experiment with perturbation metadata |
| `CellState` | Observed state of a single cell with data pointers |
| `ProcessingPipeline` | Versioned preprocessing pipeline definition |

### State Graph (`asclepius/models.py`)

`BiologicalStateGraph` assembles the four entities into a relational graph
with validation:

```python
from datetime import date
from asclepius import Experiment, ProcessingPipeline, Sample, CellState, BiologicalStateGraph

graph = BiologicalStateGraph(
    experiment=Experiment(id="GSE96315", organism="NCBITaxon:9606",
                          assay_type="EFO:0009899", date=date(2017, 1, 1)),
    pipeline=ProcessingPipeline(id="cellranger_v2", reference_genome="GRCh38",
                                normalization_method="log1p_CP10K"),
)
graph.add_sample(Sample(id="S1", experiment_id="GSE96315"))
print(graph.summary())
```

### Ingestion (`asclepius/ingestion.py`)

Validates and loads single-cell metadata and expression matrices:

```python
from asclepius import ingest

result = ingest("data/raw/pbmc3k_metadata.csv", "data/raw/pbmc3k_expression.csv")
print(f"Loaded {len(result.cells)} cells")
for w in result.warnings:
    print("WARNING:", w)
```

**Required metadata fields:** `cell_id`, `experiment_id`, `assay_type`, `organism`

Column names are automatically normalized to `snake_case`.

### Versioning (`asclepius/versioning.py`)

Git-like lineage tracking for processed datasets:

```python
from asclepius import VersionRegistry

reg = VersionRegistry()

v1 = reg.register("pbmc3k", {"norm": "log1p_CP10K", "genome": "GRCh38"})
v2 = reg.commit(v1, {"norm": "scran", "genome": "GRCh38"}, notes="Switch to scran normalisation")

branch = reg.branch(v1, "experiment-mito-filter", notes="Test tighter mito threshold")

print([h.processing_version for h in reg.history(v2)])
# ['1.0.0', '1.0.1']
```

---

## Dataset

Starting point: **10x PBMC 3k** (Zheng et al., 2017)

| Field | Value |
|---|---|
| GEO Accession | GSE96315 |
| Organism | *Homo sapiens* |
| Technology | 10x Chromium v2 |
| Approx. cells | 2,700 |
| Gene ID format | Ensembl IDs |

Download raw data from [GEO GSE96315](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE96315) into `data/raw/`.

---

## Quick Start

```bash
# Install
pip install -e .

# Run tests
python -m pytest tests/ -v
```

---

## Documentation

| Document | Contents |
|---|---|
| [`docs/schema_v1.md`](docs/schema_v1.md) | Formal schema specification for v1 |
| [`docs/pain_points.md`](docs/pain_points.md) | Concrete problems this layer solves |
| [`docs/landscape_map.md`](docs/landscape_map.md) | Tool landscape & positioning |
