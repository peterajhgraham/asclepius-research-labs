# Asclepius Research Labs – Biological Data Infrastructure

A starter Python application for managing biological research data: RNA-seq experiments, perturbation metadata, batch provenance, and ontology terms.

## Overview

This project addresses the foundational data-infrastructure needs of a modern biology lab:

| Concern | Module |
|---|---|
| RNA-seq data storage & versioning | `asclepius/models/rnaseq.py` |
| Perturbation metadata | `asclepius/models/perturbation.py` |
| Batch effect provenance | `asclepius/models/batch.py` |
| Biological ontologies | `asclepius/models/ontology.py` |
| Persistent storage | `asclepius/storage/database.py` |
| Command-line interface | `asclepius/cli.py` |
| **Single-cell dataset observation** | **`asclepius/singlecell/`** |

### Single-Cell Dataset Observation

The `asclepius/singlecell/` sub-package catalogues three public single-cell
RNA-seq datasets, traces their preprocessing steps, documents cross-dataset
metadata inconsistencies, and proposes a unified schema that answers the
question **"if I were a model, what structure would I wish existed?"**

| Sub-module | Purpose |
|---|---|
| `singlecell/datasets.py` | Catalogue of 3 public datasets with observed metadata fields |
| `singlecell/preprocessing.py` | Preprocessing step models + inconsistency detector |
| `singlecell/schema.py` | `UnifiedCell` / `UnifiedDataset` schema + `SchemaValidator` |

## Quick Start

```bash
# Install
pip install -e .

# Initialise a new database
python -m asclepius init

# List all experiments
python -m asclepius experiments list

# Show version history for an experiment
python -m asclepius experiments versions EXP_001

# List batches for an experiment
python -m asclepius batches list --experiment EXP_001

# List perturbations
python -m asclepius perturbations list

# Browse ontology terms
python -m asclepius ontology list --namespace GO --no-deprecated
```

## Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## Key Concepts

### RNA-seq Versioning
`RNASeqExperiment.content_hash()` computes a SHA-256 digest over the
experiment's scientific content (assembly, annotation, pipeline version,
and sample list). Any modification that changes the biology produces a
new hash, which is recorded in the `version_log` table on every save.

### Perturbation Metadata
`Perturbation` follows LINCS / JUMP-CP metadata conventions, capturing
compound identity, dose, duration, target gene, and vehicle — everything
needed to compare perturbation responses across datasets.

### Batch Provenance
`Batch` records sequencing date, platform, flow cell, library-kit lot,
and RNA-extraction lot. These fields feed directly into batch-correction
algorithms (ComBat, Harmony, scVI).

### Ontology Terms
`OntologyTerm` tracks whether a term is current or deprecated and, if
deprecated, which term replaces it. This surfaces broken ontology links
before they propagate through downstream analysis.

## Project Layout

```
asclepius/
    models/
        rnaseq.py          # RNASeqExperiment, Sample
        perturbation.py    # Perturbation, PerturbationType
        batch.py           # Batch
        ontology.py        # OntologyTerm, OntologyNamespace
    singlecell/
        datasets.py        # PublicDataset catalogue (PBMC 3k, Tabula Muris, CELLxGENE Lung)
        preprocessing.py   # PreprocessingPipeline, MetadataInconsistency, InconsistencyDetector
        schema.py          # UnifiedCell, UnifiedDataset, SchemaValidator
    storage/
        database.py        # SQLite-backed Database
    cli.py                 # Command-line interface
tests/
    test_models.py
    test_storage.py
    test_singlecell.py
pyproject.toml
requirements.txt
```

### The Three Public Datasets

| Dataset | Accession | Organism | Technology | Cells | Gene ID format |
|---|---|---|---|---|---|
| 10x PBMC 3k (Zheng et al., 2017) | GSE96315 | `"human"` (informal) | 10x Chromium v2 | ~2,700 | Ensembl IDs |
| Tabula Muris (Tabula Muris Consortium, 2018) | GSE109774 | `"Mus musculus"` (binomial) | Smart-seq2 + 10x | ~100,000 | MGI gene symbols |
| CELLxGENE Lung Atlas (Sikkema et al., 2023) | CXG:lung_atlas_v1 | `NCBITaxon:9606` (CURIE) | 10x v2/v3 + Smart-seq2 | ~2,400,000 | Ensembl IDs |

### Documented Metadata Inconsistencies

| Category | Datasets | Problem |
|---|---|---|
| Gene ID format | All three | Ensembl IDs vs MGI symbols — cannot concatenate without mapping |
| Organism encoding | All three | `"human"` vs `"Mus musculus"` vs `NCBITaxon:9606` |
| Cell type encoding | All three | Free-text cluster names vs CL ontology CURIEs |
| Tissue encoding | All three | Absent / free-text internal labels vs UBERON CURIEs |
| Disease encoding | All three | Absent vs MONDO / PATO CURIEs |
| QC threshold | All three | Mitochondrial threshold 5 % vs 10 % vs 20 % |
| Normalisation method | All three | log1p(CP10K) vs scran — incompatible scales |
| Missing field | All three | Suspension type (cell vs nucleus) absent in PBMC 3k and Tabula Muris |

### The Unified Schema

`UnifiedCell` specifies the per-cell metadata that a model would wish existed:

- **`organism_ontology_term_id`** – `NCBITaxon:` CURIE, never an informal string
- **`tissue_ontology_term_id`** – `UBERON:` CURIE
- **`cell_type_ontology_term_id`** – `CL:` CURIE
- **`disease_ontology_term_id`** – `MONDO:` or `PATO:` CURIE (`PATO:0000461` = healthy)
- **`assay_ontology_term_id`** – `EFO:` CURIE
- **`sex`** – `PATO:` CURIE from the `Sex` enum
- **`suspension_type`** – `"cell"` | `"nucleus"` | `"bulk"`
- QC scalars: `n_counts`, `n_genes`, `pct_counts_mito`, `doublet_score`
- Provenance: `donor_id`, `sample_id`, `batch_id`, `preprocessing_pipeline_id`

`UnifiedDataset` requires at least a `RAW` counts layer so that any
normalisation strategy can be applied retrospectively.

`SchemaValidator` enforces all CURIE prefix rules and numeric range
constraints programmatically.